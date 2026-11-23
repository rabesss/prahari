# Samsung RTL run 8 — real-device inference

Date: 2026-11-23, Asia/Kolkata. Samsung Galaxy S23 SM-S911B-IN4 in Noida, Android 14; ADB properties: SM-S911B, Samsung, Qualcomm SM8550, CPU ABI arm64-v8a (also armeabi-v7a, armeabi). See [device.txt](device.txt).

The app was installed by ADB and both transferred files matched their expected device-side SHA-256 hashes ([device-sha256.txt](device-sha256.txt)). Llama 3.2 1B INT4 produced explanations for KYC, bank debit alert, lookalike link, and port scan on this phone. The app reported ExecuTorch / XNNPACK and CPU ABI arm64-v8a on each expanded stats card. KYC was DANGEROUS, bank debit alert SUSPICIOUS, and the link and port scan DANGEROUS. The bank explanation repeated its opening sentence, and the link explanation included the unrelated phrase “Can I help you with something else?” These are visible generation-quality defects. These results demonstrate execution on this one device, not broad accuracy or performance across phones.

| Check | Detector | First token | Decode | Total | App memory |
|---|---:|---:|---:|---:|---:|
| KYC first | 255 ms | 664 ms | 42.6 tok/s | 2.00 s | 1692.4 MB |
| KYC warm 1 | 6 ms | 510 ms | 43.4 tok/s | 1.20 s | 1708.0 MB |
| KYC warm 2 | 6 ms | 499 ms | not captured | not captured | not captured |
| KYC warm 3 | 6 ms | 508 ms | 42.9 tok/s | 1.21 s | 1724.8 MB |
| Bank debit alert | 17 ms | 615 ms | 39.8 tok/s | 1.50 s | 1737.5 MB |
| Lookalike link | 183 ms | 594 ms | 39.1 tok/s | 3.53 s | 1781.2 MB |
| Port scan | 5 ms | 650 ms | 38.6 tok/s | 1.49 s | 1772.6 MB |
| KYC with airplane mode | 8 ms | 657 ms | 39.0 tok/s | 1.42 s | 1772.6 MB |

Numbers are app-displayed measurements, not independently instrumented benchmark measurements. The warm-2 card was not expanded before moving on, so only detector and first-token values were retained. Airplane mode was verified on (`airplane_mode_on=1`) before the final check, and off (`0`) after. [Airplane result](kyc-airplane-stats.png). The app's [offline proof](prove-offline.png) showed its attempted HTTPS request was blocked with a missing INTERNET permission SecurityException; this is evidence of Android's permission denial for that request, not a network capture of all activity.

Evidence: [home](home.png), [KYC top](kyc-top.png), [KYC stats](kyc-stats-full.png), [bank](bank-top.png), [bank stats](bank-stats.png), [link](link-top.png), [link stats](link-stats.png), [port scan](port-top.png), [port stats](port-stats.png), [logcat](logcat.txt), [memory dump](meminfo.txt). The dumpsys snapshot after KYC showed total PSS 1,744,842 KB and RSS 1,867,396 KB. XML files preserve the UI text and stats.

RDB first disconnected when `svc power stayon true` was attempted, so it was reconnected and that command omitted. The timeout setting was applied. The APK was successfully uninstalled and the package no longer appeared in `pm list packages`; airplane mode was disabled. The task's RDB helper was stopped, and ADB showed no devices.

**Session exit not verified:** the browser extension stopped accepting tab control with `Debugger unattached` while attempting to close the RTL session. The session was started for 30 minutes at approximately 18:30–18:31 IST, so it should expire automatically, but this report does not assert that it was returned early or that automatic expiry was observed. No other browser, CDP connection or service was used.
