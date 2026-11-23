# Prahari Hardware Utilisation & Performance Summary (Arm)

This document consolidates every **traced, artefact-backed** hardware performance measurement for
Prahari (Bharat AI-SoC Challenge 2026–27, PS3) across three Arm targets: a physical **Samsung Galaxy
S23** smartphone (`arm64-v8a`), an **Arm Neoverse-V2** Linux server (`aarch64`, 8 vCPUs), and an
**Oracle A1 Arm Neoverse-N1** Linux VM (`aarch64`, 2 vCPUs). Every number below is traced to a
recorded log, XML dump, `perf` profile, or committed evaluation record (see
[`methodology.md`](methodology.md#5-artifact-provenance) for exact file paths and hashes). The raw S23 and
Neoverse-V2 logs, UI dumps, screenshots and `perf` reports are committed under [`evidence/`](evidence/README.md);
the Oracle N1 records are in [`research/evals/ledger.jsonl`](../../research/evals/ledger.jsonl). No numbers
are interpolated, extrapolated, or drawn from x86 emulation.

All three Arm targets ran the **identical** Llama 3.2 1B Instruct QLoRA INT4 ExecuTorch artefact
(`Llama-3.2-1B-Instruct-QLORA_INT4_EO8.pte`, SHA-256 `ab7b7ebf…`, `1.100 GiB` on disk) and
`tokenizer.model` (SHA-256 `82e9d319…`, `2.08 MiB`), with local classical ML + mechanism-rule
detectors running ahead of the language model.

## Consolidated Cross-Device Performance Table

| Device & Silicon | OS / Runtime & Threads | Workload & State | Detector Latency | TTFT (first token) | Prefill (tok/s) | Decode (tok/s) | Per-Check Latency | Peak Memory (labelled by method) | Offline Proof |
|---|---|---|---:|---:|---:|---:|---:|---|---|
| **Samsung Galaxy S23** (`SM-S911B`, Qualcomm SM8550 / Snapdragon 8 Gen 2, `arm64-v8a`, `asimddp`/`i8mm`/`bf16`) | Android 14, ExecuTorch 1.5.1 AAR + XNNPACK (auto big-core pool), Chaquopy Python 3.10 + NumPy | KYC scam SMS — **warm** (warm 1 & warm 3; warm 2 TTFT 499 ms) | **6 ms** | **499–510 ms** (warm 1: 510 ms) | n/r *(AAR UI hides prefill)* | **42.9–43.4** (warm 1: 43.4) | **1.20–1.21 s** | **1,708.0–1,724.8 MB** app post-check PSS *(dumpsys after KYC: **1,703.9 MiB** PSS / **1,823.6 MiB** RSS)* | No `INTERNET` perm (`SecurityException`) + **Airplane Mode** verified |
| **Samsung Galaxy S23** (`SM-S911B`, SM8550, `arm64-v8a`) | Android 14, ExecuTorch 1.5.1 AAR + XNNPACK | **All 7 full checks** (cold KYC, 2× warm KYC, bank debit, lookalike link, port scan, **airplane-mode KYC**) | **5–17 ms** warm *(183–255 ms cold JSON load)* | **508–664 ms** *(airplane: 657 ms)* | n/r | **38.6–43.4** *(airplane: 39.0)* | **1.20–3.53 s** *(median 1.49 s; airplane: 1.42 s)* | **1,692.4–1,781.2 MB** app post-check PSS *(+88.8 MB over 7 checks)* | `airplane_mode_on=1` verified (`1.42 s`, `39.0 tok/s`) |
| **Arm Neoverse-V2** (Sail Arm L, `r0p1`, 8 online vCPUs, 15 GiB RAM, `aarch64`, `asimddp`/`i8mm`/`bf16`) | Debian 12, ExecuTorch 1.6.0 + XNNPACK/**KleidiAI**, **2 threads** (`_unsafe_reset_threadpool`) | 6 visible demo items × 3 repeats — **all-6 mean** *(incl. item-1 lazy load)* | ~1–6 ms *(in item wall)* | **922.0 ± 3.1 ms** *(warm items 2–6: **539.6 ms**)* | **210.58 ± 0.22** *(warm: **221.63**)* | **46.69 ± 0.12** *(warm: **46.72**)* | **1.728 ± 0.002 s** *(warm: **1.265 s**; cold batch: 2.485 s/item)* | **2,398.1 MiB** (`2.34 GiB`) ExecuTorch process RSS *(2,379.7 MiB after load)* | **Kernel `unshare -n`** (`lo` DOWN; curl/DNS/TCP fail; 6/6 pass) |
| **Arm Neoverse-V2** (8 online vCPUs, `aarch64`) | Debian 12, ExecuTorch 1.6.0 + XNNPACK/**KleidiAI**, **8 threads** | 6 visible demo items × 3 repeats — **all-6 mean** *(warm items 2–6 in italics)* | ~1–6 ms | **526.8 ± 15.0 ms** *(warm: **159.3 ms**)* | **676.80 ± 2.29** *(warm: **751.17**)* | **104.58 ± 1.15** *(warm: **104.31**)* | **0.980 ± 0.015 s** *(warm: **0.534 s**; cold batch: 1.606 s/item)* | **2,395.6 MiB** (`2.34 GiB`) ExecuTorch process RSS | Same host & model as `unshare -n` proof above |
| **Oracle A1 Arm Neoverse-N1** (shared VM, 2 vCPUs, ~11 GiB RAM, `aarch64`) | Ubuntu 24.04, ExecuTorch 1.6.0 + XNNPACK (2 vCPUs), `bwrap` + `systemd_scope` | Round-3 `ctl-conf51` (`gen51`, 3 clean runs × 28 items); PR #30 (`b9e16a6e…`) | **0.407–0.448 ms/item** *(batch `bin/predict`)* | n/r *(v2/v3 eval logs absolute ts)* | **75.2–82.7** *(round-2 `best-confirm`: 82.54)* | **16.05–20.26** *(med **20.12**; `best-confirm`: **20.80**)* | **3.79–4.79 s** *(med **3.85 s**; PR #30: **3.77 s**; `best-confirm`: **3.67 s**)* | **2.078–2.338 GB** systemd cgroup `memory.peak` *(PR #30: **2.05 GB**; includes page cache)* | Python import-time network guard (`eval/guard`, 0 net violations) |

> **Important accounting distinctions:**
> 1. **Memory metrics are not interchangeable across platforms:** Oracle N1 `bin/eval` records systemd
>    cgroup `memory.peak` (which includes OS file page cache), Neoverse-V2 logs report ExecuTorch
>    `TextLLMRunner` process RSS (`MiB`), and Galaxy S23 reports Android `Debug.getPss()` post-check
>    PSS (`MB`) alongside a `dumpsys meminfo` snapshot (`1,703.9 MiB` TOTAL PSS / `1,823.6 MiB` TOTAL RSS).
> 2. **Cold vs warm on Arm Linux:** ExecuTorch's `TextLLMRunner` lazily finishes model loading and
>    XNNPACK weight packing (`~2.01–2.37 s`) on the first `generate()` call. On Neoverse-V2, item 1
>    (`kyc-sms`) therefore pays that one-time cost while items 2–6 run warm (`1.265 s` at 2T, `0.534 s`
>    at 8T). On Galaxy S23, `MainActivity` preloads the `.pte` on app launch before the user taps Check.
> 3. **Emulator excluded:** Android x86_64 emulator timings are intentionally omitted from Arm claims.

## Neoverse-V2 Thread-Scaling Breakdown (1 / 2 / 4 / 8 Threads)

Measured on Arm Neoverse-V2 (`r0p1`, 8 online vCPUs, 3 cold-process repeats × 6 visible demo items,
median 122.5 prompt / 28 generated tokens, `_unsafe_reset_threadpool(n)` before model load):

| Threads | Model Load (s) | Warm TTFT (ms) *(items 2–6)* | All-6 TTFT (ms) *(mean ± sd)* | Warm Prefill (tok/s) | All-6 Prefill (tok/s) | Warm Decode (tok/s) | All-6 Decode (tok/s) | Warm Item Wall (s) | All-6 Item Wall (s) | Cold Batch (s/item) | Runner Peak RSS (MiB) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **1** | 2.367 | 1,060.1 | 1,465.5 ± 33.1 | 112.79 | 109.26 ± 0.07 | 25.69 | 25.69 ± 0.16 | 2.317 | 2.792 ± 0.031 | 3.437 ± 0.052 | 2,403.3 |
| **2** | 2.021 | 539.6 | 922.0 ± 3.1 | 221.63 | 210.58 ± 0.22 | 46.72 | 46.69 ± 0.12 | 1.265 | 1.728 ± 0.002 | 2.485 ± 0.210 | 2,398.1 |
| **4** | 2.054 | 290.0 | 907.7 ± 373.0\* | 412.23 | 378.79 ± 2.70 | 76.01 | 75.89 ± 0.43 | 0.777 | 1.470 ± 0.377\* | 2.098 ± 0.378\* | 2,397.2 |
| **8** | 2.026 | 159.3 | 526.8 ± 15.0 | 751.17 | 676.80 ± 2.29 | 104.31 | 104.58 ± 1.15 | 0.534 | 0.980 ± 0.015 | 1.606 ± 0.020 | 2,395.6 |

*\*At 4 threads, repeat 3 had a single cold item-1 spike (`6,580 ms` vs `2,677–2,732 ms` in repeats 1–2); warm items 2–6 stayed tight at `284–298 ms` TTFT and `0.61–1.23 s` item wall across all 3 repeats.*

- **Prefill scaling (1T → 8T, warm):** `112.79 → 751.17 tok/s` (**6.66×**; compute-bound NEON `i8mm` matmul scales nearly linearly across cores).
- **Decode scaling (1T → 8T, warm):** `25.69 → 104.31 tok/s` (**4.06×**; memory-bandwidth-bound INT4 matrix-vector multiply saturates earlier than prefill).
- **Architecture generation gain at equal thread count (2T Neoverse-N1 → 2T Neoverse-V2):** prefill `~82 → 210.6 tok/s` (**~2.57×**), decode `~20 → 46.7 tok/s` (**~2.33×**), reflecting Armv9 `i8mm` + `dotprod` micro-kernels and higher per-core IPC/bandwidth on V2.

## Samsung Galaxy S23 Per-Check Breakdown (RTL Run 8, 2026-11-23)

All values extracted verbatim from `*-stats.xml` UI dumps and `meminfo.txt` on physical Galaxy S23
(`SM-S911B`, Qualcomm SM8550, Android 14, `arm64-v8a`):

| Check | Verdict | Detector (ms) | First Token (ms) | Decode (tok/s) | Total (s) | App PSS (MB) | Notes |
|---|---|---:|---:|---:|---:|---:|---|
| KYC first | DANGEROUS | 255 | 664 | 42.6 | 2.00 | 1,692.4 | First SMS check (cold portable JSON model load) |
| KYC warm 1 | DANGEROUS | 6 | 510 | 43.4 | 1.20 | 1,708.0 | Warm steady-state SMS check |
| KYC warm 2 | DANGEROUS | 6 | 499 | *(not expanded)* | *(not expanded)* | *(not expanded)* | Collapsed stats card captured |
| KYC warm 3 | DANGEROUS | 6 | 508 | 42.9 | 1.21 | 1,724.8 | Warm steady-state SMS check |
| Bank debit alert | SUSPICIOUS | 17 | 615 | 39.8 | 1.50 | 1,737.5 | Pre-PR#41 APK (repeated opening sentence) |
| Lookalike link | DANGEROUS | 183 | 594 | 39.1 | 3.53 | 1,781.2 | First URL check (cold `url.json` load + longer output) |
| Port scan | DANGEROUS | 5 | 650 | 38.6 | 1.49 | 1,772.6 | Flow-text rules + Llama explanation |
| KYC (airplane mode) | DANGEROUS | 8 | 657 | 39.0 | 1.42 | 1,772.6 | Verified `airplane_mode_on=1` before check |

## Disk Footprint Breakdown (Exact Bytes)

| Component | Exact Bytes | Human Size | SHA-256 (prefix) | Platform |
|---|---:|---:|---|---|
| `Llama-3.2-1B-Instruct-QLORA_INT4_EO8.pte` | 1,181,451,008 | **1.100 GiB** (1.181 GB) | `ab7b7ebf97421c77…` | Shared (Android + Arm Linux) |
| `tokenizer.model` | 2,183,982 | **2.08 MiB** (2.18 MB) | `82e9d31979e92ab9…` | Shared (Android + Arm Linux) |
| Linux detectors (`candidates/BEST/artifacts/*.joblib`) | 4,540,938 | **4.33 MiB** | git-tracked | Arm Linux (`url` 1.83, `indic` 1.57, `sms` 0.64, `flow` 0.30 MiB) |
| Linux full bundle (`bin/eval` `size_gb`) | — | **1.186 GB** | — | Arm Linux (candidate + shared PTE) |
| Android `arm64-v8a` APK (`prahari-android-arm64.apk`) | 47,970,184 | **45.75 MiB** | `6b7b375ad1bf0498…` | Android (`libexecutorch.so` 8.64 MiB + portable JSONs 3.30 MiB comp / 14.00 MiB uncomp) |
| **Total Android on-device storage** (APK + PTE + tokenizer) | **1,231,605,174** | **1.147 GiB** (1.232 GB) | — | Physical Galaxy S23 |

## Related Documents

- [`methodology.md`](methodology.md) — Hardware inventory, KleidiAI `perf` dispatch proof (`54.17%`), offline verification tiers, and complete artefact provenance table.
- [`optimisations.md`](optimisations.md) — Honest inventory of shipped, optional/benchmarked, experimental, and deliberately omitted optimisations with measured effects.
- [`s23-rtl-runbook.md`](s23-rtl-runbook.md) — What is already captured vs what a fresh 30-minute Galaxy S23 RTL session adds, with exact step-by-step commands.
- [`../../bench/perf/README.md`](../../bench/perf/README.md) — Reproducible Arm Linux and Android (`adb`) benchmark harness guide.
