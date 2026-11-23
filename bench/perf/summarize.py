#!/usr/bin/env python3
"""Aggregate Arm Linux and Android benchmark results.json files into one comparison table."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _row_from_arm_linux(data: dict) -> list[dict]:
    cpu = data.get("host", {}).get("cpu", {})
    dev_label = cpu.get("model_name") or data.get("host", {}).get("machine", "Arm Linux")
    flags = ", ".join(cpu.get("isa_arm_features") or []) or "n/a"
    rows = []
    for cell in data.get("cells", []):
        agg = cell.get("aggregate", {})
        w_ttft = (agg.get("warm_ttft_ms_mean_std") or [None])[0]
        w_pre = (agg.get("warm_prefill_tps_mean_std") or [None])[0]
        w_dec = (agg.get("warm_decode_tps_mean_std") or [None])[0]
        w_wall = (agg.get("warm_item_wall_s_mean_std") or [None])[0]
        all_wall = (agg.get("all_item_wall_s_mean_std") or [None])[0]
        rss = agg.get("peak_rss_runner_mib_max") or agg.get("peak_rss_time_mib_max")
        rows.append({
            "device": f"{dev_label} ({cell['threads']}T)",
            "isa": flags,
            "model": cell["model"],
            "workload": f"{cell['prompt_length']} / {cell['gating_mode']}",
            "detector_ms": agg.get("detector_ms_median"),
            "warm_ttft_ms": w_ttft,
            "prefill_tps": w_pre,
            "decode_tps": w_dec,
            "per_check_s": w_wall if w_wall is not None else all_wall,
            "memory": f"{rss:.1f} MiB RSS" if rss is not None else "—",
        })
    return rows


def _row_from_android(data: dict) -> list[dict]:
    dev = data.get("device", {})
    summ = data.get("summary", {})
    mem = data.get("dumpsys_meminfo", {})
    label = f"{dev.get('manufacturer', '')} {dev.get('model', 'Android')} ({dev.get('soc_model', 'arm64')})".strip()
    flags = ", ".join(dev.get("isa_arm_features") or []) or "n/a"
    mem_str = "—"
    if mem.get("total_pss_mib"):
        mem_str = f"{mem['total_pss_mib']:.1f} MiB PSS / {mem['total_rss_mib']:.1f} MiB RSS"
    elif summ.get("app_pss_mb_min_max"):
        lo, hi = summ["app_pss_mb_min_max"]
        mem_str = f"{lo:.1f}–{hi:.1f} MB app PSS"
    det = summ.get("detector_ms_min_max")
    det_str = f"{det[0]}–{det[1]}" if det else "—"
    return [{
        "device": label,
        "isa": flags,
        "model": "llama32-1b-qlora",
        "workload": f"Android app ({summ.get('checks_total', 0)} checks)",
        "detector_ms": det_str,
        "warm_ttft_ms": summ.get("warm_kyc_ttft_ms_median") or summ.get("ttft_ms_median"),
        "prefill_tps": None,
        "decode_tps": summ.get("warm_kyc_decode_tps_max") or summ.get("decode_tps_median"),
        "per_check_s": summ.get("warm_kyc_total_s_min") or summ.get("total_s_median"),
        "memory": mem_str,
    }]


def summarize_files(paths: list[Path]) -> str:
    rows: list[dict] = []
    for p in paths:
        data = json.loads(p.read_text(encoding="utf-8"))
        schema = data.get("schema", "")
        if schema == "prahari-arm-bench-v1":
            rows.extend(_row_from_arm_linux(data))
        elif schema == "prahari-android-bench-v1":
            rows.extend(_row_from_android(data))
        else:
            raise ValueError(f"Unrecognized benchmark JSON schema in {p}: {schema!r}")

    lines = [
        "# Consolidated Prahari Arm Performance Summary",
        "",
        "| Device & Config | ISA Flags | Model | Workload | Detector (ms) | Warm TTFT (ms) | Prefill (tok/s) | Decode (tok/s) | Warm Check (s) | Peak Memory |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['device']} | `{r['isa']}` | `{r['model']}` | {r['workload']} | "
            f"{r['detector_ms'] if r['detector_ms'] is not None else '—'} | "
            f"{r['warm_ttft_ms'] if r['warm_ttft_ms'] is not None else '—'} | "
            f"{r['prefill_tps'] if r['prefill_tps'] is not None else '—'} | "
            f"{r['decode_tps'] if r['decode_tps'] is not None else '—'} | "
            f"{r['per_check_s'] if r['per_check_s'] is not None else '—'} | {r['memory']} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Merge arm_bench.py and adb_bench.py JSON outputs into one Markdown table.")
    ap.add_argument("inputs", nargs="+", type=Path, help="One or more results.json files")
    ap.add_argument("--out", type=Path, default=None, help="Optional output Markdown path")
    args = ap.parse_args(argv)
    md = summarize_files(args.inputs)
    if args.out:
        args.out.write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
