# Raw performance evidence

Unedited captures behind the numbers in [`../README.md`](../README.md). Nothing here was retyped by
hand: the S23 files are `uiautomator` XML dumps, `screencap` PNGs and `dumpsys` output pulled with
`adb`, and the Neoverse-V2 files are the logs and CSVs written on the box. Oracle Neoverse-N1 records
live in [`research/evals/ledger.jsonl`](../../../research/evals/ledger.jsonl) and are not duplicated here.

## Where each headline number comes from

| Headline number | File | How to check |
|---|---|---|
| S23 warm KYC: 6 ms detector, 510 ms first token, 43.4 tok/s, 1.20 s, 1,708.0 MB PSS | [`galaxy-s23-rtl-run8/kyc-warm1-stats.xml`](galaxy-s23-rtl-run8/kyc-warm1-stats.xml) (screenshot: [`kyc-warm1-stats.png`](galaxy-s23-rtl-run8/kyc-warm1-stats.png)) | Read the `text=` attributes, or run `python3 bench/perf/adb_bench.py parse-dir docs/perf/evidence/galaxy-s23-rtl-run8 --out-dir /tmp/s23` |
| S23 airplane mode: 8 ms, 657 ms, 39.0 tok/s, 1.42 s | [`galaxy-s23-rtl-run8/kyc-airplane-stats.xml`](galaxy-s23-rtl-run8/kyc-airplane-stats.xml), [`kyc-airplane-top.png`](galaxy-s23-rtl-run8/kyc-airplane-top.png) (airplane icon in status bar) | `airplane_mode_on=1` check recorded in [`REPORT.md`](galaxy-s23-rtl-run8/REPORT.md) |
| S23 no-INTERNET proof | [`galaxy-s23-rtl-run8/prove-offline.png`](galaxy-s23-rtl-run8/prove-offline.png) | In-app HTTPS GET blocked with `SecurityException` |
| S23 memory: 1,744,842 KiB TOTAL PSS, 1,867,396 KiB TOTAL RSS | [`galaxy-s23-rtl-run8/meminfo.txt`](galaxy-s23-rtl-run8/meminfo.txt) line 40 | `dumpsys meminfo in.prahari.app` after the KYC check |
| S23 SoC, ABI and ISA flags (`SM8550`, `i8mm`, `asimddp`, `bf16`) | [`galaxy-s23-rtl-run8/device.txt`](galaxy-s23-rtl-run8/device.txt) | `getprop` + `/proc/cpuinfo` |
| Model and tokenizer SHA-256 on the phone | [`galaxy-s23-rtl-run8/device-sha256.txt`](galaxy-s23-rtl-run8/device-sha256.txt) | Matches `ab7b7ebf…` / `82e9d319…` |
| Neoverse-V2 all-item means (e.g. 2T: 922.0 ms first token, 46.69 tok/s, 1.728 s/item) | [`neoverse-v2/out/thread-summary.txt`](neoverse-v2/out/thread-summary.txt) | Mean and sd over 3 repeats × 6 items |
| Neoverse-V2 warm means, items 2–6 (e.g. 2T: 539.6 ms, 46.72 tok/s, 1.265 s) | [`neoverse-v2/out/threads.csv`](neoverse-v2/out/threads.csv) | Mean of rows with `id != kyc-sms` for each thread count |
| Neoverse-V2 KleidiAI share: 54.17% of sampled CPU time in `kai_*` | [`neoverse-v2/out/perf-flat.txt`](neoverse-v2/out/perf-flat.txt), call graphs in [`perf-report.txt`](neoverse-v2/out/perf-report.txt) | Sum the `kai_*` rows |
| Neoverse-V2 kernel-level offline run (`unshare -n`) | [`neoverse-v2/out/offline-proof.txt`](neoverse-v2/out/offline-proof.txt), [`offline.jsonl`](neoverse-v2/out/offline.jsonl) | `lo DOWN`, curl exit 6, DNS exit 2, TCP `Network is unreachable`, then 6/6 explanations |
| Model hashes, CPU and package versions on V2 | [`neoverse-v2/out/hashes.txt`](neoverse-v2/out/hashes.txt), [`env.txt`](neoverse-v2/out/env.txt), [`kleidi-config.txt`](neoverse-v2/out/kleidi-config.txt) | |

## Caveats carried with the data

- S23 run 8 used an APK built before PR #41 and PR #43, so two explanations show bugs that were later fixed
  (a repeated sentence on the bank debit check, a stray question on the lookalike link check). Speed and
  memory are unaffected by those prompt fixes, but a fresh session on the final APK is still worth doing;
  see [`../s23-rtl-runbook.md`](../s23-rtl-runbook.md).
- S23 numbers are what the app shows on its stats card (measured in-app with `SystemClock` and
  `Debug.getPss()`), not an external profiler. The warm-2 stats card was not expanded.
- Neoverse-V2 ran on one rented 8-vCPU box, 3 cold-process repeats per thread count, on the 6 visible
  demo items only. `perf.data` binaries and pip/apt install logs were left out of the repo.
- No hidden or challenge data was used for any of these runs.
