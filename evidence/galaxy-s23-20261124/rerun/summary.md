# Prahari Android Device Benchmark Summary

- **Device:** `samsung SM-S911B` (SoC `SM8550`, Android `14`, ABI `arm64-v8a,armeabi-v7a,armeabi`)
- **Arm ISA flags:** `asimd, asimddp, asimdhp, bf16, fphp, i8mm`
- **Source:** Live adb benchmark run
- **dumpsys meminfo snapshot:** TOTAL PSS `1,776,519 KiB` (1734.9 MiB), TOTAL RSS `1,834,544 KiB` (1791.5 MiB), Native Heap PSS `1,514,752 KiB`

| Check | Status | Airplane | Detector (ms) | TTFT (ms) | Decode (tok/s) | Total (s) | App PSS after check (MB) | Highest sampled PSS (MiB) |
|---|---|---|---:|---:|---:|---:|---:|---:|
| `kyc-cold` | ok | no | 434.0 | 1620.0 | 25.6 | 3.85 | 1684.2 | 1723.6 |
| `kyc-warm-1` | ok | no | 16.0 | 1520.0 | 21.5 | 2.96 | 1698.3 | 1702.4 |
| `kyc-warm-2` | ok | no | 16.0 | 1420.0 | 21.3 | 2.9 | 1698.3 | 1702.5 |
| `kyc-warm-3` | ok | no | 16.0 | 1480.0 | 22.6 | 2.86 | 1698.0 | 1700.8 |
| `bill-benign` | ok | no | 80.0 | 1360.0 | 22.9 | 2.77 | 1700.1 | 1702.6 |
| `bank-debit` | no-sample-chip | no | — | — | — | — | — | — |
| `lookalike-link` | timeout | no | 276.0 | — | — | 7.38 | 1732.8 | 1754.0 |
| `official-link` | no-sample-chip | no | — | — | — | — | — | — |
| `port-scan` | no-sample-chip | no | — | — | — | — | — | — |
| `kyc-airplane` | ok | yes | 14.0 | 1280.0 | 22.7 | 2.64 | 1734.1 | 1737.0 |
