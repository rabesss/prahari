# Prahari — 2-Minute Phase 1 Demo Video Production Guide

- **Form requirements:** **PUBLIC** 2-minute video (`<= 2:00`), **1080p (1920×1080)**, **16:9**, **MP4**, clearly showcasing the **real-time functioning of Prahari on target Arm hardware**.
- **Core PS3 mentor guidance covered on camera:**
  1. Physical Arm hardware live (Samsung Galaxy S23 `SM-S911B`, `arm64-v8a` via Samsung Remote Test Lab) — not an x86 emulator.
  2. Real offline proof: **Airplane Mode ON (`✈`)** + live Android **`SecurityException`** (`NO INTERNET` permission).
  3. Legitimate bank/OTP notices handled carefully (not blindly screamed as malicious).
  4. **Llama 3.2 1B via ExecuTorch** generating live explanations on-device (~1.2–1.5 s/check on S23).
  5. Complete end-to-end scenario on phone + real Arm Linux CLI (`--demo` / `bin/monitor`) & KleidiAI profiling evidence.

---

## 1. Pre-flight setup (do BEFORE hitting Record)

### A. Physical Samsung Galaxy S23 (Samsung Remote Test Lab)
1. Reserve a **Samsung Galaxy S23 (`SM-S911B`, Android 14, `arm64-v8a`)** in Samsung Remote Test Lab (30+ min slot so it won't expire mid-take).
2. Start the RTL Remote Debug Bridge (`./rdb`) and connect via **Remote Debug Bridge → Connect** in the RTL browser tab. Approve USB debugging on the phone screen.
3. Verify device identity and set `ANDROID_SERIAL` from `adb devices -l`:
   ```sh
   adb devices -l
   export ANDROID_SERIAL="localhost:<PORT>"
   adb shell getprop ro.product.model
   adb shell getprop ro.product.cpu.abilist
   adb shell getprop ro.build.version.release
   ```
   Expected: `SM-S911B`, `arm64-v8a,...`, `14`.
4. Download the **latest green `arm64-v8a` APK** from GitHub Actions (`prahari-debug-apk` from `main` after final PRs merge), install, and stage the verified Llama 3.2 1B model + tokenizer:
   ```sh
   adb install -r app-debug.apk
   adb shell am start -n in.prahari.app/.MainActivity
   adb shell mkdir -p /sdcard/Android/data/in.prahari.app/files
   adb push /path/to/Llama-3.2-1B-Instruct-QLORA_INT4_EO8.pte /sdcard/Android/data/in.prahari.app/files/
   adb push /path/to/tokenizer.model /sdcard/Android/data/in.prahari.app/files/
   adb shell sha256sum /sdcard/Android/data/in.prahari.app/files/Llama-3.2-1B-Instruct-QLORA_INT4_EO8.pte \
                       /sdcard/Android/data/in.prahari.app/files/tokenizer.model
   ```
   Confirm the exact SHA-256 digests:
   - `Llama-3.2-1B-Instruct-QLORA_INT4_EO8.pte` SHA-256: `ab7b7ebf97421c7770ad97d4abfdf8650a7d9f9dc1ce9a0c4663d49f7b7a08ac`
   - `tokenizer.model` SHA-256: `82e9d31979e92ab929cd544440f129d9ecd797b69e327f80f17e1c50d5551b55`
5. **Warm up once before recording** (run KYC sample once so the OS page cache and model load are warm, giving ~1.2–1.4 s live checks during the 2-minute take; return to Home).
6. **Turn Airplane Mode ON** (either tap the Quick Settings tile on screen or run `adb shell cmd connectivity airplane-mode enable` and verify `adb shell settings get global airplane_mode_on` returns `1`). Confirm the **airplane icon (`✈`)** is clearly visible in the S23 status bar! *(Note: Samsung RTL stays connected over USB/RDB even in airplane mode; do not run `svc power stayon true` as it can drop RDB — set display timeout to 10 minutes via Settings instead.)*

### B. Arm Linux terminal clip (recorded separately and spliced at 1:18–1:44)
Prepare a clean 1080p dark terminal (16–18 pt JetBrains Mono, 16:9 window) on your Arm Linux host (`aarch64`, e.g., Oracle Neoverse-N1 or Neoverse-V2) with the repo checked out at the final submission commit and `HC_PY` / `HC_MODEL_REGISTRY` exported:
```sh
uname -m && lscpu | grep -E 'Model name|CPU\(s\)|Flags'
# Option 1 (where you have sudo, e.g. a rented Neoverse-V2 box): cut the network at the OS level.
# sudo drops exported variables, so pass HC_PY / HC_MODEL_REGISTRY through explicitly.
sudo unshare -n env HC_PY="$HC_PY" HC_MODEL_REGISTRY="$HC_MODEL_REGISTRY" \
  bash -c 'ip -brief link; curl -m 5 -sS https://example.com -o /dev/null; echo curl_exit=$?; candidates/BEST/bin/app --demo --out /tmp/demo-out.json'
# (unshare -rn works without sudo only where unprivileged user namespaces are enabled.)
# Option 2 (on Oracle Neoverse-N1, where unshare is blocked): run normally and say so on camera.
# Note: the 1:18 narration says "natively on Arm Linux"; only claim "network cut" if you used Option 1.
candidates/BEST/bin/app --demo --out .venv/demo-output.json
# And live Linux connection monitor (6 s window catching a loopback port scan, no root):
python3 candidates/BEST/bin/scan_demo.py --open --ports 150 &
candidates/BEST/bin/monitor --seconds 6
```

### C. Recording canvas & OBS / screen-capture settings
- **Resolution:** `1920×1080` (16:9), **30 fps**, H.264 (`yuv420p`), AAC stereo audio (`48 kHz`, `192 kbps`).
- **Layout for S23 segments:** Place the Samsung RTL Galaxy S23 phone mirror cleanly on the left/center-left (~45% width, crisp portrait frame, status bar with `✈` icon clearly readable!) and a clean dark side panel on the right showing:
  - Device badge: `Samsung Galaxy S23 (SM-S911B) · Snapdragon 8 Gen 2 · arm64-v8a · Android 14`
  - Runtime badge: `Llama 3.2 1B INT4 QLoRA · ExecuTorch XNNPACK · Airplane Mode ON`
  - Live scenario title (e.g., `1/3 Offline Permission Proof`, `2/3 KYC Scam SMS`, `3/3 Genuine Bank Debit Alert`)
- **Do NOT:** show hidden test items, open any suspicious URL, or show emulator frames without explicit labelling. Use **only** physical S23 + Arm Linux clips in the 2-minute video.

---

## 2. Tight 2:00 Shot List & Narration (~275 words ≈ 1:56 at 140 wpm)

| Time | Duration | Visual on screen (1920×1080, 16:9) | Spoken narration (read calmly, leave beats for live generation) |
|:--|--:|:--|:--|
| **0:00–0:10** | 10 s | **Title card** over subtle Prahari UI preview: *"Prahari — Offline Scam & Phishing Triage on Arm · Bharat AI-SoC 2026–27 (PS3)"* + badges: `Llama 3.2 1B · ExecuTorch · Arm64 · Built with Llama`. | *"Hi. This is Prahari — an offline, on-device scam and phishing assistant built for Indian smartphone users with Llama 3.2 1B running through ExecuTorch on Arm."* |
| **0:10–0:28** | 18 s | **Physical Galaxy S23 (RTL live screen).** Zoom callout highlights **Airplane icon (`✈`)** in status bar and `SM-S911B · arm64-v8a` badge. Tap **Offline / Prove it's offline** → screen immediately displays `NO INTERNET / blocked by Android` and `SecurityException: Permission denied (missing INTERNET permission?)` in `12 ms`. | *"We're running live on a physical Samsung Galaxy S23 over Remote Test Lab, with airplane mode switched on. Prahari declares no Android Internet permission at all. When we tap 'Prove it's offline', Android blocks an HTTPS test immediately with a SecurityException — your messages never leave the phone."* |
| **0:28–1:00** | 32 s | **Live KYC Scam SMS on Galaxy S23 (Airplane Mode `✈` still visible).** Tap **KYC scam SMS** sample → tap **Check**. Show **real-time** ~1.2–1.4 s completion (no cut!). Result appears: red **`DANGEROUS / खतरनाक`**, numbered bilingual steps (1. Don't open link, 2. Check bank app, 3. Report on Sanchar Saathi Chakshu), Chakshu & 1930 buttons. Scroll down to show evidence chips, **Explained on this phone by Llama 3.2** card with fallibility warning, and expand **On-device stats** (`6–8 ms` detector, `~510–657 ms` first token, `~39–43 tok/s`, `Total 1.2–1.4 s`, `ExecuTorch · XNNPACK`, `CPU ABI: arm64-v8a`). *(If using r2 APK: briefly tap `हिंदी` toggle and `Listen / सुनें`!)* | *"Now let's test a fake SBI KYC suspension SMS — completely offline. A lightweight local detector classifies the scam mechanism in under 10 milliseconds, and Llama 3.2 1B generates a plain-language explanation right on the Arm64 CPU in about 1.4 seconds at around 40 tokens per second. Safe steps come first in English and Hindi, with one-tap Sanchar Saathi Chakshu and 1930 helpline actions, followed by quoted evidence and the AI summary."* |
| **1:00–1:18** | 18 s | **Legitimate Bank Alert & Safe Notice on Galaxy S23 (Airplane Mode `✈`).** Tap **Check another** → select **Bank debit alert** (or genuine bill reminder) → tap **Check**. Show amber **`SUSPICIOUS / संदिग्ध`** ("Looks like a bank debit or OTP alert — verify in your bank app, don't use links in the message") — or slate-blue **`NO RISK FOUND — still verify`** on the bill reminder. Show completion in ~1.5 s. | *"Real bank and OTP alerts share words with scams, so Prahari avoids blindly screaming 'scam' on everyday notices. A genuine-looking bank debit alert is shown as a cautious verification check, directing the user straight to their official bank app."* |
| **1:18–1:44** | 26 s | **Arm Linux Terminal (`aarch64`) + KleidiAI & Live Monitor overlay.** Cut to crisp terminal: `uname -m` (`aarch64`), run `candidates/BEST/bin/app --demo` showing SMS, URL, flow, and prompt-injection verdicts + Llama stats; then brief terminal clip of `bin/monitor --seconds 6` catching `scan_demo.py --open` as a port scan without root. Small bottom-right metric card: **Arm Neoverse-V2:** `54.17% CPU in KleidiAI i8mm/dotprod kernels (perf)`, `1.73 s/item @ 2T`, `104.6 tok/s @ 8T`, `unshare -n offline verified`. | *"The same pipeline runs natively on Arm Linux. Here `bin/app --demo` triages SMS, lookalike URLs, network events, and prompt injection locally, while `bin/monitor` watches live Linux TCP connections without root to flag a port scan. Profiling on Arm Neoverse-V2 confirmed over 54 percent of CPU samples run directly inside Arm KleidiAI int8 kernels, scaling past 100 tokens per second across 8 threads."* |
| **1:44–2:00** | 16 s | **Honest Limits & Closing Card.** Clean slide showing: (1) S23 & Neoverse-V2 key numbers table, (2) Honest caveats (advisory-only, false alarms on hard benign look-alikes being reduced, ~1.7 GB phone PSS), (3) **Built with Llama (Llama 3.2 Community License)** + Public GitHub link `github.com/rabesss/arm-bharat-ai-soc`. | *"Prahari is an advisory prototype — verdicts can still err on hard look-alike messages, and cutting false alarms and RAM footprint further is our Phase 2 focus. Full code, benchmarks, and technical report are in the public GitHub repository. Built with Llama. Thank you."* |

---

## 3. Exact Recording & Post-Production Commands (the owner's Checklist)

1. **Record screen + voiceover** (OBS Studio set to `1920x1080`, `30 fps`, MKV → remux to MP4, or capture video clips and record clean voiceover separately so timing hits `1:55–1:59` with zero dead air).
2. **Verify / re-encode to competition-safe 1080p 16:9 MP4** (ensures universal browser/YouTube/VLC compatibility and strict `<= 2:00` duration):
   ```sh
   ffmpeg -i raw-demo.mp4 \
     -t 120 \
     -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=#0f172a,fps=30" \
     -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p \
     -c:a aac -b:a 192k -ar 48000 -ac 2 \
     -movflags +faststart \
     prahari-phase1-demo-1080p.mp4
   ```
3. **Verify technical specs before uploading:**
   ```sh
   ffprobe -v error -show_entries format=duration,size:stream=codec_type,codec_name,width,height,display_aspect_ratio,r_frame_rate -of default=noprint_wrappers=1 prahari-phase1-demo-1080p.mp4
   ```
   Confirm:
   - `width=1920`, `height=1080`, `display_aspect_ratio=16:9`
   - `duration <= 120.0` seconds
   - `codec_name=h264` and `aac`
   - `sha256sum prahari-phase1-demo-1080p.mp4` recorded in your submission manifest.
4. **Clean up RTL device after recording:**
   ```sh
   adb shell cmd connectivity airplane-mode disable
   adb uninstall in.prahari.app
   ```
   Close the Samsung Remote Test Lab session cleanly in the browser.
5. **Upload & verify public playback:**
   - Upload `prahari-phase1-demo-1080p.mp4` to a **PUBLIC** URL (YouTube Public or Unlisted if accepted, or public Google Drive/direct link — check exact wording on the Phase 1 form; "PUBLIC" means viewable without sign-in!).
   - Open the final link in a **private/incognito browser window** to confirm it plays immediately at 1080p with clear audio before pasting into the one-shot submission form.
