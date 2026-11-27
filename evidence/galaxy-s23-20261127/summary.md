# Samsung Galaxy S23 phone follow-up — 27 November 2026

## Build and setup

- Samsung Galaxy S23 phone, `SM-S911B`, Qualcomm `SM8550`, Android 14, arm64.
- Debug APK from Android CI run `45945461952`, commit `3b7575c2165289b099d9b0bf9184a294b6ab6082`; local SHA-256 `54815f5074c39173a001a028e33d17132d7786f7ff43acfee2bbad26af2259bd`.
- On-device model SHA-256 `ab7b7ebf97421c7770ad97d4abfdf8650a7d9f9dc1ce9a0c4663d49f7b7a08ac`; tokenizer SHA-256 `82e9d31979e92ab929cd544440f129d9ecd797b69e327f80f17e1c50d5551b55`. The model was assembled from 18 individually verified chunks.
- Airplane mode was checked as enabled during the checks. The permissions dump records no `android.permission.INTERNET` request; the app's separate HTTPS GET to example.com produced a `SecurityException` and was blocked. This is evidence of that request, not a complete network audit.

A previous preload attempt on this phone logged a 21 ms error with the model owned by shell at mode `0660`. After a same-hash copy was placed at mode `0644`, and the app was force-stopped and restarted, preload logged `ready` in 6,410 ms. The tokenizer was also mode `0644`. This phone result supports the file-access diagnosis; the replacement and restart were performed together, so they do not isolate the permission change as a controlled experiment. An earlier separate emulator reproduction also reached ready after changing permissions and restarting.

## Timing

The KYC sample was checked in all-items mode with the model preloaded and airplane mode on. The first check after a fresh app start is called cold here; its `total_ms` excludes the separately reported preload. The first three warm checks were captured by the harness; after a phone connection interruption, seven further warm checks were run manually in the same app process. All ten have `gating=all`, `llama_skipped=false`, no error and the same 148 prompt tokens. Values are app telemetry, not independent wall-clock measurements. P90 is the nearest-rank value.

| Measurement | Warm n | Median | Min–max | P90 |
|---|---:|---:|---:|---:|
| Total | 10 | 1,332.5 ms | 1,311–1,356 ms | 1,355 ms |
| First token | 10 | 590 ms | 574–624 ms | 624 ms |
| Decode | 10 | 42.71 tokens/s | 42.34–43.61 tokens/s | 43.61 tokens/s |

The fresh-start check took 2,141 ms total, 712 ms to first token, and 41.73 tokens/s, after a 2,543 ms preload. Battery temperature was 32.9 °C before this benchmark and 35.5 °C after the ten warm checks. `benchmark-telemetry.jsonl` preserves the app records. `benchmark-partial.json` records the interrupted harness attempt and its incomplete rows; the seven later results are in the same telemetry session and are included in the table. The separate hero check took 4,613 ms with 3,144 ms to first token; its generated sentence was replaced by a safety step, as the screen indicates.

## CPU profile

A 30-second `simpleperf` CPU-cycles recording covered three further KYC checks and produced 71,536 samples, with zero lost. The DSO report attributes 90.43% of sampled CPU-cycle weight to `libexecutorch.so`, 2.07% to kernel symbols, 1.99% to `libart.so`, 1.09% to `libhwui.so`, 1.03% to `libc.so`, 0.77% to `libm.so`, and 0.72% to `libpython3.10.so`. This is a sample-weighted profile for the recording, including time between checks, not a per-check instruction count.

The shipped library has a dynamic symbol table but no full symbol table. The report resolves its hot locations as offsets, not `kai_*` or XNNPACK symbols; `nm -D` and `strings` found no `kai_` names in the shipped arm64 libraries. Therefore neither a KleidiAI share nor a separate XNNPACK share can be established from this profile. The XNNPACK name appears in library strings, which alone does not measure its execution. Some Python extension symbols also could not be read. `profile-dso.txt`, `profile-report.txt`, and `profile-telemetry.jsonl` retain the reports and check records; installation-specific APK path components were removed from the text reports.

## Recordings

The H.264 clips retain real-time timing; the copies here are scaled and compressed. The original recordings are retained for video editing.

- `permissions.mp4` (7.02 s): Android permissions screen, airplane icon visible. Android's runtime-permission screen alone does not establish the requested-permissions claim; `permissions-dumpsys.txt` provides that evidence.
- `hero.mp4` (83.23 s): one continuous take selecting the synthetic KYC message in another app, opening the Android share sheet, selecting Prahari, checking the message, showing the verdict and steps, and scrolling to the completed explanation. The final frame shows the safety replacement: “Don't act on this message; check your account only in your bank's official app.”
- `sender.mp4` (29.19 s original): synthetic bank-debit SMS from `9000000000`; the result is SUSPICIOUS and warns about a personal mobile sender. The AI sentence was replaced by a safety step.
- `link.mp4` (21.52 s original): `http://sbi-online-in.com/redeem` returns DANGEROUS and displays the completed on-device explanation.
- `share.mp4` (14.56 s original): Copy report, the copied confirmation, and the family-warning share sheet. Nothing was sent.
- `rustdesk.mp4` (27.49 s original): KYC result with RustDesk installed and the screen-sharing warning visible.
- `offline.mp4` (19.77 s): the app's blocked HTTPS request and `SecurityException`.

The first attempts to record the hero take were interrupted or incomplete; they are retained with the original recordings, but are not used as the completed take. Phone connection interruptions also stopped an initial benchmark run; incomplete rows are not included in the timing statistics.
