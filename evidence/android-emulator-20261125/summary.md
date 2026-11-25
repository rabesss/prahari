# Android emulator run of the #64, #66, #67 and #70 features (25 Nov 2026)

On 25 Nov both Galaxy S23 Remote Test Lab sessions failed before the app could be installed
([../galaxy-s23-20261125/summary.md](../galaxy-s23-20261125/summary.md)). The same features were
then run on an Android 14 emulator instead. The emulator ran the **same APK that was measured on the
S23 on 24 Nov**: `app-debug.apk` from CI run 45398563324 (commit `5b59ee2`), SHA-256 `88f6a532…`.
No Android or detector code has changed since that commit.

**What this run shows, and what it doesn't.** The emulator is an x86_64 Android 14 image (Google
APIs, `sdk_gphone64_x86_64`). It runs the APK's arm64-v8a code (Chaquopy Python and native
libraries) through Android's ARM translation layer (`libndk_translation`). That makes this a
functional check of the app's screens and logic on Android 14. It is **not** an Arm hardware result,
and its timings mean nothing for performance. The S23 numbers in
[`docs/perf/s23-gating-20261124.md`](../../docs/perf/s23-gating-20261124.md) remain the hardware
evidence. The Llama model was not copied to the emulator, so every result shows the detector's verdict,
evidence and steps. On results where Llama would run (DANGEROUS, SUSPICIOUS, CHECK THIS ALERT), the
explanation area says that the model files are missing, as designed. NO RISK results skip Llama by
default (flagged-only gating, PR #68) and show the detector's fixed text instead. None of these features depends on Llama. The APK requests no `INTERNET` permission
([device.txt](device.txt)).

All inputs are synthetic test messages. `9000000000`/`9000000001` are placeholder numbers. For each
#67 row, `*-input.*` captures the filled-in message and sender fields just before the check. An empty
sender shows only the field's placeholder (`AX-HDFCBK-S or 98XXXXXXXX`), which UI Automator reports
as the field text.

| Feature | Input | Expected (report.md) | Observed | Result | Captures |
|---|---|---|---|---|---|
| #67 sender check: personal number | SMS "Your SBI account will be blocked today. Update KYC now and share the OTP…", sender `9000000000` | At least SUSPICIOUS; first evidence line says banks send from registered sender IDs | DANGEROUS; first line "Banks and government send SMS from registered sender IDs like XX-ABCDEF, not personal mobile numbers." | Pass | `emu-67a-personal-{input,top,mid}.*` |
| #67: DLT header | Same SMS, sender `AX-SBIINB-S` | No extra risk, no "verified" wording | DANGEROUS (from the message itself); no sender line, no "verified" text | Pass | `emu-67b-dlt-{input,top,mid}.*` |
| #67: empty sender | Same SMS, no sender | Unchanged | DANGEROUS; no sender line | Pass | `emu-67c-empty-{input,top,mid}.*` |
| #67: raises risk only when warranted | Harmless chat "Hi, reached home safely…", sender `9000000000` | Not raised | NO RISK FOUND | Pass | `emu-67d-benign-personal-{input,top,mid}.*` |
| #67: raise on a bank alert | "Rs 2000 debited from your A/c XX1234…", no sender, then sender `9000000000` | Personal number raises a debit alert to at least SUSPICIOUS | No sender: CHECK THIS ALERT. Personal number: SUSPICIOUS, first line about registered sender IDs | Pass | `emu-67e-debit-empty-{input,top,mid}.*`, `emu-67f-debit-personal-{input,top,mid}.*` |
| #70 typosquat | SMS with `https://sbi-online-in.com/redeem` | Flagged as a lookalike of an official name | DANGEROUS; "The domain sbi-online-in.com is a hyphenated lookalike of 'sbi'." | Pass | `emu-70a-typosquat-*` |
| #70 direct `.apk` link | Link mode `https://bescom-bills.in/download/bill-viewer.apk` | Flagged as a direct app download | DANGEROUS; only signal "The link points straight to an Android app file (.apk), which installs outside the Play Store" | Pass | `emu-70d-apk-link-*` |
| #70 `.apk` link inside an SMS | SMS "Install the new PM Kisan app…: https://pmkisan-update.top/PMKisan.apk" | Flagged | DANGEROUS (remote-access app scam). The card lists its 2 strongest signals ("install" request, `.top` domain); the `.apk` signal is not among the two shown | Pass (verdict); see note | `emu-70b-apk-*` |
| #70 official domain | SMS with `https://onlinesbi.sbi` | Not flagged as a typosquat | NO RISK FOUND | Pass | `emu-70c-official-*` |
| #64 Copy report | DANGEROUS SMS with account `12345678`, link `http://sbi-kyc-update.top/verify`, number `9000000001` | Report copied for the Chakshu form; preview hidden; 4+ digit runs masked; links defanged; nothing submitted | On the emulator: toast "Report copied. Paste it in the Chakshu form"; Android's clipboard preview shows only dots (sensitive flag); the on-screen evidence quote masks the account (`account •••••••• will be blocked`). The copied text itself could not be read back (see below). The report text the APK's packaged code produces for the same input is in [report-card-text.txt](report-card-text.txt) (Chakshu category, date, 3 evidence lines, `account ••••••••`, `hxxp://sbi-kyc-update[.]top/verify`) | Pass (copy action and preview on the emulator; text from the packaged code on the host) | `emu-64a-copy-toast.png`, `emu-64-result.*` |
| #64 Send to family | Same result | Share sheet with a short warning; no message body, sender or numbers; link as defanged domain | Android share sheet "Sharing text: Scam warning: I got a fake bank, KYC or bill payment message… Do not open this link: hxxp://sbi-kyc-update[.]top. If money is lost, call 1930 at once." Backed out; nothing sent | Pass | `emu-64c-share-sheet.*` |
| #66 screen-sharing banner | KYC/OTP scam with RustDesk 1.5.3 installed, then after uninstalling it | Amber note only while one of the 8 named apps is installed | Installed: amber note "A screen-sharing app (RustDesk) is installed. Scammers use these to watch your bank app…". Uninstalled: no note | Pass | `emu-66a-banner-top.*`, `emu-66b-no-banner.*` |

**About the report text.** The emulator copies its clipboard to and from the host, so pasting the
copied report back into the app did not work. The text in
[report-card-text.txt](report-card-text.txt) was produced by running the Python modules packaged
in this APK's `assets/chaquopy/app.imy` (the same `android/python` sources at `5b59ee2`, with the
APK's model files) on the host, for the same input and on the same day. The on-screen evidence
quote shows the same masking (`account •••••••• will be blocked`).

**Note on #70 inside an SMS.** The detector computes the `.apk` signal for any link to a `.apk`
file on a non-official host (`triage/rules.py`), so it was computed for this link too. An SMS result card shows only the strongest signals, though, and for this
message those were the install request and the `.top` domain. In Link mode the `.apk` signal is
shown on its own.

Captures: each `*.png` is an unedited screenshot, and the `*.xml` beside it is the UI Automator
dump of the same screen (`-top`/`-mid` are successive scroll positions).
