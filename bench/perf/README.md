# Prahari Performance Benchmark Harness

Reproducible benchmark scripts for Arm Linux (`aarch64`) and Arm Android (`arm64-v8a` over `adb`).
All outputs are written to `/var/tmp/...` (or a user-specified `--out-dir`) so running benchmarks
never dirties the git tree.

## Scripts

| File | Purpose |
|---|---|
| `arm_bench.py` | Arm Linux benchmark harness: sweeps CPU threads (`_unsafe_reset_threadpool` pre-load + `OMP_NUM_THREADS`), optional `taskset` CPU affinity, quantisation variants in `models/registry.json`, prompt-length tiers (`short`, `default`, `long`), and gating modes (`all` vs `flagged-only`). Records cold vs warm TTFT, prefill/decode tok/s, item wall latency, cold batch s/item, peak RSS, disk footprint, and optional `unshare -n` offline proof + `perf record` KleidiAI CPU share. |
| `adb_bench.py` | Android (`adb`) benchmark & telemetry collector: `probe` (SoC/ABI/ISA flags/RAM/battery/hashes), `stage` (APK install + no-`INTERNET` audit + timed model push + SHA-256 check), `run` (automated UI checks across samples + airplane mode + 500 ms `dumpsys meminfo` PSS/RSS sampling + screenshots; `--gating-mode`/`--samples gating`/`--deadline-s` measure flagged-only gating from the app's `PrahariPerf` records), and `parse-dir` (reproducibly parse saved RTL/adb UI XML dumps into `results.json`, `items.csv`, and `summary.md`). |
| `summarize.py` | Combines one or more `arm_bench.py` and `adb_bench.py` `results.json` files into a single cross-device Markdown comparison table. |
| `run_arm_linux.sh` | One-command wrapper for Arm Linux thread + prompt-length sweeps. |
| `run_s23_rtl.sh` | Turnkey script for a single 30-minute Samsung Galaxy S23 phone session (see `docs/perf/s23-rtl-runbook.md`). |

## Quick start

### Dry run (any machine, including x86 workstation — no inference executed)

```sh
python3 bench/perf/arm_bench.py --dry-run --threads 1,2,4,8 --prompt-lengths short,default,long
```

### Arm Linux full sweep (any `aarch64` Linux; the committed Neoverse-V2 numbers came from an earlier script, see `docs/perf/evidence/README.md`)

```sh
export HC_PY="$PWD/.venv/bin/python"
export HC_MODEL_REGISTRY="$PWD/.venv/prahari-registry.json"
PRAHARI_THREADS=1,2,4,8 PRAHARI_PERF_PROFILE=1 PRAHARI_OFFLINE_PROOF=1 \
  ./bench/perf/run_arm_linux.sh
```

To compare quant variants (e.g. `llama32-1b-qlora` vs `llama32-1b-spinquant`) or measure optional
detector-first gating (`all` vs `flagged-only`):

```sh
"$HC_PY" bench/perf/arm_bench.py \
  --models llama32-1b-qlora,llama32-1b-spinquant \
  --threads 2,4 \
  --pin-cpus auto \
  --gating-mode both \
  --repeats 3
```

### Android (`arm64-v8a` over USB or Samsung RTL RDB)

```sh
export ANDROID_SERIAL=localhost:PORT
APK=/path/to/prahari-android-arm64.apk \
PTE=/path/to/Llama-3.2-1B-Instruct-QLORA_INT4_EO8.pte \
TOK=/path/to/tokenizer.model \
  ./bench/perf/run_s23_rtl.sh
```

### Parse an existing Android capture directory offline

```sh
python3 bench/perf/adb_bench.py parse-dir docs/perf/evidence/galaxy-s23-rtl-run8 --out-dir /var/tmp/s23-parsed
```

### Merge Arm Linux + Android JSON outputs into one table

```sh
python3 bench/perf/summarize.py /var/tmp/perf-v2/results.json /var/tmp/s23-parsed/results.json
```

## Metric definitions

- **Cold vs Warm (Arm Linux):** ExecuTorch's `TextLLMRunner` lazily completes `.pte` loading and XNNPACK weight packing (`kai_run_rhs_pack_*`) on the first `generate()` call. `arm_bench.py` therefore reports **all-item means** (matching batch averages) *and* **warm steady-state means** (excluding `--warmup-items`, default `1`) plus **cold batch s/item** (`total process wall / n`, amortizing Python startup and model load).
- **TTFT:** Python callback `first_token_ms` (wall time from `generate()` entry to first token callback). On Arm Linux, ExecuTorch C++ stderr also logs native `Time to first generated token` (excluding lazy load on item 1), which is recorded alongside callback TTFT in `executorch_log`.
- **Memory:** Never conflated across platforms. Arm Linux reports ExecuTorch runner RSS (`MiB`) and `/usr/bin/time -f '%M'` max process RSS (`MiB`); `bin/eval` on Oracle N1 separately reports systemd scope cgroup `memory.peak` (which includes page cache); Android reports both in-app post-check `Debug.getPss()` (`MB`) and the highest TOTAL PSS / TOTAL RSS sampled by `dumpsys meminfo` polling during each check (`MiB`; short spikes between polls can be missed).
