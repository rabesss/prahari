# Performance Measurement Methodology & Provenance

This document describes the hardware environments, metric definitions, profiling methods, offline
verification procedures, and exact artefact provenance backing [`docs/perf/README.md`](README.md).

## 1. Hardware & Software Matrix

| Target | Silicon & Microarchitecture | Cores & RAM | Arm ISA Flags Verified | OS & Runtime | Model Artefact |
|---|---|---|---|---|---|
| **Samsung Galaxy S23** (`SM-S911B`, RTL Noida) | Qualcomm SM8550 (Snapdragon 8 Gen 2; `0xd46` Cortex-A510 + `0xd4d` Cortex-A715 (the 60-line `/proc/cpuinfo` excerpt in `device.txt` shows only these two part numbers)) | 8-core Armv9 SoC | `asimd`, `asimddp`, `i8mm`, `bf16`, `fphp`, `asimdhp` (`/proc/cpuinfo`) | Android 14, `arm64-v8a`, `org.pytorch:executorch-android:1.5.1` + XNNPACK, Chaquopy 17.2.0 (Python 3.10, NumPy 1.26.2) | `Llama-3.2-1B-Instruct-QLORA_INT4_EO8.pte` (`ab7b7ebf…`) + `tokenizer.model` (`82e9d319…`) |
| **Arm Neoverse-V2 Linux** (Sail Arm size L) | Arm Neoverse-V2 `r0p1` (single NUMA node, 512 KiB L1d/L1i, 16 MiB L2, 36 MiB L3) | 8 online vCPUs (56 offline), 15 GiB RAM, 0 swap | `asimd`, `asimddp`, `i8mm`, `bf16`, `fphp`, `asimdhp` (no `sve`/`sve2` exposed) | Debian 12, Linux 6.1.155 `aarch64`, Python 3.12.16, ExecuTorch 1.6.0, Torch 2.15.0+cpu, scikit-learn 1.9.1 | Exact same `.pte` & `tokenizer.model` (hashes verified) |
| **Oracle A1 Arm Neoverse-N1** (shared cloud VM) | Arm Neoverse-N1 (Ampere Altra) | 2 vCPUs, ~11 GiB RAM | `aarch64` (no `i8mm`/`bf16`; Armv8.2-A) | Ubuntu 24.04, Python 3.12, ExecuTorch 1.6.0, Torch CPU, scikit-learn 1.9.1 | Exact same `.pte` & `tokenizer.model` (hashes verified) |

## 2. Metric Definitions & Measurement Boundaries

To prevent apples-to-oranges comparisons, every measurement is tagged with its exact boundary:

- **Detector latency (`detector_ms`):**
  - *Android S23:* Wall time of `mobile.verdict(kind, text)` measured with `time.perf_counter()` inside Python (`android/python/mobile.py`). First check per task pays one-time JSON load (`255 ms` for SMS/Indic, `183 ms` for URL); subsequent warm checks take `5–17 ms`.
  - *Arm Linux (`bin/eval` on N1):* Per-task batch `bin/predict` throughput (`detection.<task>.items_per_s` in `research/evals/ledger.jsonl`, which includes interpreter start and model load) for SMS (`n=1,162`), URL (`n=7,997`), Indic (`n=320`) and NSL-KDD flow (`n=22,544`). Round-3 `ctl-conf51-gen51` runs 1–3: SMS 206–215/s, URL 1,996–2,375/s, Indic 57–64/s, flow 5,342–7,118/s. Earlier per-run records under `research/evals/*/details.json` also report a pooled `performance.detector_ms_per_item` (e.g. 0.407 ms in round-2 `best-confirm`); it varies by detector version and host load.
  - *Arm Linux (`arm_bench.py`):* Per-item `detect.classify_any()` wall time via `time.perf_counter()`.
- **Time to First Token (`TTFT` / `first_token_ms`):**
  - *Android S23:* Elapsed time from `LlmModule.generate()` entry (`SystemClock.elapsedRealtime()`) to the first `LlmCallback.onResult()` invocation (`MainActivity.kt:458–467`). Model loading already occurred on app startup (`requestModel()`).
  - *Arm Linux (`bin/explain` / `arm_bench.py`):* Elapsed time from `TextLLMRunner.generate()` entry to first Python `token_callback` call (`triage/llm.py:540–545`). Because ExecuTorch's `TextLLMRunner` lazily finishes loading the `.pte` (`Model Load Time` 1.85–2.37 s in 11 of 12 V2 runs; 6.04 s once at 4T repeat 3) on the **first** `generate()` call, item 1's callback `first_token_ms` includes model load (`~2.82 s` at 2T on V2), while ExecuTorch's native `Time to first generated token` logs `0.79–0.80 s` for item 1 (it includes one-time XNNPACK weight packing) and `0.505–0.564 s` for warm items 2–6 at 2T. Both **all-item** and **warm (items 2–6)** statistics are therefore reported separately.
  - *Oracle N1 historical `bin/app --demo` (17 Nov):* Earlier `first_token_ms` logged an absolute timestamp rather than a delta and is excluded.
- **Prefill & Decode Throughput (`prefill_tps`, `decode_tps`):**
  - Reported directly by ExecuTorch's native C++ `Stats` (`PyTorchObserver` JSON: `prefill_token_per_sec`, `decode_token_per_sec`). Android 1.5.1 UI displays `decode_tps` (`t/s`) and does not surface `prefill_tps` on the card.
- **Per-Check Latency (`item_wall_s` vs `cold_batch_s_per_item`):**
  - *Item wall (`latency_ms` / `Total s`):* Detector classification + Llama prompt build + generation + safety post-checks for one item.
  - *Cold batch s/item (`batch_wall_s / n`):* Whole-process wall clock (including Python interpreter startup, imports, joblib load, `.pte` load, and all `n` items) divided by `n`.
- **Memory Accounting (three distinct counters, never merged):**
  - *Android App Memory (`MB`):* `android.os.Debug.getPss() / 1024.0` sampled immediately after each check finishes (`MainActivity.kt:394`). This is a post-inference snapshot, not continuous peak.
  - *Android `dumpsys meminfo` (`KiB` / `MiB`):* Kernel-accounted `TOTAL PSS` (proportional set size), `TOTAL RSS` (resident set size), and per-segment breakdown (`Native Heap`, `Java Heap`, `Graphics`, `Code`, `SwapPss`). On S23 run 8 after KYC: `1,744,842 KiB` (`1,703.9 MiB`) TOTAL PSS, `1,867,396 KiB` (`1,823.6 MiB`) TOTAL RSS, with Native Heap (`1,566,056 KiB` = `1,529.4 MiB`, **89.8% of PSS**) holding the loaded INT4 weights and KV buffers.
  - *Arm Linux ExecuTorch RSS (`MiB`):* Logged directly by `text_llm_runner.cpp` after model load (`2,373.8–2,385.0 MiB`), after prefill, and after generation (`2,392.1–2,403.3 MiB` peak on V2).
  - *Oracle N1 `bin/eval` (`GB`):* Systemd user-scope cgroup `memory.peak` (2.05 GB for PR #30; 2.078–2.338 GB across the three `ctl-conf51-gen51` runs; ledger key `peak_process_tree_rss_gb`), which includes OS file-backed page cache and varies by over 10% between identical runs; older round-2 `best-confirm` (`2.256 GB`) used proc/runner peak RSS.

## 3. KleidiAI Micro-Kernel Dispatch Evidence

### Direct CPU Profiling on Arm Neoverse-V2 (`ExecuTorch 1.6.0`)

`perf record -F 99 -g` profiled one complete 2-thread `bin/explain` invocation (Python startup,
imports, model load, and all 6 demo items) on Arm Neoverse-V2 (`i8mm` + `asimddp` + `bf16`).
`perf report --stdio --no-children` recorded ~2,222 samples (`event count ≈ 22,444,444,220`) with
**zero lost samples**. Named Arm KleidiAI (`kai_*`) leaf functions accounted for **54.17%** of
whole-process sampled CPU time (including Python startup and kernel page-clearing overhead):

| KleidiAI Symbol (`libexecutorch_backend_xnnpack.so`) | Sampled CPU % | Call-Stack Attribution (`perf report -g`) | Role in Prahari |
|---|---:|---|---|
| `kai_kernel_matmul_clamp_f32_qai8dxp4x8_qsi4c32p4x8_16x4x32_opt32_neon_i8mm` | **23.27%** | `TextPrefiller::prefill_chunk` → `XNNExecutor::forward` → `xnn_invoke_runtime` | Prompt prefill (4-bit group-32 weights × dynamic INT8 activations, Arm NEON `i8mm`) |
| `kai_kernel_matmul_clamp_f32_qai8dxp1x8_qsi4c32p4x8_1x4x32_neon_dotprod` | **20.57%** | `TextTokenGenerator::generate` → `XNNExecutor::forward` → `xnn_invoke_runtime` | Autoregressive token decode (4-bit group-32 matvec, Arm NEON `dotprod`) |
| `kai_run_matmul_clamp_f32_qai8dxp1x8_qsi8cxp4x8_1x4_neon_dotprod` | **5.63%** | `XNNExecutor::forward` → `xnn_invoke_runtime` | 8-bit quantized linear / embedding-output (`EO8`) matmul (`dotprod`) |
| `kai_run_rhs_pack_nxk_qsi4c32p_qsu4c32s1s0` | **3.20%** | `XnnpackBackend::init` → `XNNCompiler::compileModel` → `xnn_create_fully_connected_nc_qp8_f32_qb4w` | One-time 4-bit weight repacking during model init |
| `kai_run_rhs_pack_nxk_qsi8cxp_qsi8cx_neon` | **0.77%** | `XnnpackBackend::init` → `XNNCompiler::compileModel` → `xnn_create_fully_connected_nc_qp8_f32_qc8w` | One-time 8-bit weight repacking during model init |
| `kai_run_lhs_quant_pack_qai8dxp_f32` (+ `.plt` 0.05%) | **0.73%** | `XNNExecutor::forward` | Per-token dynamic FP32 → INT8 activation quantization & packing |
| **Total named `kai_*` CPU share** | **54.17%** | Whole process (incl. Python startup, GC, kernel `__pi_clear_page` 7.88%, OpenBLAS 3.78%) | Directly confirms active KleidiAI dispatch on Arm |

Additional inference kernels observed in the same profile: ExecuTorch `cpu_flash_attention<float, 32, 512>`
(`libcustom_ops_aot_lib.so`, 0.36%) for SDPA with KV cache (`use_sdpa_with_kv_cache = 1`, `max_context_len = 2048`).

### Honest Scope Limits on KleidiAI Claims

- **No KleidiAI on/off A/B on the installed wheel:** Searching the installed ExecuTorch 1.6.0 Python
  sources and `.so` strings found no supported runtime flag to disable KleidiAI without rebuilding
  ExecuTorch from source; therefore we report measured KleidiAI CPU share (`54.17%`) and cross-generation
  speed (`N1 → V2`, `2.33–2.57×`), not a fabricated KleidiAI on-vs-off speedup ratio.
- **Oracle Neoverse-N1:** `nm -D --defined-only` confirmed `517` `kai_*` exported symbols in
  `libexecutorch_backend_xnnpack.so` (plus `56` in `libexecutorch_kernels_torchao.so`, `47` in
  `libexecutorch_kernels_optimized.so`, `47` in `libcustom_ops_aot_lib.so`); `perf` was not run on N1.
- **Samsung Galaxy S23 (`executorch-android:1.5.1` Maven AAR):** The shipped `lib/arm64-v8a/libexecutorch.so`
  (`8.64 MiB`) embeds `XnnpackBackend` but is stripped of internal function symbols, and unrooted RTL
  devices do not permit `perf record`. S23 hardware (`SM8550`) exposes `asimddp`, `i8mm`, and `bf16` and
  executes the exact same `.pte` via XNNPACK at `38.6–43.4 tok/s`, while kernel-level `kai_*` dispatch
  proof comes from Neoverse-V2 Linux above.

## 4. Offline Verification Tiers

| Target | Isolation Mechanism | Observed Failure of Outbound Access | Observed Prahari Inference Result |
|---|---|---|---|
| **Galaxy S23** (physical phone) | 1. Manifest declares **no `android.permission.INTERNET`** (audited in CI via `check_manifest.py` + `aapt dump permissions`).<br>2. **Airplane mode enabled** (`airplane_mode_on=1`). | 1. In-app "Prove it's offline" HTTPS attempt threw Android `SecurityException`.<br>2. Radio disabled (`airplane_mode_on=1`, airplane icon visible in screenshot). | KYC check succeeded offline: `DANGEROUS`, detector `8 ms`, TTFT `657 ms`, decode `39.0 tok/s`, total `1.42 s`, PSS `1,772.6 MB`. |
| **Arm Neoverse-V2** (Linux) | Kernel network namespace (`unshare -n`) | `ip -brief link` showed only `lo DOWN`; `curl https://example.com` exit `6`; `getent ahosts huggingface.co` exit `2`; raw TCP to `1.1.1.1:443` raised `OSError: [Errno 101] Network is unreachable`. | `bin/explain` exited `0`; all 6 explanations succeeded (`45.5–46.3 tok/s` decode, `1.057–1.748 s` warm item latency, `2,392.1 MiB` RSS). |
| **Oracle Neoverse-N1** (Linux VM) | Python import-time network guard (`eval/guard`) + `HF_HUB_OFFLINE=1` + `bwrap` | `unshare -rn` blocked on Oracle VM (`Operation not permitted`); `eval/guard` blocks non-loopback sockets/DNS (`0` violations in `guard.log`). | Full `bin/eval` suite passed with `net_violations: 0`. |

## 5. Artifact Provenance

| Claim / Dataset | Primary Source Artifact / Log | Date | Status / Caveat |
|---|---|---|---|
| Galaxy S23 per-check metrics, airplane mode, `dumpsys meminfo`, device CPU flags | RTL run 8 capture (`REPORT.md`, `device.txt`, `device-sha256.txt`, `meminfo.txt`, `*-stats.xml`, `*-stats.png`, `prove-offline.png`); committed at [`evidence/galaxy-s23-rtl-run8/`](evidence/galaxy-s23-rtl-run8/REPORT.md) | 2026-11-23 | Re-verified by `bench/perf/adb_bench.py parse-dir`; pre-PR#41 APK (had bank repeat & link question bugs fixed in PR #41); warm-2 card not expanded |
| Arm Neoverse-V2 thread scaling (1/2/4/8T), KleidiAI `perf` 54.17%, `unshare -n` offline proof | Sail Arm L capture (`REPORT.md`, `out/env.txt`, `out/hashes.txt`, `out/threads.csv`, `out/thread-*-*.{log,jsonl}`, `out/perf-flat.txt`, `out/perf-report.txt`, `out/offline-proof.txt`); committed at [`evidence/neoverse-v2/`](evidence/neoverse-v2/REPORT.md) (`perf.data` binaries, pip/apt logs not committed) | 2026-11-23 | 3 repeats × 6 visible items on one box; 4T repeat-3 had a cold item-1 spike |
| Oracle Neoverse-N1 round-3 confirmation (`ctl-conf51`), PR #28 review-2, PR #30 | Committed [`research/evals/ledger.jsonl`](../../research/evals/ledger.jsonl), [`research/LOG.md`](../../research/LOG.md), [`docs/phase1/EVIDENCE.md`](../phase1/EVIDENCE.md) | 2026-11-21 | Shared 2-vCPU cloud VM (`±15–30%` co-tenant load swing); systemd cgroup `memory.peak` includes page cache |
| Oracle Neoverse-N1 round-2 `best-confirm` & prompt compaction trajectory (`222→199→137→130` tok) | Committed [`research/evals/20261111-075405-best-confirm/details.json`](../../research/evals/20261111-075405-best-confirm/details.json) and earlier round-2 `details.json` stamps (`gen2-full-r2`, `gen2-full-r2b`, `best-final`, `gen11-full`) | 2026-11-10 – 11-11 | Mixed host load across days; token counts are deterministic |
| Oracle N1 SpinQuant comparison (`58–63` prefill / `12–13.5` decode) | Committed [`candidates/BEST/REPORT.md`](../../candidates/BEST/REPORT.md) & [`docs/phase1/EVIDENCE.md`](../phase1/EVIDENCE.md) | 2026-11-11 | Measured under mixed co-tenant load; not a controlled paired A/B |
| Oracle N1 KleidiAI symbol inspection (`517` `kai_*` symbols in XNNPACK `.so`) | Committed [`docs/phase1/EVIDENCE.md`](../phase1/EVIDENCE.md) (line 11) | 2026-11-17 | Exported symbol count only; dispatch verified on Neoverse-V2 |
| Exact `.pte`, tokenizer, joblib, and Android APK disk sizes | Direct `stat` & APK zip inspection of `candidates/BEST/artifacts/*.joblib`, `/var/tmp/prahari-model/*`, `/var/tmp/prahari-final-v2/prahari-android-arm64.apk` | 2026-11-23 | Exact byte counts and SHA-256 digests recorded in `docs/perf/README.md` |
