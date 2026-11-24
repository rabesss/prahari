#!/usr/bin/env python3
"""Reproducible Android (adb) benchmark & telemetry collector for Prahari.

Supports four subcommands:
  probe     - Capture device SoC/ABI/CPU ISA flags, RAM, battery temp, APK & model hashes.
  stage     - Install APK, audit absence of INTERNET permission, push .pte & tokenizer, verify SHA-256.
  run       - Run timed sample checks over adb with continuous `dumpsys meminfo` peak PSS/RSS
              polling, optional airplane-mode check, UI stats XML parsing, and screenshots.
              `--gating-mode all|flagged-only|both` sets the app's flagged-only gating per pass
              (debug APK launch extra) and reads the app's per-check `PrahariPerf` logcat record:
              detector ms, prompt tokens, prefill ms and tok/s, TTFT, decode tok/s, total and
              whether Llama was skipped.
  parse-dir - Parse an existing Android RTL/adb capture directory (e.g., `*-stats.xml`, `device.txt`,
              `meminfo.txt`) into standardized `results.json`, `items.csv`, and `summary.md`.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import threading
import time

PKG = "in.prahari.app"
ACTIVITY = f"{PKG}/.MainActivity"
DEVICE_FILES_DIR = f"/sdcard/Android/data/{PKG}/files"
EXPECTED_PTE_NAME = "Llama-3.2-1B-Instruct-QLORA_INT4_EO8.pte"
EXPECTED_TOK_NAME = "tokenizer.model"
EXPECTED_PTE_SHA256 = "ab7b7ebf97421c7770ad97d4abfdf8650a7d9f9dc1ce9a0c4663d49f7b7a08ac"
EXPECTED_TOK_SHA256 = "82e9d31979e92ab929cd544440f129d9ecd797b69e327f80f17e1c50d5551b55"

# MainActivity.kt: debug-only launch extra and the logcat tag of its per-check JSON record.
GATING_EXTRA = "in.prahari.app.extra.GATING"
PERF_TAG = "PrahariPerf"

# Built-in sample chips in MainActivity.kt (`samples` list)
DEFAULT_SAMPLES = [
    ("kyc-cold", "KYC scam SMS", False),
    ("kyc-warm-1", "KYC scam SMS", False),
    ("kyc-warm-2", "KYC scam SMS", False),
    ("kyc-warm-3", "KYC scam SMS", False),
    ("bill-benign", "Bill reminder", False),
    ("bank-debit", "Bank debit alert", False),
    ("lookalike-link", "Lookalike link", False),
    ("official-link", "Official link", False),
    ("port-scan", "Port scan", False),
    ("kyc-airplane", "KYC scam SMS", True),
]

# Short matrix for the gating session (docs/perf/s23-rtl-runbook.md §5): KYC cold, KYC warm ×2 and a
# lookalike link (flagged) plus two NO RISK items, run once per gating mode, so the pair fits one short RTL reservation.
GATING_SAMPLES = [
    ("kyc-cold", "KYC scam SMS", False),
    ("kyc-warm-1", "KYC scam SMS", False),
    ("kyc-warm-2", "KYC scam SMS", False),
    ("bill-benign", "Bill reminder", False),
    ("official-link", "Official link", False),
    ("lookalike-link", "Lookalike link", False),
]

# Per-check fields that only the app's PrahariPerf record carries (None when absent).
PERF_FIELDS = ("prompt_tokens", "prefill_ms", "prefill_tps", "llama_skipped", "gating_mode_observed",
               "verdict_call_ms", "generated_tokens", "total_ms", "fallback")


def adb_cmd(serial: str | None, *args: str) -> list[str]:
    cmd = ["adb"]
    if serial:
        cmd += ["-s", serial]
    cmd.extend(args)
    return cmd


def adb_out(serial: str | None, *args: str, check: bool = True, timeout: int = 120) -> str:
    proc = subprocess.run(adb_cmd(serial, *args), capture_output=True, text=True, timeout=timeout)
    if check and proc.returncode != 0:
        raise RuntimeError(f"adb {' '.join(args)} failed (rc={proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout


def parse_meminfo(text: str) -> dict:
    """Parse `adb shell dumpsys meminfo in.prahari.app` into KiB/MiB metrics."""
    out: dict = {}
    m_tot = re.search(r"TOTAL PSS:\s*(\d+)\s+TOTAL RSS:\s*(\d+)(?:\s+TOTAL SWAP PSS:\s*(\d+))?", text)
    if m_tot:
        out["total_pss_kb"] = int(m_tot.group(1))
        out["total_rss_kb"] = int(m_tot.group(2))
        out["total_swap_pss_kb"] = int(m_tot.group(3)) if m_tot.group(3) else 0
        out["total_pss_mib"] = round(out["total_pss_kb"] / 1024.0, 1)
        out["total_rss_mib"] = round(out["total_rss_kb"] / 1024.0, 1)
    else:
        m_row = re.search(r"^\s*TOTAL\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", text, re.M)
        if m_row:
            out["total_pss_kb"] = int(m_row.group(1))
            out["private_dirty_kb"] = int(m_row.group(2))
            out["private_clean_kb"] = int(m_row.group(3))
            out["total_swap_pss_kb"] = int(m_row.group(4))
            out["total_rss_kb"] = int(m_row.group(5))
            out["total_pss_mib"] = round(out["total_pss_kb"] / 1024.0, 1)
            out["total_rss_mib"] = round(out["total_rss_kb"] / 1024.0, 1)
    m_nat = re.search(r"Native Heap:\s*(\d+)\s+(\d+)", text)
    if m_nat:
        out["native_heap_pss_kb"] = int(m_nat.group(1))
        out["native_heap_rss_kb"] = int(m_nat.group(2))
        out["native_heap_pss_mib"] = round(out["native_heap_pss_kb"] / 1024.0, 1)
    m_java = re.search(r"Java Heap:\s*(\d+)\s+(\d+)", text)
    if m_java:
        out["java_heap_pss_kb"] = int(m_java.group(1))
    m_gfx = re.search(r"Graphics:\s*(\d+)\s+(\d+)", text)
    if m_gfx:
        out["graphics_pss_kb"] = int(m_gfx.group(1))
    return out


def parse_device_txt(text: str) -> dict:
    """Parse key=value Android properties + /proc/cpuinfo snippet."""
    props: dict[str, str] = {}
    features: set[str] = set()
    cpu_parts: list[str] = []
    for line in text.splitlines():
        if "=" in line and line.startswith("ro."):
            k, v = line.split("=", 1)
            props[k.strip()] = v.strip()
        elif line.startswith("Features"):
            features.update(line.split(":", 1)[-1].split())
        elif line.startswith("CPU part"):
            part = line.split(":", 1)[-1].strip()
            if part not in cpu_parts:
                cpu_parts.append(part)
    arm_flags = sorted(features & {"asimd", "asimddp", "i8mm", "bf16", "sve", "sve2", "fphp", "asimdhp"})
    return {
        "model": props.get("ro.product.model"),
        "manufacturer": props.get("ro.product.manufacturer"),
        "android_release": props.get("ro.build.version.release"),
        "sdk": props.get("ro.build.version.sdk"),
        "abilist": props.get("ro.product.cpu.abilist"),
        "soc_model": props.get("ro.soc.model"),
        "soc_manufacturer": props.get("ro.soc.manufacturer"),
        "cpu_parts": cpu_parts,
        "isa_arm_features": arm_flags,
    }


def _duration_ms(token: str) -> float:
    """Parse the app's duration format: "N ms" below one second, "x.xx s" from one second (formatMs)."""
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(ms|s)\s*", token)
    if not m:
        raise ValueError(f"not a duration: {token!r}")
    return float(m.group(1)) * (1.0 if m.group(2) == "ms" else 1000.0)


def parse_stats_xml(xml_text: str) -> dict:
    """Extract Prahari on-device stats card metrics from a uiautomator XML dump."""
    # Extract attributes from the raw XML first, then unescape each value, so an escaped quote inside a
    # value cannot end the match early.
    texts = [html.unescape(v) for v in re.findall(r' text="([^"]*)"', xml_text)]
    descs = [html.unescape(v) for v in re.findall(r'content-desc="([^"]*)"', xml_text)]

    rec: dict = {
        "detector_ms": None,
        "first_token_ms": None,
        "decode_tps": None,
        "total_s": None,
        "app_memory_mb": None,
        "backend_line": None,
        "cpu_abi": None,
        "stats_expanded": False,
        "prompt_tokens": None,
        "prefill_ms": None,
        "prefill_tps": None,
        "llama_skipped": None,
    }

    for d in descs:
        m_skip = re.search(r"On-device stats,\s*(expanded|collapsed)\.\s*(\d+(?:\.\d+)?\s*(?:ms|s))\s*·\s*Llama skipped", d)
        if m_skip:
            rec["stats_expanded"] = m_skip.group(1) == "expanded"
            rec["detector_ms"] = _duration_ms(m_skip.group(2))
            rec["llama_skipped"] = True
        m_sum = re.search(r"On-device stats,\s*(expanded|collapsed)\.\s*(\d+(?:\.\d+)?\s*(?:ms|s))\s*·\s*(\d+(?:\.\d+)?\s*(?:ms|s))", d)
        if m_sum:
            rec["stats_expanded"] = m_sum.group(1) == "expanded"
            rec["detector_ms"] = _duration_ms(m_sum.group(2))
            rec["first_token_ms"] = _duration_ms(m_sum.group(3))

    for i, t in enumerate(texts):
        s = t.strip()
        m_pair = re.fullmatch(r"(\d+(?:\.\d+)?\s*(?:ms|s))\s*·\s*(\d+(?:\.\d+)?\s*(?:ms|s))", s)
        if m_pair and rec["detector_ms"] is None:
            rec["detector_ms"] = _duration_ms(m_pair.group(1))
            rec["first_token_ms"] = _duration_ms(m_pair.group(2))
        # Each tile is a value followed by its label. Older builds had one unlabelled speed (decode).
        nxt = texts[i + 1].strip() if i + 1 < len(texts) else ""
        m_tps = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(?:t/s|tok/s)", s)
        if m_tps:
            if nxt == "Prefill speed":
                rec["prefill_tps"] = float(m_tps.group(1))
            elif nxt == "Decode speed" or rec["decode_tps"] is None:
                rec["decode_tps"] = float(m_tps.group(1))
        if nxt == "Prompt tokens" and re.fullmatch(r"\d+", s):
            rec["prompt_tokens"] = int(s)
        if nxt == "Prefill" and re.fullmatch(r"\d+(?:\.\d+)?\s*(?:ms|s)", s):
            rec["prefill_ms"] = _duration_ms(s)
        if s.startswith("Llama skipped:"):
            rec["llama_skipped"] = True
        m_tot = re.search(r"Total\s+(\d+(?:\.\d+)?\s*(?:ms|s))\s*·\s*Memory\s+(\d+(?:\.\d+)?)\s*MB", s)
        if m_tot:
            rec["total_s"] = round(_duration_ms(m_tot.group(1)) / 1000.0, 3)
            rec["app_memory_mb"] = float(m_tot.group(2))
            rec["stats_expanded"] = True
        m_be = re.search(r"(Llama[^\n]+ExecuTorch[^\n]+)", s)
        if m_be:
            rec["backend_line"] = m_be.group(1).strip()
        m_abi = re.search(r"CPU ABI:\s*([a-zA-Z0-9_-]+)", s)
        if m_abi:
            rec["cpu_abi"] = m_abi.group(1)
        if s == "Detector" and i > 0 and rec["detector_ms"] is None:
            m_d = re.fullmatch(r"\d+(?:\.\d+)?\s*(?:ms|s)", texts[i - 1].strip())
            if m_d:
                rec["detector_ms"] = _duration_ms(m_d.group(0))
        if s == "First token" and i > 0 and rec["first_token_ms"] is None:
            m_f = re.fullmatch(r"\d+(?:\.\d+)?\s*(?:ms|s)", texts[i - 1].strip())
            if m_f:
                rec["first_token_ms"] = _duration_ms(m_f.group(0))

    return rec


def parse_battery(text: str) -> dict:
    out: dict = {}
    m_lvl = re.search(r"level:\s*(\d+)", text)
    if m_lvl:
        out["level_pct"] = int(m_lvl.group(1))
    m_tmp = re.search(r"temperature:\s*(\d+)", text)
    if m_tmp:
        out["temp_c"] = round(int(m_tmp.group(1)) / 10.0, 1)
    return out


class MemPoller:
    """Background thread sampling `dumpsys meminfo in.prahari.app`; reports the highest sampled PSS/RSS."""

    def __init__(self, serial: str | None, interval_s: float = 0.5):
        self.serial = serial
        self.interval_s = interval_s
        self.samples: list[dict] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                raw = adb_out(self.serial, "shell", "dumpsys", "meminfo", PKG, check=False, timeout=10)
                parsed = parse_meminfo(raw)
                if parsed.get("total_pss_kb"):
                    parsed["t_monotonic"] = round(time.monotonic(), 3)
                    self.samples.append(parsed)
            except Exception:
                pass
            self._stop.wait(self.interval_s)

    def stop(self) -> dict:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        if not self.samples:
            return {"samples": 0, "peak_pss_mib": None, "peak_rss_mib": None}
        return {
            "samples": len(self.samples),
            "peak_pss_mib": max(s["total_pss_mib"] for s in self.samples if s.get("total_pss_mib") is not None),
            "peak_rss_mib": max(s["total_rss_mib"] for s in self.samples if s.get("total_rss_mib") is not None),
            "peak_native_pss_mib": max(
                (s["native_heap_pss_mib"] for s in self.samples if s.get("native_heap_pss_mib") is not None),
                default=None,
            ),
        }


def dump_ui_xml(serial: str | None) -> str:
    # Remove the previous dump first so a failed `uiautomator dump` cannot return the last screen.
    # uiautomator can fail transiently ("could not get idle state") while text is streaming, so retry.
    for _ in range(3):
        adb_out(serial, "shell", "rm", "-f", "/sdcard/prahari_ui.xml", check=False, timeout=20)
        adb_out(serial, "shell", "uiautomator", "dump", "/sdcard/prahari_ui.xml", check=False, timeout=20)
        out = adb_out(serial, "shell", "cat", "/sdcard/prahari_ui.xml", check=False, timeout=20)
        if "<hierarchy" in out:
            return out
        time.sleep(0.5)
    raise RuntimeError("uiautomator dump produced no hierarchy after 3 tries")


def find_bounds_center(xml_text: str, *, text_contains: str | None = None, desc_contains: str | None = None) -> tuple[int, int] | None:
    for node in re.finditer(r"<node\b[^>]+>", xml_text):
        tag = node.group(0)
        if text_contains:
            m_t = re.search(r'text="([^"]*)"', tag)
            if not m_t or text_contains.lower() not in m_t.group(1).lower():
                continue
        if desc_contains:
            m_d = re.search(r'content-desc="([^"]*)"', tag)
            if not m_d or desc_contains.lower() not in m_d.group(1).lower():
                continue
        m_b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', tag)
        if m_b:
            x1, y1, x2, y2 = map(int, m_b.groups())
            return (x1 + x2) // 2, (y1 + y2) // 2
    return None


def tap_element(serial: str | None, xml_text: str, *, text_contains: str | None = None, desc_contains: str | None = None) -> bool:
    pt = find_bounds_center(xml_text, text_contains=text_contains, desc_contains=desc_contains)
    if not pt:
        return False
    adb_out(serial, "shell", "input", "tap", str(pt[0]), str(pt[1]))
    return True


def cmd_probe(args: argparse.Namespace) -> int:
    serial = args.serial
    props = []
    for prop in (
        "ro.product.model", "ro.product.manufacturer", "ro.build.version.release",
        "ro.build.version.sdk", "ro.product.cpu.abilist", "ro.soc.model", "ro.soc.manufacturer",
    ):
        val = adb_out(serial, "shell", "getprop", prop).strip()
        props.append(f"{prop}={val}")
    cpuinfo = adb_out(serial, "shell", "head", "-n", "60", "/proc/cpuinfo", check=False)
    device_raw = "\n".join(props) + "\n" + cpuinfo
    dev = parse_device_txt(device_raw)
    mem_total = adb_out(serial, "shell", "grep", "-m1", "MemTotal", "/proc/meminfo", check=False).strip()
    batt = parse_battery(adb_out(serial, "shell", "dumpsys", "battery", check=False))
    sha_out = adb_out(
        serial, "shell", "sha256sum",
        f"{DEVICE_FILES_DIR}/{EXPECTED_PTE_NAME}", f"{DEVICE_FILES_DIR}/{EXPECTED_TOK_NAME}",
        check=False,
    ).strip()
    pkg_perms = adb_out(serial, "shell", "dumpsys", "package", PKG, check=False)
    has_internet = "android.permission.INTERNET" in pkg_perms
    result = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "serial": serial,
        "device": dev,
        "mem_total_line": mem_total,
        "battery": batt,
        "package_installed": f"Package [{PKG}]" in pkg_perms,
        "internet_permission_declared": has_internet,
        "model_sha256_raw": sha_out,
        "pte_hash_ok": EXPECTED_PTE_SHA256 in sha_out,
        "tokenizer_hash_ok": EXPECTED_TOK_SHA256 in sha_out,
    }
    if args.out_dir:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        (args.out_dir / "device.txt").write_text(device_raw, encoding="utf-8")
        (args.out_dir / "probe.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


def cmd_stage(args: argparse.Namespace) -> int:
    serial = args.serial
    if not args.apk.is_file():
        raise SystemExit(f"APK not found: {args.apk}")
    if not args.pte.is_file():
        raise SystemExit(f"PTE not found: {args.pte}")
    if not args.tokenizer.is_file():
        raise SystemExit(f"Tokenizer not found: {args.tokenizer}")

    print("[adb_bench] installing APK...", flush=True)
    adb_out(serial, "install", "-r", str(args.apk), timeout=180)
    pkg_perms = adb_out(serial, "shell", "dumpsys", "package", PKG)
    if "android.permission.INTERNET" in pkg_perms:
        raise SystemExit("FAIL: installed APK declares android.permission.INTERNET")
    print("[adb_bench] verified: no INTERNET permission declared", flush=True)

    adb_out(serial, "shell", "am", "start", "-n", ACTIVITY)
    time.sleep(2)
    adb_out(serial, "shell", "mkdir", "-p", DEVICE_FILES_DIR)

    t0 = time.monotonic()
    print(f"[adb_bench] pushing PTE ({args.pte.stat().st_size / (1024**3):.3f} GiB)...", flush=True)
    adb_out(serial, "push", str(args.pte), f"{DEVICE_FILES_DIR}/{EXPECTED_PTE_NAME}", timeout=600)
    pte_push_s = round(time.monotonic() - t0, 1)

    adb_out(serial, "push", str(args.tokenizer), f"{DEVICE_FILES_DIR}/{EXPECTED_TOK_NAME}", timeout=120)
    sha_out = adb_out(
        serial, "shell", "sha256sum",
        f"{DEVICE_FILES_DIR}/{EXPECTED_PTE_NAME}", f"{DEVICE_FILES_DIR}/{EXPECTED_TOK_NAME}",
        timeout=180,
    ).strip()
    print(sha_out, flush=True)
    if not args.skip_hash_check:
        if EXPECTED_PTE_SHA256 not in sha_out or EXPECTED_TOK_SHA256 not in sha_out:
            raise SystemExit("FAIL: device-side SHA-256 mismatch for PTE or tokenizer")
    print(f"[adb_bench] staged and verified in {pte_push_s}s", flush=True)
    return 0


def _median(vals: list, ndigits: int):
    vals = [v for v in vals if v is not None]
    return round(statistics.median(vals), ndigits) if vals else None


def summarize_android(device: dict, rows: list[dict], meminfo: dict | None = None, source_note: str = "",
                      chronological: bool = True) -> dict:
    all_rows = rows
    # Aggregates use completed checks only; timed-out or skipped checks stay listed under "checks".
    rows = [r for r in all_rows if r.get("status") == "ok"]
    det_vals = [r["detector_ms"] for r in rows if r.get("detector_ms") is not None]
    ttft_vals = [r["first_token_ms"] for r in rows if r.get("first_token_ms") is not None]
    dec_vals = [r["decode_tps"] for r in rows if r.get("decode_tps") is not None]
    tot_vals = [r["total_s"] for r in rows if r.get("total_s") is not None]
    mem_vals = [r["app_memory_mb"] for r in rows if r.get("app_memory_mb") is not None]
    # Warm KYC medians stay comparable with run 8: Llama on for every check (no gating, or "all").
    warm_kyc = [r for r in rows if "warm" in r.get("check", "").lower() and r.get("gating_mode") in (None, "all")]
    warm_ttft = [r["first_token_ms"] for r in warm_kyc if r.get("first_token_ms") is not None]
    return {
        "schema": "prahari-android-bench-v1",
        "device_class": "android-arm64",
        "source_note": source_note,
        "device": device,
        "dumpsys_meminfo": meminfo or {},
        "summary": {
            "checks_total": len(all_rows),
            "checks_incomplete": [r.get("check") for r in all_rows if r.get("status") != "ok"],
            "checks_full_stats": sum(1 for r in rows if r.get("decode_tps") is not None and r.get("total_s") is not None),
            "detector_ms_min_max": [min(det_vals), max(det_vals)] if det_vals else None,
            "ttft_ms_median": round(statistics.median(ttft_vals), 1) if ttft_vals else None,
            "ttft_ms_min_max": [min(ttft_vals), max(ttft_vals)] if ttft_vals else None,
            "decode_tps_median": round(statistics.median(dec_vals), 1) if dec_vals else None,
            "decode_tps_min_max": [min(dec_vals), max(dec_vals)] if dec_vals else None,
            "total_s_median": round(statistics.median(tot_vals), 2) if tot_vals else None,
            "total_s_min_max": [min(tot_vals), max(tot_vals)] if tot_vals else None,
            "app_pss_mb_min_max": [min(mem_vals), max(mem_vals)] if mem_vals else None,
            # Growth needs rows in run order; parse-dir only knows file names, so it reports None.
            "app_pss_growth_mb": (round(mem_vals[-1] - mem_vals[0], 1) if len(mem_vals) >= 2 else 0.0) if chronological else None,
            "warm_kyc_ttft_ms_median": round(statistics.median(warm_ttft), 1) if warm_ttft else None,
            "warm_kyc_decode_tps_median": _median([r.get("decode_tps") for r in warm_kyc], 1),
            "warm_kyc_total_s_median": _median([r.get("total_s") for r in warm_kyc], 2),
            "prompt_tokens_median": _median([r.get("prompt_tokens") for r in rows], 0),
            "prefill_ms_median": _median([r.get("prefill_ms") for r in rows], 1),
            "prefill_tps_median": _median([r.get("prefill_tps") for r in rows], 1),
            "by_gating_mode": _gating_summary(rows),
        },
        "checks": all_rows,
    }


def _gating_summary(rows: list[dict]) -> dict:
    """Per gating mode: checks, how many skipped Llama, and median totals for each group.

    Only rows whose app record confirmed the requested mode count. An older APK writes no record and
    ignores the launch extra, so its rows (status ok, gating_mode_observed None) are counted under
    `unconfirmed` and never as a gating comparison.
    """
    out: dict = {}
    unconfirmed = [r for r in rows if r.get("gating_mode") and r.get("gating_mode_observed") != r.get("gating_mode")]
    if unconfirmed:
        out["unconfirmed"] = {"checks": len(unconfirmed)}
    for mode in sorted({r.get("gating_mode") for r in rows if r.get("gating_mode")}):
        group = [r for r in rows if r.get("gating_mode") == mode and r.get("gating_mode_observed") == mode]
        if not group:
            continue
        skipped = [r for r in group if r.get("llama_skipped")]
        ran = [r for r in group if not r.get("llama_skipped")]
        out[mode] = {
            "checks": len(group),
            "llama_skipped": len(skipped),
            "total_s_median_skipped": _median([r.get("total_s") for r in skipped], 3),
            "total_s_median_llama": _median([r.get("total_s") for r in ran], 3),
            "detector_ms_median": _median([r.get("detector_ms") for r in group], 1),
        }
    return out


def render_android_md(report: dict) -> str:
    dev = report.get("device", {})
    lines = [
        "# Prahari Android Device Benchmark Summary",
        "",
        f"- **Device:** `{dev.get('manufacturer')} {dev.get('model')}` (SoC `{dev.get('soc_model')}`, Android `{dev.get('android_release')}`, ABI `{dev.get('abilist')}`)",
        f"- **Arm ISA flags:** `{', '.join(dev.get('isa_arm_features') or []) or 'n/a'}`",
    ]
    if report.get("source_note"):
        lines.append(f"- **Source:** {report['source_note']}")
    mem = report.get("dumpsys_meminfo") or {}
    if mem.get("total_pss_kb"):
        lines.append(
            f"- **dumpsys meminfo snapshot:** TOTAL PSS `{mem['total_pss_kb']:,} KiB` ({mem['total_pss_mib']} MiB), "
            f"TOTAL RSS `{mem['total_rss_kb']:,} KiB` ({mem['total_rss_mib']} MiB), "
            f"Native Heap PSS `{mem.get('native_heap_pss_kb', 0):,} KiB`"
        )
    lines += [
        "",
        "| Check | Status | Airplane | Gating | Llama skipped | Detector (ms) | Prompt tokens | Prefill (ms) | Prefill (tok/s) | TTFT (ms) | Decode (tok/s) | Total (s) | App PSS after check (MB) | Highest sampled PSS (MiB) |",
        "|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    def cell(v):
        return "—" if v is None else ("yes" if v is True else "no" if v is False else v)
    for r in report["checks"]:
        polled = r.get("mem_polled", {}).get("peak_pss_mib")
        lines.append(
            f"| `{r['check']}` | {r.get('status', 'unknown')} | {'yes' if r.get('airplane_mode') else 'no'} | "
            f"{cell(r.get('gating_mode'))} | {cell(r.get('llama_skipped'))} | "
            f"{r['detector_ms'] if r['detector_ms'] is not None else '—'} | "
            f"{cell(r.get('prompt_tokens'))} | {cell(r.get('prefill_ms'))} | {cell(r.get('prefill_tps'))} | "
            f"{r['first_token_ms'] if r['first_token_ms'] is not None else '—'} | "
            f"{r['decode_tps'] if r['decode_tps'] is not None else '—'} | "
            f"{r['total_s'] if r['total_s'] is not None else '—'} | "
            f"{r['app_memory_mb'] if r['app_memory_mb'] is not None else '—'} | "
            f"{polled if polled is not None else '—'} |"
        )
    by_mode = (report.get("summary") or {}).get("by_gating_mode") or {}
    if by_mode:
        lines += ["", "| Gating | Checks | Llama skipped | Median total, skipped (s) | Median total, Llama ran (s) |",
                  "|---|---:|---:|---:|---:|"]
        for mode, g in by_mode.items():
            if mode == "unconfirmed":
                lines.append(f"| unconfirmed (no app record; not a gating result) | {g['checks']} | — | — | — |")
                continue
            lines.append(f"| `{mode}` | {g['checks']} | {g['llama_skipped']} | {cell(g['total_s_median_skipped'])} | "
                         f"{cell(g['total_s_median_llama'])} |")
    return "\n".join(lines) + "\n"


def write_android_outputs(report: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (out_dir / "summary.md").write_text(render_android_md(report), encoding="utf-8")
    fields = [
        "check", "status", "airplane_mode", "detector_ms", "first_token_ms", "decode_tps",
        "total_s", "app_memory_mb", "polled_peak_pss_mib", "polled_peak_rss_mib", "cpu_abi",
        "gating_mode", "gating_mode_observed", "llama_skipped", "prompt_tokens", "prefill_ms", "prefill_tps",
    ]
    with (out_dir / "items.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in report["checks"]:
            mp = r.get("mem_polled") or {}
            w.writerow({
                "check": r["check"],
                "status": r.get("status", "unknown"),
                "airplane_mode": bool(r.get("airplane_mode")),
                "detector_ms": r.get("detector_ms"),
                "first_token_ms": r.get("first_token_ms"),
                "decode_tps": r.get("decode_tps"),
                "total_s": r.get("total_s"),
                "app_memory_mb": r.get("app_memory_mb"),
                "polled_peak_pss_mib": mp.get("peak_pss_mib"),
                "polled_peak_rss_mib": mp.get("peak_rss_mib"),
                "cpu_abi": r.get("cpu_abi"),
                "gating_mode": r.get("gating_mode"),
                "gating_mode_observed": r.get("gating_mode_observed"),
                "llama_skipped": r.get("llama_skipped"),
                "prompt_tokens": r.get("prompt_tokens"),
                "prefill_ms": r.get("prefill_ms"),
                "prefill_tps": r.get("prefill_tps"),
            })


def cmd_parse_dir(args: argparse.Namespace) -> int:
    src = args.capture_dir.resolve()
    dev = parse_device_txt((src / "device.txt").read_text(errors="replace")) if (src / "device.txt").is_file() else {}
    mem = parse_meminfo((src / "meminfo.txt").read_text(errors="replace")) if (src / "meminfo.txt").is_file() else {}
    xml_files = sorted(src.glob("*-stats.xml"))
    if not xml_files:
        raise SystemExit(f"No *-stats.xml files found in {src}")
    # A live `run` records each check's status in results.json; keep it, so a timed-out check whose XML
    # happens to hold late values is not promoted to a completed one when the captures are reparsed.
    recorded: dict[str, str] = {}
    live: dict[str, dict] = {}
    prior = src / "results.json"
    if prior.is_file():
        try:
            prior_rows = json.loads(prior.read_text()).get("checks", [])
            # Only explicit statuses count; rows from older reports without one are judged from their XML.
            recorded = {c["check"]: c["status"] for c in prior_rows if c.get("status")}
            live = {c["check"]: c for c in prior_rows if c.get("check")}
        except (ValueError, KeyError, TypeError, AttributeError):
            recorded, live = {}, {}
    rows = []
    for xf in xml_files:
        name = xf.name.removesuffix("-stats.xml")
        xml_text = xf.read_text(errors="replace")
        rec = parse_stats_xml(xml_text)
        rec["check"] = name
        rec["airplane_mode"] = "airplane" in name.lower()
        # Without a recorded status, count a check as complete only if its stats header carries a first-token time.
        rec["status"] = recorded.get(name) or ("ok" if stats_header_state(xml_text) == "done" else "incomplete-capture")
        # The UI text cannot show the requested gating mode or the app's own PrahariPerf numbers; keep
        # them from the live run's row, so reparsing a gating capture does not lose them.
        prev = live.get(name) or {}
        for key in ("gating_mode",) + PERF_FIELDS + ("detector_ms", "first_token_ms", "decode_tps", "total_s",
                                                     "app_memory_mb", "mem_polled", "perf_error", "fallback"):
            if prev.get(key) is not None:
                rec[key] = prev[key]
        rows.append(rec)
    # Checks the live run recorded as failed before any XML was written still belong in the report.
    seen = {r["check"] for r in rows}
    for name, status in recorded.items():
        if name not in seen:
            rows.append({"check": name, "status": status, "airplane_mode": "airplane" in name.lower(),
                         "detector_ms": None, "first_token_ms": None, "decode_tps": None, "total_s": None,
                         "app_memory_mb": None, "mem_polled": {}})
    report = summarize_android(dev, rows, mem, source_note=f"Parsed UI XML artifacts from {src}", chronological=False)
    if args.out_dir:
        write_android_outputs(report, args.out_dir.resolve())
    print(render_android_md(report))
    return 0


# The main action button. Match its accessibility label, not any text containing "Check": the app header
# subtitle ("... scam & threat check") and "Check for the model files" would otherwise match first.
CHECK_BUTTON_DESC = "Check on this phone"
# The stats header's accessibility label is "On-device stats, <state>. <detector> · <first token>". The app
# fills it twice: once when the verdict appears (first token "—") and again when Llama has finished.
_STATS_DESC_RE = re.compile(r'content-desc="On-device stats, (?:collapsed|expanded)\. ([^"]*?) · ([^"]*)"')


# Sample chips are labelled "<name>, SMS sample" in older builds and "<name>, SMS" in the round-3 app.
_SAMPLE_CHIP_RE = re.compile(r'<node\b[^>]*content-desc="[^"]*, (?:SMS|Link|Network)(?: sample)?"[^>]*>')


def sample_row_y(xml_text: str) -> int | None:
    """Vertical centre of the "Try a sample" chip row, from any visible chip's bounds."""
    m = _SAMPLE_CHIP_RE.search(xml_text)
    if not m:
        return None
    b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', m.group(0))
    return (int(b.group(2)) + int(b.group(4))) // 2 if b else None


def stats_header_state(xml_text: str) -> str:
    """'absent' (header not on screen), 'pending' (Llama still running), 'fallback' (the stage ended
    with the detector's fixed text instead of Llama's reply: "Detector text"), 'no-ai-text' (it ended
    with no explanation: missing model or an error) or 'done'."""
    m = _STATS_DESC_RE.search(xml_text)
    if not m:
        return "absent"
    first_token = m.group(2).strip()
    if first_token == "Detector text":
        return "fallback"
    if first_token == "No AI text":
        return "no-ai-text"
    return "pending" if (not first_token or first_token.startswith("—") or first_token == "…") else "done"


def parse_perf_lines(text: str) -> list[dict]:
    """PrahariPerf JSON records from `logcat -v raw` output (other lines and bad JSON are skipped)."""
    out = []
    for line in text.splitlines():
        start = line.find("{")
        if start < 0:
            continue
        try:
            rec = json.loads(line[start:])
        except ValueError:
            continue
        if isinstance(rec, dict) and "session" in rec and "seq" in rec and "event" in rec:
            out.append(rec)
    return out


def read_perf(serial: str | None) -> list[dict]:
    """Every PrahariPerf record still in the device log. Never clears logcat (other apps share it)."""
    try:
        raw = adb_out(serial, "logcat", "-d", "-v", "raw", "-s", f"{PERF_TAG}:I", check=False, timeout=30)
    except Exception:
        return []
    return parse_perf_lines(raw)


def _perf_key(rec: dict) -> tuple:
    return (str(rec.get("session")), rec.get("seq"))


def new_perf_record(before: list[dict], after: list[dict], event: str) -> dict | None:
    """The newest `event` record in `after` that was not already in `before`.

    Records are keyed by (process session, sequence), so a restarted app (sequence back at 1) and
    records left from an earlier pass are told apart.
    """
    seen = {_perf_key(r) for r in before}
    fresh = [r for r in after if r.get("event") == event and _perf_key(r) not in seen]
    return fresh[-1] if fresh else None


def merge_perf(rec: dict, perf: dict | None) -> None:
    """Fill a check row from the app's record; the record wins over UI text for the fields it has."""
    for key in PERF_FIELDS:
        rec.setdefault(key, None)
    if not perf:
        return
    rec["gating_mode_observed"] = perf.get("gating")
    rec["llama_skipped"] = bool(perf.get("llama_skipped"))
    rec["perf_error"] = bool(perf.get("error"))
    rec["fallback"] = perf.get("fallback")
    for key in ("detector_ms", "first_token_ms", "decode_tps", "prompt_tokens", "prefill_ms", "prefill_tps",
                "verdict_call_ms", "generated_tokens", "total_ms"):
        val = perf.get(key)
        if val is not None:
            rec[key] = round(float(val), 3) if key not in ("prompt_tokens", "generated_tokens") else int(val)
    if perf.get("total_ms") is not None:
        rec["total_s"] = round(float(perf["total_ms"]) / 1000.0, 3)
    if perf.get("pss_mb") is not None:
        rec["app_memory_mb"] = round(float(perf["pss_mb"]), 1)


def launch_app(serial: str | None, gating: str | None, model_timeout_s: float, settle_s: float,
               until: float | None = None) -> dict:
    """Restart the app (optionally with a gating mode) and wait for its model-preload record.

    `until` (a time.monotonic() value) also ends the wait, so a launch near the run deadline does not
    poll past it.
    """
    before = read_perf(serial)
    adb_out(serial, "shell", "am", "force-stop", PKG, check=False)
    cmd = ["shell", "am", "start", "-n", ACTIVITY]
    if gating:
        cmd += ["--es", GATING_EXTRA, gating]
    adb_out(serial, *cmd)
    model = None
    if gating:
        # About one poll a second; counted in polls, not wall time, so a stalled adb cannot loop forever.
        for _ in range(max(1, int(model_timeout_s))):
            if until is not None and time.monotonic() >= until:
                break
            time.sleep(1.0)
            model = new_perf_record(before, read_perf(serial), "model")
            if model:
                break
    # Without a gating request (or with an older APK that writes no record) keep the fixed settle time.
    time.sleep(settle_s if model is None else 1.0)
    return {"gating_requested": gating, "model_event": model}


def _set_airplane(serial: str | None, enabled: bool) -> str:
    mode = "enable" if enabled else "disable"
    adb_out(serial, "shell", "cmd", "connectivity", "airplane-mode", mode, check=False)
    time.sleep(2)
    return adb_out(serial, "shell", "settings", "get", "global", "airplane_mode_on", check=False).strip()


def cmd_run(args: argparse.Namespace) -> int:
    serial = args.serial
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_dir = (args.out_dir or Path(f"/var/tmp/prahari-perf-android-{stamp}")).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Probe device first
    props = [f"{p}={adb_out(serial, 'shell', 'getprop', p).strip()}" for p in (
        "ro.product.model", "ro.product.manufacturer", "ro.build.version.release",
        "ro.build.version.sdk", "ro.product.cpu.abilist", "ro.soc.model", "ro.soc.manufacturer",
    )]
    cpuinfo = adb_out(serial, "shell", "head", "-n", "60", "/proc/cpuinfo", check=False)
    dev_raw = "\n".join(props) + "\n" + cpuinfo
    (out_dir / "device.txt").write_text(dev_raw, encoding="utf-8")
    dev = parse_device_txt(dev_raw)

    run_start = time.monotonic()
    modes: list[str | None] = {"app-default": [None], "both": ["all", "flagged-only"]}.get(
        args.gating_mode, [args.gating_mode])
    samples = GATING_SAMPLES if args.samples == "gating" else DEFAULT_SAMPLES
    passes: list[dict] = []
    launch_failed: set = set()
    pass_has_telemetry = {"v": False}

    rows = []
    airplane_active = False

    active_poller: dict = {"p": None}

    def blank_row(check_id: str, sample_label: str, status: str, airplane: bool, gating: str | None) -> dict:
        row = {"check": check_id, "sample_label": sample_label, "status": status, "airplane_mode": airplane,
               "gating_mode": gating, "detector_ms": None, "first_token_ms": None, "decode_tps": None,
               "total_s": None, "app_memory_mb": None, "mem_polled": {}}
        merge_perf(row, None)
        return row

    def one_check(check_id: str, sample_label: str, want_airplane: bool, gating: str | None = None) -> None:
        nonlocal airplane_active
        if want_airplane and not args.with_airplane:
            return
        observed_airplane = None
        if want_airplane != airplane_active:
            observed_airplane = _set_airplane(serial, want_airplane)
            airplane_active = want_airplane
            print(f"[adb_bench] airplane_mode_on={observed_airplane}", flush=True)
        if want_airplane:
            observed_airplane = observed_airplane or adb_out(
                serial, "shell", "settings", "get", "global", "airplane_mode_on", check=False).strip()
            if observed_airplane != "1":
                print(f"[adb_bench] ERROR: airplane mode requested but device reports airplane_mode_on={observed_airplane!r}; "
                      f"skipping {check_id} rather than recording a false offline result", file=sys.stderr)
                rows.append({"check": check_id, "sample_label": sample_label, "status": "airplane-not-confirmed",
                             "airplane_mode": False, "airplane_mode_on_observed": observed_airplane,
                             "detector_ms": None, "first_token_ms": None, "decode_tps": None,
                             "total_s": None, "app_memory_mb": None, "mem_polled": {}})
                return

        batt_before = parse_battery(adb_out(serial, "shell", "dumpsys", "battery", check=False))
        xml = dump_ui_xml(serial)
        found = tap_element(serial, xml, desc_contains=f"{sample_label}, ")
        for _ in range(9):  # nine sample chips on main; Bank debit alert is last
            if found:
                break
            # Step the horizontal sample-chip row left along its own y (read from the dump). A slow drag
            # (1.5 s) moves it by about the swipe distance; a fast swipe would fling it past middle chips.
            row_y = sample_row_y(xml)
            if row_y is None:
                break
            adb_out(serial, "shell", "input", "swipe", "900", str(row_y), "400", str(row_y), "1500")
            time.sleep(0.6)
            xml = dump_ui_xml(serial)
            found = tap_element(serial, xml, desc_contains=f"{sample_label}, ")
        if not found:
            print(f"[adb_bench] ERROR: sample chip {sample_label!r} not found; skipping {check_id}", file=sys.stderr)
            rows.append({"check": check_id, "sample_label": sample_label, "status": "no-sample-chip",
                         "airplane_mode": want_airplane, "detector_ms": None, "first_token_ms": None,
                         "decode_tps": None, "total_s": None, "app_memory_mb": None, "mem_polled": {}})
            return
        time.sleep(0.5)
        xml = dump_ui_xml(serial)

        if not find_bounds_center(xml, desc_contains=CHECK_BUTTON_DESC):
            print(f"[adb_bench] ERROR: {CHECK_BUTTON_DESC!r} button not on screen; skipping {check_id}", file=sys.stderr)
            rows.append({"check": check_id, "sample_label": sample_label, "status": "no-check-button",
                         "airplane_mode": want_airplane, "detector_ms": None, "first_token_ms": None,
                         "decode_tps": None, "total_s": None, "app_memory_mb": None, "mem_polled": {}})
            return
        if out_of_time():
            # Chip search and UI dumps can cross the deadline; do not start a check past it.
            rows.append(blank_row(check_id, sample_label, "skipped-deadline", want_airplane, gating))
            return
        perf_before = read_perf(serial)
        if out_of_time():  # the log read itself can take a while
            rows.append(blank_row(check_id, sample_label, "skipped-deadline", want_airplane, gating))
            return
        poller = MemPoller(serial, interval_s=args.mem_poll_ms / 1000.0)
        active_poller["p"] = poller
        poller.start()
        t0 = time.monotonic()
        tap_element(serial, xml, desc_contains=CHECK_BUTTON_DESC)

        # Wait until the stats header reports a first-token time, i.e. Llama has finished. The header sits
        # below the fold on the result screen, so scroll down whenever it is not in the dump.
        deadline = time.monotonic() + args.check_timeout_s
        stats_xml = ""
        state = "absent"
        while time.monotonic() < deadline:
            time.sleep(1.0)
            stats_xml = dump_ui_xml(serial)
            state = stats_header_state(stats_xml)
            if state in ("done", "fallback", "no-ai-text"):
                break
            if state == "absent" and "Check another" in stats_xml:
                adb_out(serial, "shell", "input", "swipe", "540", "1600", "540", "500", "300")
        wall_s = round(time.monotonic() - t0, 2)
        polled = poller.stop()
        active_poller["p"] = None
        # A fallback check finished, but without Llama timing: keep it out of the completed aggregates.
        status = {"done": "ok", "fallback": "detector-fallback", "no-ai-text": "explanation-error"}.get(state, "timeout")
        if status == "detector-fallback":
            print(f"[adb_bench] WARNING: {check_id} finished with the detector's fixed text (no usable Llama reply)",
                  file=sys.stderr)
        elif status == "explanation-error":
            print(f"[adb_bench] ERROR: {check_id} finished with no explanation (missing model or an error)",
                  file=sys.stderr)
        elif status != "ok":
            print(f"[adb_bench] ERROR: {check_id} did not finish within {args.check_timeout_s:.0f} s "
                  f"(stats header state: {state}); its numbers are incomplete", file=sys.stderr)

        # Scroll down and expand stats card if collapsed
        adb_out(serial, "shell", "input", "swipe", "540", "1600", "540", "500", "300")
        time.sleep(0.5)
        stats_xml = dump_ui_xml(serial)
        if "On-device stats, collapsed" in stats_xml:
            tap_element(serial, stats_xml, desc_contains="On-device stats, collapsed")
            time.sleep(0.5)
            stats_xml = dump_ui_xml(serial)

        (out_dir / f"{check_id}-stats.xml").write_text(stats_xml, encoding="utf-8")
        png_bytes = subprocess.check_output(adb_cmd(serial, "exec-out", "screencap", "-p"), timeout=20)
        (out_dir / f"{check_id}-stats.png").write_bytes(png_bytes)

        rec = parse_stats_xml(stats_xml)
        rec["check"] = check_id
        rec["sample_label"] = sample_label
        rec["gating_mode"] = gating
        perf = new_perf_record(perf_before, read_perf(serial), "result")
        merge_perf(rec, perf)
        if status == "ok" and gating:
            # Any record present must report the requested mode. A missing record fails the check only
            # when this pass has shown the app writes records (preload record or an earlier result);
            # an older APK writes none and ignores the launch extra, so its rows keep status ok with
            # gating_mode_observed None.
            if perf is not None:
                pass_has_telemetry["v"] = True
                if perf.get("gating") != gating:
                    status = "gating-mismatch"
            elif pass_has_telemetry["v"]:
                status = "telemetry-missing"
            if status != "ok":
                print(f"[adb_bench] ERROR: {check_id}: {status} (requested {gating}, "
                      f"record {perf.get('gating') if perf else None})", file=sys.stderr)
        rec["status"] = status
        rec["airplane_mode"] = want_airplane
        if want_airplane:
            rec["airplane_mode_on_observed"] = observed_airplane
        rec["host_observed_wall_s"] = wall_s
        rec["mem_polled"] = polled
        rec["battery_before"] = batt_before
        rec["battery_after"] = parse_battery(adb_out(serial, "shell", "dumpsys", "battery", check=False))
        rows.append(rec)
        print(
            f"[adb_bench] {check_id}: gating={gating} skipped={rec.get('llama_skipped')} det={rec['detector_ms']}ms "
            f"prompt={rec.get('prompt_tokens')}tok prefill={rec.get('prefill_ms')}ms/{rec.get('prefill_tps')}tok/s "
            f"ttft={rec['first_token_ms']}ms "
            f"decode={rec['decode_tps']}tok/s total={rec['total_s']}s pss={rec['app_memory_mb']}MB "
            f"polled_peak_pss={polled.get('peak_pss_mib')}MiB",
            flush=True,
        )

        # Return to home screen
        if not tap_element(serial, stats_xml, text_contains="Check another"):
            adb_out(serial, "shell", "input", "keyevent", "KEYCODE_BACK")
        time.sleep(1.0)

    def out_of_time() -> bool:
        return args.deadline_s > 0 and time.monotonic() - run_start > args.deadline_s

    deadline_at = run_start + args.deadline_s if args.deadline_s > 0 else None

    plan = []
    for gating in modes:
        for check_id, sample_label, want_airplane in samples:
            if want_airplane and not args.with_airplane:
                continue
            plan.append((gating, check_id + ("-gated" if gating == "flagged-only" else ""), sample_label, want_airplane))

    try:
        launched: object = object()  # sentinel: no pass launched yet
        for gating, check_id, sample_label, want_airplane in plan:
            if out_of_time():
                # Deadline reached: record what was not run instead of overrunning the reservation.
                rows.append(blank_row(check_id, sample_label, "skipped-deadline", want_airplane, gating))
                continue
            if gating != launched:
                launched = gating
                try:
                    if airplane_active:
                        _set_airplane(serial, False)
                        airplane_active = False
                    info = launch_app(serial, gating, args.model_timeout_s, args.settle_s, until=deadline_at)
                except Exception as exc:
                    # Keep the rows already measured; this pass's checks are recorded as not run.
                    print(f"[adb_bench] ERROR: launching pass gating={gating} failed: {exc}", file=sys.stderr)
                    info = {"gating_requested": gating, "model_event": None, "error": type(exc).__name__}
                    launch_failed.add(gating)
                passes.append(info)
                pass_has_telemetry["v"] = info.get("model_event") is not None
                print(f"[adb_bench] pass gating={gating} model={(info['model_event'] or {}).get('state')}", flush=True)
            if gating in launch_failed:
                rows.append(blank_row(check_id, sample_label, "launch-failed", want_airplane, gating))
                continue
            if out_of_time():
                # The launch itself crossed the deadline.
                rows.append(blank_row(check_id, sample_label, "skipped-deadline", want_airplane, gating))
                continue
            try:
                one_check(check_id, sample_label, want_airplane, gating)
            except Exception as exc:  # one adb failure must not lose the rest of the session
                print(f"[adb_bench] ERROR: {check_id} failed: {exc}", file=sys.stderr)
                if active_poller["p"] is not None:  # never leave dumpsys polling running into later checks
                    try:
                        active_poller["p"].stop()
                    except Exception:
                        pass
                    active_poller["p"] = None
                if rows and rows[-1].get("check") == check_id:
                    # The measurement was recorded; only the navigation afterwards failed.
                    rows[-1]["note"] = f"post-check navigation failed: {type(exc).__name__}"
                else:
                    rows.append(blank_row(check_id, sample_label, f"error: {type(exc).__name__}", want_airplane, gating))
                try:
                    adb_out(serial, "shell", "input", "keyevent", "KEYCODE_BACK", check=False, timeout=20)
                except Exception as nav_exc:
                    print(f"[adb_bench] ERROR: recovery BACK key failed: {nav_exc}", file=sys.stderr)
                time.sleep(1.0)

        try:
            mem_raw = adb_out(serial, "shell", "dumpsys", "meminfo", PKG, check=False)
        except Exception as exc:
            print(f"[adb_bench] ERROR: final dumpsys meminfo failed: {exc}", file=sys.stderr)
            mem_raw = ""
        (out_dir / "meminfo.txt").write_text(mem_raw, encoding="utf-8")
        report = summarize_android(dev, rows, parse_meminfo(mem_raw), source_note="Live adb benchmark run")
        report["passes"] = passes
        report["elapsed_s"] = round(time.monotonic() - run_start, 1)
        write_android_outputs(report, out_dir)
        print(render_android_md(report))
        print(f"[adb_bench] outputs written to {out_dir}")
        failed = [r["check"] for r in rows if r.get("status") != "ok"]
        if failed:
            print(f"[adb_bench] {len(failed)} check(s) incomplete: {', '.join(failed)}", file=sys.stderr)
            return 2
        return 0
    finally:
        if airplane_active:
            _set_airplane(serial, False)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Android (adb) benchmark and telemetry collector for Prahari.")
    ap.add_argument("--serial", default=os.environ.get("ANDROID_SERIAL"), help="adb serial (e.g. localhost:PORT)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_probe = sub.add_parser("probe", help="Inspect connected Android device, APK, and model hashes")
    p_probe.add_argument("--out-dir", type=Path, default=None)

    p_stage = sub.add_parser("stage", help="Install APK, audit permissions, push model & tokenizer, verify SHA-256")
    p_stage.add_argument("--apk", type=Path, required=True)
    p_stage.add_argument("--pte", type=Path, required=True)
    p_stage.add_argument("--tokenizer", type=Path, required=True)
    p_stage.add_argument("--skip-hash-check", action="store_true")

    p_run = sub.add_parser("run", help="Run automated UI checks over adb with peak memory polling")
    p_run.add_argument("--out-dir", type=Path, default=None)
    p_run.add_argument("--with-airplane", action="store_true", help="Include airplane-mode check at end")
    p_run.add_argument("--mem-poll-ms", type=int, default=500)
    p_run.add_argument("--settle-s", type=float, default=6.0, help="Seconds to wait for model preload after app launch")
    p_run.add_argument("--check-timeout-s", type=float, default=60.0)
    p_run.add_argument("--gating-mode", choices=["app-default", "all", "flagged-only", "both"], default="app-default",
                       help="Set the app's flagged-only gating per pass (debug APK); app-default leaves the setting alone")
    p_run.add_argument("--samples", choices=["default", "gating"], default="default",
                       help="default: the 10-check run-8 list; gating: 6 checks per mode for the gating session")
    p_run.add_argument("--deadline-s", type=float, default=0.0,
                       help="Stop starting checks after this many seconds (0: no limit); the rest are recorded as skipped")
    p_run.add_argument("--model-timeout-s", type=float, default=60.0,
                       help="Polls (about 1 s each) to wait for the app's model-preload record after each launch")

    p_parse = sub.add_parser("parse-dir", help="Parse an existing RTL/adb capture directory into JSON/CSV/Markdown")
    p_parse.add_argument("capture_dir", type=Path)
    p_parse.add_argument("--out-dir", type=Path, default=None)

    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.cmd == "probe":
        return cmd_probe(args)
    if args.cmd == "stage":
        return cmd_stage(args)
    if args.cmd == "run":
        return cmd_run(args)
    if args.cmd == "parse-dir":
        return cmd_parse_dir(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
