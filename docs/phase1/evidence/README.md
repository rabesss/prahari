# Raw measurement evidence (Phase 1)

Primary records behind the hardware and holdout numbers in [report.md](../report.md) and [EVIDENCE.md](../EVIDENCE.md).

| Folder | What it holds | Report source |
|:--|:--|:--|
| [galaxy-s23/](galaxy-s23/) | Samsung Galaxy S23 (`SM-S911B`, Snapdragon 8 Gen 2, Android 14) run via Samsung Remote Test Lab, 23 Nov 2026: run report, `dumpsys meminfo`, device properties and CPU flags, on-device SHA-256 of the model files, and the visible text of every stats screen (from `uiautomator` dumps). Screenshots are in [`../img/s23-*.png`](../img/). | [S9] |
| [neoverse-v2/](neoverse-v2/) | Arm Neoverse-V2 (8 vCPU, Debian 12) run, 23 Nov 2026: run report, environment, `perf` reports (KleidiAI `kai_*` share), thread-scaling CSV and per-run JSONL/logs, `unshare -n` offline transcript, KleidiAI switch search, detector test output. | [S10] |
| [sealed-holdout/](sealed-holdout/) | Aggregate conservative scores of the 184-item sealed holdout for PR #21, `gen51`, `main` before PR #42 and `main` at `1eb8916`. Item texts and per-item predictions are not published. | [S8], [S11] |

The S23 numbers are app-displayed, not separately instrumented. The cloud box's hostname is replaced with `<box>`. Raw `perf.data` and the device logcat are not included.
