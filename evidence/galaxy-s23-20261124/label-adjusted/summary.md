# Prahari Android Device Benchmark Summary

- **Device:** `samsung SM-S911B` (SoC `SM8550`, Android `14`, ABI `arm64-v8a,armeabi-v7a,armeabi`)
- **Arm ISA flags:** `asimd, asimddp, asimdhp, bf16, fphp, i8mm`
- **Source:** Live adb benchmark run
- **dumpsys meminfo snapshot:** TOTAL PSS `1,776,499 KiB` (1734.9 MiB), TOTAL RSS `1,893,516 KiB` (1849.1 MiB), Native Heap PSS `1,572,880 KiB`

| Check | Status | Airplane | Detector (ms) | TTFT (ms) | Decode (tok/s) | Total (s) | App PSS after check (MB) | Highest sampled PSS (MiB) |
|---|---|---|---:|---:|---:|---:|---:|---:|
| `kyc-cold` | ok | no | 447.0 | 1780.0 | 23.0 | 3.97 | 1678.1 | 1774.1 |
| `kyc-warm-1` | ok | no | 45.0 | 1520.0 | 22.3 | 2.95 | 1689.7 | 1693.2 |
| `kyc-warm-2` | ok | no | 16.0 | 1510.0 | 22.6 | 2.9 | 1689.8 | 1692.7 |
| `kyc-warm-3` | ok | no | 25.0 | 1460.0 | 22.5 | 2.83 | 1691.5 | 1698.1 |
| `bill-benign` | ok | no | 76.0 | 1210.0 | 26.2 | 2.49 | 1693.1 | 1697.6 |
| `bank-debit` | ok | no | 30.0 | 1640.0 | 21.7 | 3.15 | 1694.9 | 1697.4 |
| `lookalike-link` | timeout | no | 244.0 | — | — | 5.86 | 1727.4 | 1746.2 |
| `official-link` | ok | no | 0.0 | 1040.0 | 27.2 | 2.15 | 1733.5 | 1737.6 |
| `port-scan` | ok | no | 6.0 | 1400.0 | 22.5 | 3.19 | 1734.7 | 1738.5 |
| `kyc-airplane` | ok | yes | 19.0 | 1450.0 | 22.9 | 2.8 | 1733.7 | 1736.5 |
