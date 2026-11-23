# Call Guard (preview)

Call Guard checks a recorded scam call for the Indian "digital arrest" script and tells the listener
to hang up. It is a preview: the Linux/Arm pipeline works end to end; the Android part has not run on a
phone yet.

## What it does

1. **Input.** A WhatsApp voice note or other shared audio file (`.wav` natively; `.ogg`, `.opus`, `.m4a`,
   `.mp3` through a local `ffmpeg`), or a speakerphone recording made with `--record N --consent`.
   Android and Linux apps cannot tap live cellular or VoIP call audio, so Call Guard never listens to a
   call by itself. The person has to share or record the audio.
2. **Speech-to-text on the device.** Arm's INT8 Whisper Tiny export
   (`Arm/whisper-tiny-int8-xnnpack-executorch`, Apache-2.0, 117 MB `.pte`) runs through ExecuTorch with
   XNNPACK. Log-mel features are computed in NumPy, not by `whisper_preprocessor.pte`, which kept peak
   RSS far lower on aarch64. Greedy decoding, 30 s windows, up to 2 minutes per file, with a repetition
   guard and a per-window time cap.
3. **Detection.** The transcript goes through the existing SMS detector (`detect.classify_any("sms", …)`)
   and new call-script rules (`triage/callrules.py`): fake CBI, police, customs, TRAI or RBI callers;
   arrest warrants and "digital arrest"; drug parcels linked to Aadhaar; "do not disconnect"; "stay alone
   on video call" or "do not tell your family"; transfers to an "RBI safe" or "verification" account;
   SIM-disconnection and "press 9" scripts; OTP or remote-app requests. The rules are clause-scoped and
   check for protective framing, so a genuine bank reminder ("never share your OTP on a call") is not
   flagged. `callguard.fuse()` combines both and is shared by the desktop and Android code.
4. **Explanation.** Llama 3.2 1B (the configured `llama32-1b-qlora` `.pte`) writes the warning through
   ExecuTorch. For a scam it starts with "STOP — This call is DANGEROUS: …" and adds one sentence telling
   the listener to hang up and report it. The existing post-processing removes unsafe advice.
5. **Actions and read-aloud.** Vetted steps: hang up; never move money to a "safe account"; tell family;
   report on Sanchar Saathi Chakshu (sancharsaathi.gov.in) or cybercrime.gov.in; call 1930 if money was
   lost. `--speak` reads a short fixed STOP script aloud with `espeak-ng`/`spd-say` on Linux. The spoken
   script never repeats the caller's words.

## Run (Linux / aarch64)

```sh
# once, with network: download and SHA-256-verify the Whisper .pte and tokenizer (not committed)
candidates/BEST/bin/callguard --setup-model          # or set PRAHARI_WHISPER_DIR to an existing copy
# offline from here on
candidates/BEST/bin/callguard --demo                 # four synthetic calls in demo/call_guard/
candidates/BEST/bin/callguard --file voice-note.ogg  # JSON on stdout (native runner logs go to stderr)
candidates/BEST/bin/callguard --transcript "This is CBI, do not disconnect…" --no-explain
candidates/BEST/bin/callguard --record 30 --consent  # speakerphone, only with consent
candidates/BEST/bin/app --call-guard                 # web UI with POST /api/callguard (transcript)
```

The feature is behind a flag. The web endpoint returns 404 unless `PRAHARI_CALL_GUARD=1` or
`--call-guard` is set. `PRAHARI_CALL_GUARD=0` disables the CLI. The SMS, URL, flow and injection paths
do not import Call Guard.

## Measured on Arm (Oracle A1, 2 vCPU Neoverse-N1, ~11 GB RAM)

Run on 2026-11-23 with `bin/callguard --demo`. The raw output is in
`candidates/BEST/artifacts/callguard_demo_neoverse_n1.json`. The VM is shared, and load average was
3.0–3.6 during the run, so the slower rows reflect co-tenant contention.

| Clip | Audio | ASR (Whisper Tiny INT8) | Real-time factor | Llama prefill / decode | End to end (ASR + rules + Llama) |
|---|---|---|---|---|---|
| digital arrest (CBI) | 17.9 s | 4.02 s | 4.5x | 41 / 11 tok/s | 16.5 s |
| TRAI + customs parcel | 11.6 s | 5.49 s | 2.1x | 43 / 12 tok/s | 12.3 s |
| SBI security reminder | 13.5 s | 3.32 s | 4.1x | 85 / 21 tok/s | 6.9 s |
| clinic + courier | 11.4 s | 2.93 s | 3.9x | 76 / 20 tok/s | 6.6 s |

- Whisper model load: 0.24 s. Rules plus detector: 30–55 ms per call (2.0 s on the first call while the
  detectors load).
- Peak process RSS (`/usr/bin/time -v`, four clips): **851 MB ASR only**; **2.67 GB ASR + Llama** in
  one process. The Llama runner reports 2.6 GB RSS after load.
- All four clips got the expected verdict (2 scam → STOP, 2 benign → no risk found).
- Import order matters. If `executorch.extension.llm.custom_ops` is not imported before the Whisper
  program loads, Whisper decode is about 1.8x slower, and a Llama runner loaded later in the same
  process drops from about 82 to about 18 prefill tokens/s. `asr.py` now imports it first.

**Not measured:** Galaxy S23 or any physical phone. That needs a Remote Test Lab session. Android
numbers must not be quoted from these Linux results.

## Android (preview, not wired into the UI)

- `android/python/callguard_mobile.py` is the Chaquopy adapter. It needs only NumPy: mel features, a
  pure-Python Whisper token decoder, `callguard.fuse()`, Hindi action strings, and the existing
  `BridgeExplainer` for the Llama STOP warning. `android/tools/test_callguard_bridge.py` runs it with
  torch, executorch, sklearn and tokenizers blocked, as on the phone, in the Android CI job.
- `android/app/.../CallGuardPreview.kt` has shared-audio intent parsing, offline MediaCodec decoding to
  PCM, and an ExecuTorch `Module` Whisper encoder/decoder loop. Its output feeds the adapter above. It
  compiles with the app, but no button or share target in `MainActivity` calls it yet, and it has not
  run on a device. The Whisper `.pte` and `tokenizer.json` must be pushed to the app's files dir with
  adb. It is not bundled. The Kotlin path transcribes only the first 30 s of a file.
- The read-aloud step on Android is meant to reuse the app's existing offline `TextToSpeech` voice.

## Limitations

- **Hindi is not reliable.** On a synthetic Hindi digital-arrest clip, Whisper Tiny (with `--lang hi`)
  produced a garbled English-like transcript. The rules still found the fake-authority signal, but the
  verdict was SUSPICIOUS, not STOP. A larger multilingual Whisper or a Hindi-tuned model would be needed.
- The demo clips are synthetic English TTS in a US voice, not real Indian calls. Real call audio
  (compressed, noisy, accented, two speakers) will raise the ASR error rate. Whisper already mishears
  "UPI PIN", "Aadhaar" and "TRAI" on the clean clips. The rules tolerate some of this, but not all.
- Four demo clips are not an accuracy evaluation. Precision and recall on real calls are unknown.
- Only 2 minutes per file are transcribed. Longer recordings are cut.
- The model can still word the advice imperfectly ("report to authorities" rather than naming 1930).
  The vetted action list always names 1930 and Chakshu.

## Fixture provenance

`demo/call_guard/*.wav` are synthetic. `demo/call_guard/generate.py` reads the `script` field in
`manifest.json` aloud with Piper `en_US-libritts_r-medium` (training data LibriTTS-R, CC BY 4.0; the
Piper maintainers state it was retrained from scratch) and stores 16 kHz mono PCM. No real call audio or
real person's voice is used. An earlier draft used `en_US-lessac`. That voice was dropped because its
Blizzard 2013 training corpus is licensed for research use only.
