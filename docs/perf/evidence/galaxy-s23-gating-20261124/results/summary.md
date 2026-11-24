# Prahari Android Device Benchmark Summary

- **Device:** `samsung SM-S911B` (SoC `SM8550`, Android `14`, ABI `arm64-v8a,armeabi-v7a,armeabi`)
- **Arm ISA flags:** `asimd, asimddp, asimdhp, bf16, fphp, i8mm`
- **Source:** Live adb benchmark run

| Check | Status | Airplane | Gating | Llama skipped | Detector (ms) | Prompt tokens | Prefill (ms) | Prefill (tok/s) | TTFT (ms) | Decode (tok/s) | Total (s) | App PSS after check (MB) | Highest sampled PSS (MiB) |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `kyc-cold` | timeout | no | all | — | — | — | — | — | — | — | — | — | 1409.7 |
| `kyc-warm-1` | no-sample-chip | no | — | — | — | — | — | — | — | — | — | — | — |
| `kyc-warm-2` | no-sample-chip | no | — | — | — | — | — | — | — | — | — | — | — |
| `bill-benign` | no-sample-chip | no | — | — | — | — | — | — | — | — | — | — | — |
| `official-link` | no-sample-chip | no | — | — | — | — | — | — | — | — | — | — | — |
| `lookalike-link` | no-sample-chip | no | — | — | — | — | — | — | — | — | — | — | — |
| `kyc-cold-gated` | error: RuntimeError | no | flagged-only | — | — | — | — | — | — | — | — | — | — |
| `kyc-warm-1-gated` | error: RuntimeError | no | flagged-only | — | — | — | — | — | — | — | — | — | — |
| `kyc-warm-2-gated` | error: RuntimeError | no | flagged-only | — | — | — | — | — | — | — | — | — | — |
| `bill-benign-gated` | error: RuntimeError | no | flagged-only | — | — | — | — | — | — | — | — | — | — |
| `official-link-gated` | error: RuntimeError | no | flagged-only | — | — | — | — | — | — | — | — | — | — |
| `lookalike-link-gated` | error: RuntimeError | no | flagged-only | — | — | — | — | — | — | — | — | — | — |
