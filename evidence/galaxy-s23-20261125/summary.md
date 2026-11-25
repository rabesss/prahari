# Galaxy S23 RTL attempt — 25 Nov 2026

**Incomplete.** The phone was a Galaxy S23 `SM-S911B`, Qualcomm `SM8550`, Android 14 (see [device.txt](device.txt)). The pinned APK and model were verified on the host, but transfer to the device did not complete in time. ADB install timed out, and Samsung's web transfer also stalled. No app feature was exercised in this attempt. These are not feature failures or passes. See [log.md](log.md) for the sequence and [packages.txt](packages.txt) for the package inventory.

| Feature | Input | Expected | Observed | Status | Screenshot |
|---|---|---|---|---|---|
| #67 sender check | Debit/OTP message with mobile, registered-looking header, and empty sender | Personal sender raises risk; header and empty sender do not | App unavailable during staging | Not tested | None |
| #70 typosquat and APK | Lookalike, direct APK, official domain | Flag the first two, not the official domain for typosquat | App unavailable during staging | Not tested | None |
| #64 report and family share | Flagged result | Mask 4+ digit runs, defang links, open safe share text | App unavailable during staging | Not tested | None |
| #66 screen-sharing banner | Bank/KYC scam; package inventory | Banner only when relevant app is installed | All eight named packages absent; banner itself not exercised | Not tested | None |
| Regression and demo | KYC scam, benign sample, offline and Hindi flow | Expected verdicts and real-time Llama demo | App and model staging incomplete; no footage | Not tested | None |

No claim is made about the requested features on this device. No real-time demo video was recorded.
