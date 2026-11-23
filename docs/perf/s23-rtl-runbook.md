# Samsung Galaxy S23 Remote Test Lab — 30-Minute Session Runbook

This runbook tells the owner (1) what physical-phone evidence is **already captured and verified**
from Samsung Remote Test Lab (RTL) run 8 (`2026-11-23`), (2) what exact gaps a **single fresh
30-minute S23 session** closes, and (3) the turnkey commands to execute it cleanly inside 20 minutes.

## 1. Already Captured vs What a Fresh 30-Min Session Adds

### Already verified & traceable (RTL run 8, `SM-S911B`, 2026-11-23)

- Real physical Armv9 phone: **Samsung Galaxy S23 (`SM-S911B`)**, Qualcomm SM8550 (Snapdragon 8 Gen 2), Android 14, `arm64-v8a`, ISA flags `asimddp`, `i8mm`, `bf16`.
- Device-side SHA-256 verification of `Llama-3.2-1B-Instruct-QLORA_INT4_EO8.pte` (`ab7b7ebf…`) and `tokenizer.model` (`82e9d319…`).
- 7 complete checks + 1 partial check: warm KYC **6 ms detector**, **510 ms TTFT** (warm 2: 499 ms, warm 3: 508 ms), **43.4 tok/s** decode (warm 3: 42.9 tok/s), **1.20–1.21 s** total per check.
- **Airplane mode verified** (`airplane_mode_on=1`): **8 ms** detector, **657 ms** TTFT, **39.0 tok/s**, **1.42 s** total, plus in-app `SecurityException` offline proof.
- `dumpsys meminfo` snapshot after KYC: **1,703.9 MiB TOTAL PSS** (`1,744,842 KiB`, Native Heap `1,529.4 MiB`), **1,823.6 MiB TOTAL RSS** (`1,867,396 KiB`).

### Gaps a fresh 30-minute S23 session closes (recommended before final submission)

1. **Final merged APK verification & clean screenshots/video:** Run 8 tested the pre-PR#41/43 APK (which had the repeated sentence on bank debit and `"Can I help you with something else?"` on lookalike link — both fixed in PR #41 — and lacked the PR #43 Hindi toggle, share sheet, read-aloud, QR, and history features). The submission form also requires a **public 2-minute real-time demo video on physical Arm hardware**.
2. **Continuous peak PSS/RSS & memory-growth check:** Run 8 showed app post-check PSS drifting from `1,692.4 MB` → `1,781.2 MB` (`+88.8 MB` over 7 checks) and only captured one post-KYC `dumpsys meminfo`. Our `bench/perf/run_s23_rtl.sh` polls `dumpsys meminfo` every **500 ms during generation** to capture true peak PSS/RSS and checks stability across 10 consecutive checks.
3. **Complete benign + thermal matrix:** Run 8 did not capture a `NO RISK FOUND` check (`Bill reminder` / `Official link`), left warm-2 collapsed, and did not record battery temperature (`dumpsys battery`) before/after to check whether the `43.4 → 38.6 tok/s` drift across checks 2–7 was thermal throttling. `run_s23_rtl.sh` logs all 10 checks + before/after battery temperature automatically.

## 2. Pre-Session Checklist (Do Before Clicking "Start" on RTL)

Run these locally on your machine *before* burning RTL minutes:

```sh
# 1. Confirm latest arm64 APK from GitHub Actions `Android spike` on `main` (after final PRs merge)
ls -lh /var/tmp/prahari-final-v2/prahari-android-arm64.apk \
       /var/tmp/prahari-model/Llama-3.2-1B-Instruct-QLORA_INT4_EO8.pte \
       /var/tmp/prahari-model/tokenizer.model

# 2. Verify local SHA-256 digests match pinned values (ab7b7ebf... and 82e9d319...)
sha256sum /var/tmp/prahari-model/Llama-3.2-1B-Instruct-QLORA_INT4_EO8.pte \
          /var/tmp/prahari-model/tokenizer.model

# 3. Ensure TCP port 8888 is FREE (Samsung RDB helper binds localhost:8888)
ss -tlnp | grep ':8888' || echo "Port 8888 is free"
```

If port 8888 is in use (e.g., `hindsight-omp` on Arch), stop that service temporarily and restart
it after the RTL session finishes.

## 3. Exact 30-Minute Execution Plan

| Minute | Step | Command / Action |
|---|---|---|
| **0:00 – 4:00** | Reserve phone & open RDB | Open `https://developer.samsung.com/remote-test-lab`, sign in, reserve a **Galaxy S23 / S23 FE (Noida, Android 14, arm64)** for 30 min. Start the Samsung RDB client (`./rdb`), click **Remote Debug Bridge → Connect** in the web client, and tap **Allow** on the phone's USB debugging dialog. |
| **4:00 – 5:00** | Confirm ADB serial | Run `adb devices -l` and export the exact reported serial (never guess the port):<br>`export ANDROID_SERIAL=localhost:<PORT>` |
| **5:00 – 19:00** | Run turnkey benchmark script | Run the automated script (installs APK, verifies zero `INTERNET` permission, pushes `.pte` + `tokenizer.model`, verifies device SHA-256, runs all 10 checks incl. 3× warm KYC, benign Bill reminder & Official link, Bank debit, Lookalike link, Port scan, and Airplane mode, polls peak PSS/RSS at 500 ms, captures screenshots + XML + `dumpsys battery`):<br><br>`UNINSTALL_ON_EXIT=0 APK=/path/to/latest-arm64.apk ./bench/perf/run_s23_rtl.sh` |
| **19:00 – 25:00** | Capture 2-min demo video & offline proof | With the app still installed (`UNINSTALL_ON_EXIT=0`), record real-time phone clips (max 180 s per `screenrecord`):<br>1. `adb -s "$ANDROID_SERIAL" shell screenrecord --bit-rate 8000000 /sdcard/prahari-demo.mp4` (in a second terminal while tapping: **Prove it's offline** → **KYC scam SMS** → **Hindi toggle** → **Bank debit** → **Port scan** → **Airplane mode check**).<br>2. Stop recording (`Ctrl-C`), wait 2 s, pull: `adb -s "$ANDROID_SERIAL" pull /sdcard/prahari-demo.mp4 /var/tmp/prahari-rtl-latest/`<br>3. Delete video from phone: `adb -s "$ANDROID_SERIAL" shell rm -f /sdcard/prahari-demo.mp4` |
| **25:00 – 28:00** | Clean up phone | Restore airplane mode off, uninstall app & delete staged model files:<br>`adb -s "$ANDROID_SERIAL" shell cmd connectivity airplane-mode disable`<br>`adb -s "$ANDROID_SERIAL" uninstall in.prahari.app`<br>`adb -s "$ANDROID_SERIAL" shell rm -rf /sdcard/Android/data/in.prahari.app` |
| **28:00 – 30:00** | Close RTL & merge summary | Click **End Session** in the Samsung RTL web client, stop `./rdb`, restart any local port-8888 service, and inspect `/var/tmp/prahari-rtl-session-*/summary.md` and `results.json`. |

## 4. Operational Notes Learned from RTL Run 8

- **Do NOT run `adb shell svc power stayon true`:** On Samsung RTL run 8, that command dropped the
  RDB bridge immediately. `run_s23_rtl.sh` uses `settings put system screen_off_timeout 1800000`
  (30 minutes) instead, which worked reliably without disconnecting RDB.
- **Model transfer time:** Pushing the `1.100 GiB` `.pte` over RTL RDB typically takes ~3–5 minutes
  depending on Noida link speed. Keep `adb push` inside the script (timeout set to 600 s).
- **Zero hidden data:** All checks run only the app's built-in visible samples. Never copy hidden
  evaluation sets onto a shared Remote Test Lab device.
- **Combining with Arm Linux numbers:** After the session finishes, regenerate a single combined
  comparison table via:
  ```sh
  python3 bench/perf/summarize.py /var/tmp/prahari-rtl-session-*/results.json
  ```
