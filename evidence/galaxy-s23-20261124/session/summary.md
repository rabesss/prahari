# Prahari Android Device Benchmark Summary

- **Device:** `samsung SM-S911B` (SoC `SM8550`, Android `14`, ABI `arm64-v8a,armeabi-v7a,armeabi`)
- **Arm ISA flags:** `asimd, asimddp, asimdhp, bf16, fphp, i8mm`
- **Source:** Live adb benchmark run
- **dumpsys meminfo snapshot:** TOTAL PSS `1,394,613 KiB` (1361.9 MiB), TOTAL RSS `1,505,168 KiB` (1469.9 MiB), Native Heap PSS `1,344,796 KiB`

| Check | Status | Airplane | Detector (ms) | TTFT (ms) | Decode (tok/s) | Total (s) | App PSS after check (MB) | Highest sampled PSS (MiB) |
|---|---|---|---:|---:|---:|---:|---:|---:|
| `kyc-cold` | no-sample-chip | no | — | — | — | — | — | — |
| `kyc-warm-1` | no-sample-chip | no | — | — | — | — | — | — |
| `kyc-warm-2` | no-sample-chip | no | — | — | — | — | — | — |
| `kyc-warm-3` | no-sample-chip | no | — | — | — | — | — | — |
| `bill-benign` | no-sample-chip | no | — | — | — | — | — | — |
| `bank-debit` | no-sample-chip | no | — | — | — | — | — | — |
| `lookalike-link` | no-sample-chip | no | — | — | — | — | — | — |
| `official-link` | no-sample-chip | no | — | — | — | — | — | — |
| `port-scan` | no-sample-chip | no | — | — | — | — | — | — |
| `kyc-airplane` | no-sample-chip | yes | — | — | — | — | — | — |
