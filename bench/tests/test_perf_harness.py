"""Unit tests for the Arm Linux and Android (adb) performance benchmark harness."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

import pytest

PERF_DIR = Path(__file__).resolve().parents[1] / "perf"
sys.path.insert(0, str(PERF_DIR))

import adb_bench  # noqa: E402
import arm_bench  # noqa: E402
import summarize  # noqa: E402


SAMPLE_ET_STDERR = """\
[threadpool.cpp:66] Resetting threadpool to 2 threads.
[text_llm_runner.cpp:89] RSS after loading model: 2379.683594 MiB (0 if unsupported)
[text_llm_runner.cpp:228] RSS after prompt prefill: 2398.140625 MiB (0 if unsupported)
[text_llm_runner.cpp:258] RSS after finishing text generation: 2398.140625 MiB (0 if unsupported)
[stats.h:181] \tModel Load Time:\t\t2.021000 (seconds)
[stats.h:219] \tTime to first generated token:\t0.798000 (seconds)
[stats.h:219] \tTime to first generated token:\t0.564000 (seconds)
"""

SAMPLE_PERF_FLAT = """\
# Total Lost Samples: 0
# Samples: 2K of event 'cpu-clock:pppH'
# Overhead  Command  Shared Object                      Symbol
    23.27%  python   libexecutorch_backend_xnnpack.so   [.] kai_kernel_matmul_clamp_f32_qai8dxp4x8_qsi4c32p4x8_16x4x32_opt32_neon_i8mm
    20.57%  python   libexecutorch_backend_xnnpack.so   [.] kai_kernel_matmul_clamp_f32_qai8dxp1x8_qsi4c32p4x8_1x4x32_neon_dotprod
     7.88%  python   [kernel.kallsyms]                  [k] __pi_clear_page
     5.63%  python   libexecutorch_backend_xnnpack.so   [.] kai_run_matmul_clamp_f32_qai8dxp1x8_qsi8cxp4x8_1x4_neon_dotprod
     3.20%  python   libexecutorch_backend_xnnpack.so   [.] kai_run_rhs_pack_nxk_qsi4c32p_qsu4c32s1s0
     0.77%  python   libexecutorch_backend_xnnpack.so   [.] kai_run_rhs_pack_nxk_qsi8cxp_qsi8cx_neon
     0.68%  python   libexecutorch_backend_xnnpack.so   [.] kai_run_lhs_quant_pack_qai8dxp_f32
     0.05%  python   libexecutorch_backend_xnnpack.so   [.] kai_run_lhs_quant_pack_qai8dxp_f32@plt
"""

SAMPLE_MEMINFO = """\
** MEMINFO in pid 3497 [in.prahari.app] **
 App Summary
                       Pss(KB)                        Rss(KB)
                        ------                         ------
           Java Heap:    11044                          38348
         Native Heap:  1566056                        1569136
            Graphics:    58676                          58680
           TOTAL PSS:  1744842            TOTAL RSS:  1867396       TOTAL SWAP PSS:       23
"""

SAMPLE_STATS_XML = """\
<hierarchy>
  <node content-desc="On-device stats, expanded. 6 ms · 510 ms" text="" bounds="[0,0][100,100]" />
  <node text="6 ms" bounds="[0,0][10,10]" />
  <node text="Detector" bounds="[0,0][10,10]" />
  <node text="510 ms" bounds="[0,0][10,10]" />
  <node text="First token" bounds="[0,0][10,10]" />
  <node text="43.4 t/s" bounds="[0,0][10,10]" />
  <node text="Total 1.20 s · Memory 1708.0 MB&#10;Llama 3.2 1B INT4 · ExecuTorch · XNNPACK&#10;CPU ABI: arm64-v8a" bounds="[0,0][10,10]" />
</hierarchy>
"""

SAMPLE_DEVICE_TXT = """\
ro.product.model=SM-S911B
ro.product.manufacturer=samsung
ro.build.version.release=14
ro.product.cpu.abilist=arm64-v8a,armeabi-v7a,armeabi
ro.soc.model=SM8550
ro.soc.manufacturer=QTI
Features\t: fp asimd asimddp i8mm bf16
CPU part\t: 0xd46
CPU part\t: 0xd4d
"""


def test_parse_executorch_stderr():
    parsed = arm_bench.parse_executorch_stderr(SAMPLE_ET_STDERR)
    assert parsed["threadpool_reset_to"] == 2
    assert parsed["model_load_s"] == pytest.approx(2.021)
    assert parsed["rss_after_load_mib"] == pytest.approx(2379.683594)
    assert parsed["rss_peak_runner_mib"] == pytest.approx(2398.140625)
    assert parsed["native_ttft_ms"] == [798.0, 564.0]


def test_parse_perf_flat_kleidiai_share():
    parsed = arm_bench.parse_perf_flat(SAMPLE_PERF_FLAT)
    assert parsed["lost_samples"] == 0
    assert parsed["samples_header"] == "2K"
    assert parsed["kai_total_cpu_pct"] == pytest.approx(54.17)
    assert len(parsed["kai_kernels"]) == 7
    assert parsed["kai_kernels"][0]["symbol"].endswith("neon_i8mm")


def test_aggregate_cell_separates_cold_warm_and_gating():
    runs = [
        {
            "batch_wall_s": 10.0,
            "peak_rss_time_mib": 2400.0,
            "executorch_log": {"model_load_s": 2.0, "rss_peak_runner_mib": 2398.0},
            "items": [
                {
                    "id": "i1", "kind": "sms", "verdict": "malicious",
                    "explanation_status": "success", "detector_ms": 1.2, "latency_ms": 4000.0,
                    "llm": {"prompt_tokens": 124, "generated_tokens": 28, "first_token_ms": 2800.0, "prefill_tps": 155.0, "decode_tps": 46.5},
                },
                {
                    "id": "i2", "kind": "sms", "verdict": "benign",
                    "explanation_status": "skipped_benign", "detector_ms": 0.8, "latency_ms": 0.9,
                    "llm": None,
                },
                {
                    "id": "i3", "kind": "url", "verdict": "malicious",
                    "explanation_status": "success", "detector_ms": 0.5, "latency_ms": 1200.0,
                    "llm": {"prompt_tokens": 116, "generated_tokens": 30, "first_token_ms": 520.0, "prefill_tps": 225.0, "decode_tps": 47.0},
                },
            ],
        }
    ]
    agg = arm_bench.aggregate_cell(runs, warmup_items=1)
    assert agg["explained_items_total"] == 2
    assert agg["skipped_benign_total"] == 1
    assert agg["failed_items_total"] == 0
    assert agg["cold_item1_ttft_ms_mean"] == pytest.approx(2800.0)
    assert agg["warm_ttft_ms_mean_std"][0] == pytest.approx(520.0)
    assert agg["warm_decode_tps_mean_std"][0] == pytest.approx(47.0)
    assert agg["warm_item_wall_s_mean_std"][0] == pytest.approx(1.2)
    assert agg["peak_rss_runner_mib_max"] == pytest.approx(2398.0)


def test_arm_bench_dry_run_outputs_valid_plan(capsys):
    rc = arm_bench.main(["--dry-run", "--threads", "1,2,4", "--prompt-lengths", "short,default", "--no-sha256"])
    assert rc == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["schema"] == "prahari-arm-bench-v1"
    assert plan["matrix"]["threads"] == [1, 2, 4]
    assert plan["matrix"]["prompt_lengths"] == ["short", "default"]
    assert plan["disk"]["detector_artifacts_total_bytes"] > 0


def test_adb_parsers_and_parse_dir(tmp_path, capsys):
    mem = adb_bench.parse_meminfo(SAMPLE_MEMINFO)
    assert mem["total_pss_kb"] == 1744842
    assert mem["total_rss_kb"] == 1867396
    assert mem["native_heap_pss_kb"] == 1566056

    dev = adb_bench.parse_device_txt(SAMPLE_DEVICE_TXT)
    assert dev["model"] == "SM-S911B"
    assert dev["soc_model"] == "SM8550"
    assert set(dev["isa_arm_features"]) >= {"asimddp", "i8mm", "bf16"}

    stats = adb_bench.parse_stats_xml(SAMPLE_STATS_XML)
    assert stats["detector_ms"] == pytest.approx(6.0)
    assert stats["first_token_ms"] == pytest.approx(510.0)
    assert stats["decode_tps"] == pytest.approx(43.4)
    assert stats["total_s"] == pytest.approx(1.20)
    assert stats["app_memory_mb"] == pytest.approx(1708.0)
    assert stats["cpu_abi"] == "arm64-v8a"
    assert stats["stats_expanded"] is True

    cap_dir = tmp_path / "rtl"
    cap_dir.mkdir()
    (cap_dir / "device.txt").write_text(SAMPLE_DEVICE_TXT, encoding="utf-8")
    (cap_dir / "meminfo.txt").write_text(SAMPLE_MEMINFO, encoding="utf-8")
    (cap_dir / "kyc-warm1-stats.xml").write_text(SAMPLE_STATS_XML, encoding="utf-8")
    out_dir = tmp_path / "out"
    rc = adb_bench.main(["parse-dir", str(cap_dir), "--out-dir", str(out_dir)])
    assert rc == 0
    res = json.loads((out_dir / "results.json").read_text(encoding="utf-8"))
    assert res["schema"] == "prahari-android-bench-v1"
    assert res["summary"]["warm_kyc_decode_tps_median"] == pytest.approx(43.4)
    assert (out_dir / "items.csv").is_file()
    assert (out_dir / "summary.md").is_file()

    # Cross-device summarize.py combines Arm Linux + Android JSON cleanly
    arm_json = tmp_path / "arm.json"
    arm_json.write_text(
        json.dumps({
            "schema": "prahari-arm-bench-v1",
            "host": {"machine": "aarch64", "cpu": {"model_name": "Neoverse-V2", "isa_arm_features": ["asimddp", "bf16", "i8mm"]}},
            "cells": [{
                "model": "llama32-1b-qlora",
                "threads": 2,
                "prompt_length": "default",
                "gating_mode": "all",
                "aggregate": {
                    "detector_ms_median": 1.0,
                    "warm_ttft_ms_mean_std": [539.6, 25.0],
                    "warm_prefill_tps_mean_std": [221.6, 5.0],
                    "warm_decode_tps_mean_std": [46.7, 0.2],
                    "warm_item_wall_s_mean_std": [1.265, 0.2],
                    "all_item_wall_s_mean_std": [1.728, 0.002],
                    "peak_rss_runner_mib_max": 2398.1,
                },
            }],
        }),
        encoding="utf-8",
    )
    md = summarize.summarize_files([arm_json, out_dir / "results.json"])
    assert "Neoverse-V2 (2T)" in md
    assert "samsung SM-S911B (SM8550)" in md
    assert "43.4" in md
    assert "46.7" in md


def _running(pid: int) -> bool:
    """True if pid is alive and not a zombie (kill(pid, 0) also succeeds for an unreaped zombie)."""
    try:
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except (FileNotFoundError, IndexError):
        return False
    return state not in ("Z", "X")


def _wait_gone(pid: int, tries: int = 50) -> bool:
    for _ in range(tries):
        if not _running(pid):
            return True
        time.sleep(0.1)
    return False


def _fake_executorch(root: Path, ok: bool = True) -> Path:
    """Minimal `executorch.extension.pybindings.portable_lib` so the threadpool hook can be exercised."""
    pkg = root / "fake_et" / "executorch" / "extension" / "pybindings"
    pkg.mkdir(parents=True)
    for d in (pkg.parents[1], pkg.parents[0], pkg):
        (d / "__init__.py").write_text("")
    body = "def _unsafe_reset_threadpool(n):\n    return None\n" if ok else "def _unsafe_reset_threadpool(n):\n    raise RuntimeError('unsupported')\n"
    (pkg / "portable_lib.py").write_text(body)
    return root / "fake_et"


def _stub_candidate(tmp_path):
    cand = tmp_path / "stub_cand"
    (cand / "triage").mkdir(parents=True)
    (cand / "artifacts").mkdir()
    (cand / "artifacts" / "sms.joblib").write_bytes(b"stub")
    (cand / "config.json").write_text(json.dumps({"model": "stub-llama", "max_new_tokens": 40, "temperature": 0.0}))
    (cand / "triage" / "__init__.py").write_text("")
    (cand / "triage" / "detect.py").write_text(
        "def classify_any(kind, inp):\n"
        "    if 'bill' in inp.lower() or 'irctc' in inp.lower():\n"
        "        return 0, 0.05, ['routine notice']\n"
        "    return 1, 0.99, ['scam signal']\n"
    )
    (cand / "triage" / "cli.py").write_text(
        "import json\n"
        "VERDICT = {1: 'malicious', 0: 'benign', 'uncertain': 'uncertain'}\n"
        "def read_jsonl(p): return [json.loads(l) for l in open(p) if l.strip()]\n"
        "def write_jsonl(p, rows):\n"
        "    with open(p, 'w') as f:\n"
        "        for r in rows: f.write(json.dumps(r) + '\\n')\n"
    )
    (cand / "triage" / "llm.py").write_text(
        "import json, sys\n"
        "from pathlib import Path\n"
        "def load_config(): return json.loads((Path(__file__).resolve().parents[1] / 'config.json').read_text())\n"
        "def actions_for(kind, lab, inp): return ['Check official app.']\n"
        "def scam_type(kind, inp, lab): return 'scam' if lab == 1 else ''\n"
        "class Explainer:\n"
        "    def __init__(self, cfg=None):\n"
        "        self.calls = 0\n"
        "        self.model_name = (cfg or load_config())['model']\n"
        "    def prompt(self, kind, inp, lab, ev): return f'{kind}:{lab}:{inp[:40]}'\n"
        "    def generate(self, prompt):\n"
        "        self.calls += 1\n"
        "        sys.stderr.write('[text_llm_runner.cpp:89] RSS after loading model: 1200.0 MiB\\n')\n"
        "        sys.stderr.write('[stats.h:181] \\tModel Load Time:\\t\\t1.500000 (seconds)\\n')\n"
        "        return ('Stub explanation.', {\n"
        "            'backend': 'executorch', 'model': self.model_name,\n"
        "            'prompt_tokens': 120, 'generated_tokens': 24,\n"
        "            'prefill_tps': 200.0, 'decode_tps': 45.0,\n"
        "            'first_token_ms': 900.0 if self.calls == 1 else 500.0, 'gen_wall_ms': 1000.0,\n"
        "        })\n"
    )
    pte = tmp_path / "stub.pte"
    tok = tmp_path / "tokenizer.model"
    pte.write_bytes(b"fake-pte-bytes")
    tok.write_bytes(b"fake-tok")
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps({"stub-llama": {"family": "llama", "pte": str(pte), "tokenizer": str(tok), "notes": "stub"}}))
    return cand, reg


def test_arm_bench_end_to_end_stub_candidate_gating(tmp_path, monkeypatch):
    """Exercise full arm_bench.main pipeline (all vs flagged-only) on a tiny stub candidate."""
    cand, reg = _stub_candidate(tmp_path)
    monkeypatch.setenv("PYTHONPATH", str(_fake_executorch(tmp_path)))
    out_dir = tmp_path / "bench_out"

    rc = arm_bench.main([
        "--candidate", str(cand),
        "--registry", str(reg),
        "--python", sys.executable,
        "--threads", "2",
        "--prompt-lengths", "short",
        "--gating-mode", "both",
        "--repeats", "1",
        "--out-dir", str(out_dir),
    ])
    assert rc == 0
    rep = json.loads((out_dir / "results.json").read_text(encoding="utf-8"))
    assert len(rep["cells"]) == 2
    by_mode = {c["gating_mode"]: c["aggregate"] for c in rep["cells"]}
    assert by_mode["all"]["explained_items_total"] == 6
    assert by_mode["all"]["skipped_benign_total"] == 0
    assert by_mode["flagged-only"]["explained_items_total"] == 4
    assert by_mode["flagged-only"]["skipped_benign_total"] == 2
    assert by_mode["all"]["warm_ttft_ms_mean_std"][0] == pytest.approx(500.0)
    assert by_mode["all"]["cold_item1_ttft_ms_mean"] == pytest.approx(900.0)
    assert (out_dir / "items.csv").is_file()
    assert (out_dir / "summary.md").is_file()


def test_adb_helpers_bounds_battery_and_meminfo_fallback():
    pt = adb_bench.find_bounds_center(SAMPLE_STATS_XML, desc_contains="On-device stats, expanded")
    assert pt == (50, 50)
    batt = adb_bench.parse_battery("  level: 79\n  temperature: 342\n")
    assert batt == {"level_pct": 79, "temp_c": 34.2}
    mem = adb_bench.parse_meminfo("  TOTAL  1744842  1695276  39000  23  1867396\n")
    assert mem["total_pss_kb"] == 1744842
    assert mem["total_rss_kb"] == 1867396


def test_arm_bench_refuses_unconfirmed_thread_count(tmp_path, monkeypatch):
    """A failed threadpool reset must fail the run, not be reported as an N-thread result."""
    cand, reg = _stub_candidate(tmp_path)
    monkeypatch.setenv("PYTHONPATH", str(_fake_executorch(tmp_path, ok=False)))
    rc = arm_bench.main([
        "--candidate", str(cand), "--registry", str(reg), "--python", sys.executable,
        "--threads", "4", "--prompt-lengths", "short", "--repeats", "1",
        "--out-dir", str(tmp_path / "out"),
    ])
    assert rc == 3
    rep = json.loads((tmp_path / "out" / "results.json").read_text(encoding="utf-8"))
    (cell,) = rep["cells"]
    assert cell["runs"] == [] and cell["aggregate"] == {}
    assert "threadpool reset to 4 was not confirmed" in cell["errors"][0]["error"]
    assert "all runs failed" in (tmp_path / "out" / "summary.md").read_text(encoding="utf-8")


def test_run_bounded_kills_process_group_on_timeout(tmp_path):
    marker = tmp_path / "child.pid"
    script = f"import subprocess, sys, time; p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); open({str(marker)!r}, 'w').write(str(p.pid)); time.sleep(60)"
    with pytest.raises(RuntimeError, match="timed out"):
        arm_bench.run_bounded([sys.executable, "-c", script], timeout_s=2)
    child = int(marker.read_text())
    if not _wait_gone(child):
        pytest.fail("grandchild survived the timeout kill")


def test_adb_check_button_and_completion_selectors():
    run8 = Path(__file__).resolve().parents[2] / "docs" / "perf" / "evidence" / "galaxy-s23-rtl-run8"
    sample_row = (run8 / "sample-row.xml").read_text(encoding="utf-8")
    home = (run8 / "home.xml").read_text(encoding="utf-8")
    # The real button, not the header subtitle "... scam & threat check".
    assert adb_bench.find_bounds_center(sample_row, desc_contains=adb_bench.CHECK_BUTTON_DESC) == (540, 1726)
    assert adb_bench.find_bounds_center(home, desc_contains=adb_bench.CHECK_BUTTON_DESC) is None
    # Result screen before scrolling: header not visible. After Llama finished: done.
    assert adb_bench.stats_header_state((run8 / "kyc-running.xml").read_text(encoding="utf-8")) == "absent"
    assert adb_bench.stats_header_state((run8 / "kyc-stats.xml").read_text(encoding="utf-8")) == "done"
    pending = 'content-desc="On-device stats, collapsed. 6 ms · —"'
    assert adb_bench.stats_header_state(pending) == "pending"


def test_android_summary_ignores_incomplete_checks():
    ok = {"check": "kyc-warm-1", "status": "ok", "detector_ms": 6.0, "first_token_ms": 510.0,
          "decode_tps": 43.4, "total_s": 1.2, "app_memory_mb": 1708.0}
    bad = {"check": "kyc-warm-2", "status": "timeout", "detector_ms": 6.0, "first_token_ms": None,
           "decode_tps": None, "total_s": None, "app_memory_mb": None}
    rep = adb_bench.summarize_android({}, [ok, bad])
    assert rep["summary"]["checks_total"] == 2
    assert rep["summary"]["checks_incomplete"] == ["kyc-warm-2"]
    assert rep["summary"]["warm_kyc_ttft_ms_median"] == 510.0
    assert "| `kyc-warm-2` | timeout |" in adb_bench.render_android_md(rep)


def test_adb_sample_chip_row_and_duration_formats():
    run8 = Path(__file__).resolve().parents[2] / "docs" / "perf" / "evidence" / "galaxy-s23-rtl-run8"
    home = (run8 / "home.xml").read_text(encoding="utf-8")
    assert adb_bench.sample_row_y(home) == 1522
    # Chip matched by its accessibility label, which every sample chip carries.
    assert adb_bench.find_bounds_center(home, desc_contains="KYC scam SMS, ") == (263, 1522)
    # The app prints "x.xx s" from one second (MainActivity.formatMs); an escaped quote must not cut a value.
    xml = ('<node text="" content-desc="On-device stats, expanded. 1.05 s · 2.31 s" />'
           '<node text="Total 4.20 s · Memory 1700.0 MB" content-desc="" />'
           '<node text="He said &quot;hi&quot; 12.0 t/s" content-desc="" />'
           '<node text="41.0 t/s" content-desc="" />')
    rec = adb_bench.parse_stats_xml(xml)
    assert rec["detector_ms"] == 1050.0 and rec["first_token_ms"] == 2310.0
    assert rec["total_s"] == 4.2 and rec["app_memory_mb"] == 1700.0
    assert rec["decode_tps"] == 41.0


def test_run_bounded_kills_sigterm_ignoring_descendant(tmp_path):
    marker = tmp_path / "child.pid"
    child = "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)"
    script = (f"import subprocess, sys, time; p = subprocess.Popen([sys.executable, '-c', {child!r}]); "
              f"open({str(marker)!r}, 'w').write(str(p.pid)); time.sleep(60)")
    with pytest.raises(RuntimeError, match="timed out"):
        arm_bench.run_bounded([sys.executable, "-c", script], timeout_s=2)
    pid = int(marker.read_text())
    if not _wait_gone(pid):
        os.kill(pid, 9)
        pytest.fail("SIGTERM-ignoring descendant survived the timeout kill")


def test_parse_dir_keeps_recorded_timeout_status(tmp_path):
    run8 = Path(__file__).resolve().parents[2] / "docs" / "perf" / "evidence" / "galaxy-s23-rtl-run8"
    cap = tmp_path / "cap"
    cap.mkdir()
    done_xml = (run8 / "kyc-warm1-stats.xml").read_text(encoding="utf-8")
    (cap / "kyc-warm-1-stats.xml").write_text(done_xml, encoding="utf-8")
    (cap / "kyc-warm-2-stats.xml").write_text(done_xml, encoding="utf-8")  # late values, but recorded as timeout
    (cap / "results.json").write_text(json.dumps({"checks": [
        {"check": "kyc-warm-1", "status": "ok"}, {"check": "kyc-warm-2", "status": "timeout"},
        {"check": "port-scan", "status": "no-sample-chip"}, {"check": "kyc-legacy"}]}))
    (cap / "kyc-legacy-stats.xml").write_text(done_xml, encoding="utf-8")  # older report row without status
    (cap / "home-stats.xml").write_text((run8 / "home.xml").read_text(encoding="utf-8"), encoding="utf-8")
    out = tmp_path / "out"
    assert adb_bench.main(["parse-dir", str(cap), "--out-dir", str(out)]) == 0
    rep = json.loads((out / "results.json").read_text(encoding="utf-8"))
    status = {c["check"]: c["status"] for c in rep["checks"]}
    assert status == {"kyc-warm-1": "ok", "kyc-warm-2": "timeout", "home": "incomplete-capture",
                      "port-scan": "no-sample-chip", "kyc-legacy": "ok"}
    assert sorted(rep["summary"]["checks_incomplete"]) == ["home", "kyc-warm-2", "port-scan"]
    assert "status" in (out / "items.csv").read_text(encoding="utf-8").splitlines()[0]


def test_adb_run_loop_with_fake_device(tmp_path, monkeypatch):
    """Drive cmd_run against replayed run-8 screens: chip tap, Check button, scroll to stats, airplane check."""
    run8 = Path(__file__).resolve().parents[2] / "docs" / "perf" / "evidence" / "galaxy-s23-rtl-run8"
    home = (run8 / "sample-row.xml").read_text(encoding="utf-8")      # Port scan chip + Check button visible
    running = (run8 / "kyc-running.xml").read_text(encoding="utf-8")  # result screen, stats below the fold
    stats = (run8 / "kyc-stats.xml").read_text(encoding="utf-8")      # stats header with first-token time
    state = {"screen": "home", "polls": 0, "airplane": "0", "taps": []}

    def fake_dump(serial):
        if state["screen"] == "home":
            return home
        state["polls"] += 1
        return running if state["polls"] < 3 else stats

    def fake_adb(serial, *args, check=True, timeout=120):
        a = list(args)
        if a[:2] == ["shell", "getprop"]:
            return {"ro.soc.model": "SM8550", "ro.product.model": "SM-S911B"}.get(a[2], "x") + "\n"
        if a[:3] == ["shell", "input", "tap"]:
            x, y = int(a[3]), int(a[4])
            state["taps"].append((x, y))
            if state["screen"] == "home" and (x, y) == (540, 1726):
                state["screen"], state["polls"] = "result", 0
            elif state["screen"] == "result" and y > 2000:
                state["screen"] = "home"
            return ""
        if a[:4] == ["shell", "cmd", "connectivity", "airplane-mode"]:
            state["airplane"] = "1" if a[4] == "enable" else "0"
            return ""
        if a[:4] == ["shell", "settings", "get", "global"]:
            return state["airplane"] + "\n"
        return ""

    class NoPoller:
        def __init__(self, *a, **k): pass
        def start(self): pass
        def stop(self): return {"peak_pss_mib": 1800.0, "peak_rss_mib": 1900.0, "samples": 3}

    monkeypatch.setattr(adb_bench, "adb_out", fake_adb)
    monkeypatch.setattr(adb_bench, "dump_ui_xml", fake_dump)
    monkeypatch.setattr(adb_bench, "MemPoller", NoPoller)
    monkeypatch.setattr(adb_bench.subprocess, "check_output", lambda *a, **k: b"png")
    monkeypatch.setattr(adb_bench.time, "sleep", lambda s: None)
    monkeypatch.setattr(adb_bench, "DEFAULT_SAMPLES", [("port-scan", "Port scan", False), ("kyc-airplane", "Port scan", True)])
    out = tmp_path / "out"
    rc = adb_bench.main(["--serial", "fake", "run", "--out-dir", str(out), "--with-airplane", "--settle-s", "0"])
    rep = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert rc == 0, rep["summary"]
    assert [c["status"] for c in rep["checks"]] == ["ok", "ok"]
    assert rep["checks"][0]["first_token_ms"] == 664.0 and rep["checks"][0]["decode_tps"] == 42.6
    assert rep["checks"][1]["airplane_mode_on_observed"] == "1"
    assert state["airplane"] == "0"  # restored afterwards
    # The header subtitle at (549, 211) must never be tapped.
    assert (549, 211) not in state["taps"]


def test_adb_run_loop_recovers_from_errors(tmp_path, monkeypatch):
    """A failure mid-check stops the poller; a failure after the row is recorded does not duplicate it."""
    run8 = Path(__file__).resolve().parents[2] / "docs" / "perf" / "evidence" / "galaxy-s23-rtl-run8"
    home = (run8 / "sample-row.xml").read_text(encoding="utf-8")
    stats = (run8 / "kyc-stats.xml").read_text(encoding="utf-8")
    state = {"screen": "home", "check": 0, "stops": 0}

    def fake_dump(serial):
        if state["screen"] == "home":
            return home
        if state["check"] == 1:
            raise RuntimeError("bridge dropped")  # first check dies while waiting for Llama
        return stats

    def fake_adb(serial, *args, check=True, timeout=120):
        a = list(args)
        if a[:3] == ["shell", "input", "tap"]:
            x, y = int(a[3]), int(a[4])
            if state["screen"] == "home" and (x, y) == (540, 1726):
                state["screen"] = "result"
                state["check"] += 1
            elif state["screen"] == "result" and y > 2000:
                raise RuntimeError("tap failed")  # second check: navigation after the row is recorded
            return ""
        if a[:3] == ["shell", "input", "keyevent"]:
            state["screen"] = "home"
            if state["check"] == 1:
                raise subprocess.TimeoutExpired("adb", 20)  # the recovery call itself fails once
            return ""
        return ""

    class CountingPoller:
        def __init__(self, *a, **k): pass
        def start(self): pass
        def stop(self):
            state["stops"] += 1
            return {}

    import subprocess
    monkeypatch.setattr(adb_bench, "adb_out", fake_adb)
    monkeypatch.setattr(adb_bench, "dump_ui_xml", fake_dump)
    monkeypatch.setattr(adb_bench, "MemPoller", CountingPoller)
    monkeypatch.setattr(adb_bench.subprocess, "check_output", lambda *a, **k: b"png")
    monkeypatch.setattr(adb_bench.time, "sleep", lambda s: None)
    monkeypatch.setattr(adb_bench, "DEFAULT_SAMPLES", [("a", "Port scan", False), ("b", "Port scan", False)])
    out = tmp_path / "out"
    rc = adb_bench.main(["--serial", "fake", "run", "--out-dir", str(out), "--settle-s", "0"])
    rep = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert rc == 2
    assert [(c["check"], c["status"]) for c in rep["checks"]] == [("a", "error: RuntimeError"), ("b", "ok")]
    assert rep["checks"][1]["note"].startswith("post-check navigation failed")
    assert state["stops"] == 2  # stopped by the error handler for "a", normally for "b"



GATED_STATS_XML = """\
<hierarchy>
  <node content-desc="On-device stats, expanded. 7 ms · Llama skipped" text="" bounds="[0,0][100,100]" />
  <node text="7 ms · Llama skipped" bounds="[0,0][10,10]" />
  <node text="7 ms" bounds="[0,0][10,10]" />
  <node text="Detector" bounds="[0,0][10,10]" />
  <node text="—" bounds="[0,0][10,10]" />
  <node text="First token" bounds="[0,0][10,10]" />
  <node text="—" bounds="[0,0][10,10]" />
  <node text="Decode speed" bounds="[0,0][10,10]" />
  <node text="—" bounds="[0,0][10,10]" />
  <node text="Prompt tokens" bounds="[0,0][10,10]" />
  <node text="—" bounds="[0,0][10,10]" />
  <node text="Prefill" bounds="[0,0][10,10]" />
  <node text="—" bounds="[0,0][10,10]" />
  <node text="Prefill speed" bounds="[0,0][10,10]" />
  <node text="Llama skipped: verdict and text from the detector&#10;Total 25 ms · Memory 1690.0 MB&#10;CPU ABI: arm64-v8a" bounds="[0,0][10,10]" />
</hierarchy>
"""

LLAMA_STATS_XML = """\
<hierarchy>
  <node content-desc="On-device stats, expanded. 6 ms · 510 ms" text="" bounds="[0,0][100,100]" />
  <node text="6 ms" /><node text="Detector" />
  <node text="510 ms" /><node text="First token" />
  <node text="43.4 t/s" /><node text="Decode speed" />
  <node text="128" /><node text="Prompt tokens" />
  <node text="455 ms" /><node text="Prefill" />
  <node text="281.3 t/s" /><node text="Prefill speed" />
</hierarchy>
"""


def test_stats_xml_gated_and_prefill_tiles():
    gated = adb_bench.parse_stats_xml(GATED_STATS_XML)
    assert gated["llama_skipped"] is True and gated["detector_ms"] == 7.0
    assert gated["first_token_ms"] is None and gated["decode_tps"] is None and gated["total_s"] == 0.025
    assert adb_bench.stats_header_state(GATED_STATS_XML) == "done"
    full = adb_bench.parse_stats_xml(LLAMA_STATS_XML)
    # The prefill speed tile must not overwrite decode speed.
    assert full["decode_tps"] == 43.4 and full["prefill_tps"] == 281.3
    assert full["prompt_tokens"] == 128 and full["prefill_ms"] == 455.0 and full["llama_skipped"] is None


def test_perf_records_are_correlated_across_restarts():
    text = "\n".join([
        "--------- beginning of main",
        '{"event":"model","session":"a","seq":1,"state":"ready","gating":"all"}',
        '{"event":"result","session":"a","seq":2,"id":1,"gating":"all","llama_skipped":false,"total_ms":1200}',
        "not json {",
    ])
    before = adb_bench.parse_perf_lines(text)
    assert [r["seq"] for r in before] == [1, 2]
    # The app restarted: a new session starts at seq 1 again and must still count as new.
    after = before + adb_bench.parse_perf_lines(
        '{"event":"model","session":"b","seq":1,"state":"ready","gating":"flagged-only"}\n'
        '{"event":"result","session":"b","seq":2,"id":1,"gating":"flagged-only","llama_skipped":true,'
        '"detector_ms":7.5,"total_ms":31,"prompt_tokens":null,"pss_mb":1690.04}')
    assert adb_bench.new_perf_record(before, before, "result") is None
    model = adb_bench.new_perf_record(before, after, "model")
    assert model["session"] == "b"
    res = adb_bench.new_perf_record(before, after, "result")
    row = {"detector_ms": 9.0, "first_token_ms": None}
    adb_bench.merge_perf(row, res)
    assert row["llama_skipped"] is True and row["gating_mode_observed"] == "flagged-only"
    assert row["detector_ms"] == 7.5 and row["total_s"] == 0.031 and row["app_memory_mb"] == 1690.0
    assert row["prompt_tokens"] is None and row["first_token_ms"] is None
    empty = {}
    adb_bench.merge_perf(empty, None)
    assert all(empty[k] is None for k in adb_bench.PERF_FIELDS)


def test_adb_run_gating_both_with_fake_device(tmp_path, monkeypatch):
    """Two passes: launch extra per mode, -gated ids, perf records merged, mismatch and missing flagged."""
    run8 = Path(__file__).resolve().parents[2] / "docs" / "perf" / "evidence" / "galaxy-s23-rtl-run8"
    home = (run8 / "sample-row.xml").read_text(encoding="utf-8")
    stats = (run8 / "kyc-stats.xml").read_text(encoding="utf-8")
    state = {"screen": "home", "log": [], "session": 0, "seq": 0, "gating": None, "starts": [], "checks": 0}

    def log(rec):
        state["seq"] += 1
        rec.update(session=f"s{state['session']}", seq=state["seq"])
        state["log"].append(json.dumps(rec))

    def fake_dump(serial):
        return home if state["screen"] == "home" else stats

    def fake_adb(serial, *args, check=True, timeout=120):
        a = list(args)
        if a[:2] == ["shell", "getprop"]:
            return "x\n"
        if a[:3] == ["shell", "am", "start"]:
            state["starts"].append(a)
            state["session"] += 1
            state["seq"] = 0
            if adb_bench.GATING_EXTRA in a:
                state["gating"] = a[a.index(adb_bench.GATING_EXTRA) + 1]
            log({"event": "model", "state": "ready", "gating": state["gating"]})
            return ""
        if a[:2] == ["logcat", "-d"]:
            return "\n".join(state["log"]) + "\n"
        if a[:3] == ["shell", "input", "tap"]:
            x, y = int(a[3]), int(a[4])
            if state["screen"] == "home" and (x, y) == (540, 1726):
                state["screen"] = "result"
                state["checks"] += 1
                n = state["checks"]
                if n == 2:
                    pass  # no record for this check: telemetry-missing
                else:
                    skipped = state["gating"] == "flagged-only"
                    gating = "all" if n == 3 else state["gating"]  # check 3 reports the wrong mode
                    log({"event": "result", "id": n, "gating": gating, "llama_skipped": skipped,
                         "detector_ms": 6.0, "prompt_tokens": None if skipped else 128,
                         "prefill_ms": None if skipped else 455.0, "prefill_tps": None if skipped else 281.3,
                         "first_token_ms": None if skipped else 510.0, "decode_tps": None if skipped else 43.4,
                         "total_ms": 30 if skipped else 1210, "pss_mb": 1700.0, "error": False})
            elif state["screen"] == "result" and y > 2000:
                state["screen"] = "home"
            return ""
        return ""

    class NoPoller:
        def __init__(self, *a, **k): pass
        def start(self): pass
        def stop(self): return {}

    monkeypatch.setattr(adb_bench, "adb_out", fake_adb)
    monkeypatch.setattr(adb_bench, "dump_ui_xml", fake_dump)
    monkeypatch.setattr(adb_bench, "MemPoller", NoPoller)
    monkeypatch.setattr(adb_bench.subprocess, "check_output", lambda *a, **k: b"png")
    monkeypatch.setattr(adb_bench.time, "sleep", lambda s: None)
    monkeypatch.setattr(adb_bench, "GATING_SAMPLES", [("port-scan", "Port scan", False), ("port-scan-2", "Port scan", False)])
    out = tmp_path / "out"
    rc = adb_bench.main(["--serial", "fake", "run", "--out-dir", str(out), "--gating-mode", "both",
                         "--samples", "gating", "--settle-s", "0", "--model-timeout-s", "3"])
    rep = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert rc == 2  # two checks incomplete
    assert [s[-1] for s in state["starts"]] == ["all", "flagged-only"]
    checks = {c["check"]: c for c in rep["checks"]}
    assert list(checks) == ["port-scan", "port-scan-2", "port-scan-gated", "port-scan-2-gated"]
    assert checks["port-scan"]["status"] == "ok" and checks["port-scan"]["prefill_tps"] == 281.3
    assert checks["port-scan"]["prompt_tokens"] == 128 and checks["port-scan"]["llama_skipped"] is False
    assert checks["port-scan-2"]["status"] == "telemetry-missing"
    assert checks["port-scan-gated"]["status"] == "gating-mismatch"
    gated = checks["port-scan-2-gated"]
    assert gated["status"] == "ok" and gated["llama_skipped"] is True and gated["total_s"] == 0.03
    assert gated["gating_mode"] == gated["gating_mode_observed"] == "flagged-only"
    assert [p["model_event"]["state"] for p in rep["passes"]] == ["ready", "ready"]
    by = rep["summary"]["by_gating_mode"]
    assert by["flagged-only"]["llama_skipped"] == 1 and by["all"]["llama_skipped"] == 0
    md = (out / "summary.md").read_text(encoding="utf-8")
    assert "| Gating | Checks | Llama skipped |" in md and "Prefill (tok/s)" in md
    assert "prefill_tps" in (out / "items.csv").read_text(encoding="utf-8").splitlines()[0]


def test_adb_run_deadline_records_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(adb_bench, "adb_out", lambda *a, **k: "x\n")
    ticks = iter([0.0] + [1000.0] * 50)
    monkeypatch.setattr(adb_bench.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(adb_bench.time, "sleep", lambda s: None)
    out = tmp_path / "out"
    rc = adb_bench.main(["--serial", "fake", "run", "--out-dir", str(out), "--samples", "gating",
                         "--deadline-s", "10", "--settle-s", "0"])
    rep = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert rc == 2 and {c["status"] for c in rep["checks"]} == {"skipped-deadline"}
    assert len(rep["checks"]) == len(adb_bench.GATING_SAMPLES)

def test_stats_header_after_failed_explanation():
    """24 Nov S23 lookalike link: the check ended (5.86 s) but the header kept "—", so the run waited 60 s."""
    old = (Path(__file__).resolve().parents[2] / "evidence" / "galaxy-s23-20261124" / "label-adjusted"
           / "lookalike-link-stats.xml").read_text(encoding="utf-8")
    assert adb_bench.stats_header_state(old) == "pending"
    fixed = old.replace("244 ms · —", "244 ms · No AI text")
    assert adb_bench.stats_header_state(fixed) == "done"
    assert adb_bench.parse_stats_xml(fixed)["detector_ms"] == 244.0
