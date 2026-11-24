# Prahari Android Device Benchmark Summary

- **Device:** `samsung SM-S911B` (SoC `SM8550`, Android `14`, ABI `arm64-v8a,armeabi-v7a,armeabi`)
- **Arm ISA flags:** `asimd, asimddp, asimdhp, bf16, fphp, i8mm`
- **Source:** Live adb benchmark run
- **dumpsys meminfo snapshot:** TOTAL PSS `1,783,754 KiB` (1741.9 MiB), TOTAL RSS `1,892,276 KiB` (1847.9 MiB), Native Heap PSS `1,572,176 KiB`

| Check | Status | Airplane | Gating | Llama skipped | Detector (ms) | Prompt tokens | Prefill (ms) | Prefill (tok/s) | TTFT (ms) | Decode (tok/s) | Total (s) | App PSS after check (MB) | Highest sampled PSS (MiB) |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `kyc-cold` | ok | no | all | no | 424.521 | 145 | 1057.0 | 137.181 | 1057.0 | 34.356 | 2.953 | 1701.7 | 1795.3 |
| `kyc-warm-1` | ok | no | all | no | 15.848 | 145 | 879.0 | 164.96 | 879.0 | 31.927 | 1.877 | 1711.9 | 1715.9 |
| `kyc-warm-2` | ok | no | all | no | 12.386 | 145 | 879.0 | 164.96 | 879.0 | 32.98 | 1.836 | 1713.4 | 1718.5 |
| `bill-benign` | ok | no | all | no | 63.267 | 140 | 906.0 | 154.525 | 906.0 | 32.941 | 1.914 | 1714.7 | 1718.3 |
| `official-link` | ok | no | all | no | 210.709 | 129 | 830.0 | 155.422 | 830.0 | 30.43 | 2.053 | 1747.4 | 1756.7 |
| `lookalike-link` | detector-fallback | no | all | no | 0.926 | 63 | 438.0 | 143.836 | 438.0 | 33.973 | 5.001 | 1750.1 | 1754.0 |
| `kyc-cold-gated` | ok | no | flagged-only | no | 511.252 | 145 | 1731.0 | 83.767 | 1731.0 | 23.333 | 4.104 | 1691.7 | 1699.3 |
| `kyc-warm-1-gated` | ok | no | flagged-only | no | 15.944 | 145 | 1299.0 | 111.624 | 1299.0 | 25.045 | 2.573 | 1706.2 | 1711.1 |
| `kyc-warm-2-gated` | ok | no | flagged-only | no | 15.911 | 145 | 1251.0 | 115.907 | 1251.0 | 22.709 | 2.648 | 1705.7 | 1709.3 |
| `bill-benign-gated` | ok | no | flagged-only | yes | 84.612 | — | — | — | — | — | 0.186 | 1706.7 | 1709.8 |
| `official-link-gated` | ok | no | flagged-only | yes | 253.768 | — | — | — | — | — | 0.312 | 1755.1 | 1755.5 |
| `lookalike-link-gated` | detector-fallback | no | flagged-only | no | 1.207 | 63 | 551.0 | 114.338 | 551.0 | 27.414 | 6.399 | 1739.7 | 1744.0 |

| Gating | Checks | Llama skipped | Median total, skipped (s) | Median total, Llama ran (s) |
|---|---:|---:|---:|---:|
| `all` | 5 | 0 | — | 1.914 |
| `flagged-only` | 5 | 2 | 0.249 | 2.648 |
