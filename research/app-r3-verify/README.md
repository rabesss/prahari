# App round 3: verification on an Android 14 emulator (24 Nov 2026)

Emulator: Android 14, x86_64, on a cloud box (instabox `android` template). Timings and memory on x86 are
not Arm numbers; the physical Galaxy S23 run of this build is pending (owner, Samsung Remote Test Lab,
docs/perf/s23-rtl-runbook.md). Builds: CI emulator APK from main 6b5e199 (round-3 app plus #46-#52), and
cursor/app-r3 at 365ecb2 for the font-scale and share-preview captures.

| Check | Result | File |
|---|---|---|
| Parcel scam shared from another app | Text pre-filled with "Shared text — review, then tap Check"; nothing runs until Check | 07-share-preview.png |
| Parcel scam result | DANGEROUS, 3 signals with defanged link quote, AI opening shown once plus a vetted fact | 02-parcel.png, 03-parcel-ai.png |
| Genuine SBI debit alert | Amber CHECK THIS ALERT | 04-bank.png |
| OTP notification (`... is 482910 ...`) | NO RISK, evidence quote masked `••••••`; the code appears 0 times in the UI dump | 02-otp.png, 03-otp-quotes.png |
| Official-channel message | NO RISK FOUND with "Still verify" | 05-listen.png |
| Listen with no offline voice installed | Toast "No offline voice installed"; no network voice used | 05-listen.png |
| UPI link `upi://pay?pa=cashback.refund99@ybl...` | DANGEROUS, UPI QR details card, no UPI app opened | 05-upi.png, 06-upi-b.png |
| KYC scam in Hindi mode | Hindi chrome, Hindi type line, fixed-text Hindi summary above the English AI paragraph | 07-kyc-hi.png, 09-kyc-hi-c.png |
| Font scale 2.0 | Home footer clears the nav bar; result wraps without clipping | 06-home-font2-bottom.png, 07/08-result-font2*.png |
| Network under Advanced | Collapsing Advanced returns to SMS | 14-adv-collapsed.png |
| History (off by default) | Off by default; switched on, a check is saved and is still listed after a force-stop and restart | 09-history-list.png, 11-history-on.png, 12-history-after-restart.png |
| Memory over 10 checks in one process | `dumpsys meminfo` TOTAL PSS after each check: 1,797,588 KB at check 1; 1,802,148 KB at check 2; 1,797,263 KB at check 10 (drift checks 2→10: −4.9 MB) | 10-meminfo.csv |

Not shown here: TalkBack focus order, QR photo decode from the picker, Call Guard on a device.
