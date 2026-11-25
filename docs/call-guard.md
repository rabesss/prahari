# Call Guard (preview)

Call Guard checks a recorded scam call for the Indian "digital arrest" script and tells the listener
to hang up. It is a preview: the Linux/Arm pipeline works end to end; the Android part has not run on a
phone yet.

## What it does

1. **Input.** A WhatsApp voice note or other shared audio file (`.wav` natively; `.ogg`, `.opus`, `.m4a`,
   `.mp3` through a local `ffmpeg`, which may only use audio demuxers so a disguised playlist cannot
   pull in other files), or a speakerphone recording made with `--record N --consent`.
   Android and Linux apps cannot tap live cellular or VoIP call audio, so Call Guard never listens to a
   call by itself. The person has to share or record the audio.
2. **Speech-to-text on the device.** Arm's INT8 Whisper Tiny export
   (`Arm/whisper-tiny-int8-xnnpack-executorch`, Apache-2.0, 117 MB `.pte`) runs through ExecuTorch with
   XNNPACK. Log-mel features are computed in NumPy, not by `whisper_preprocessor.pte`, which kept peak
   RSS far lower on aarch64. Greedy decoding, 30 s windows, up to 2 minutes per file (only that much
   is read from disk), with a repetition guard and a per-window time cap. If the file was longer, or any
   window stopped before end-of-text, the transcript is marked incomplete. An incomplete transcript can
   never be cleared: NO RISK becomes SUSPICIOUS with a note naming the part that was not checked.
3. **Detection.** The transcript goes through the existing SMS detector (`detect.classify_any("sms", …)`)
   and new call-script rules (`triage/callrules.py`): fake CBI, police, customs, TRAI or RBI callers;
   arrest warrants and "digital arrest"; drug parcels linked to Aadhaar; "do not disconnect"; "stay alone
   on video call" or "do not tell your family"; transfers to an "RBI safe" or "verification" account;
   SIM-disconnection and "press 9" scripts; OTP or remote-app requests. A match governed by a negation
   ("never transfer to a safe account") is advice, not a demand. A sentence that only describes scams
   ("real police never…", "fraudsters pose as CBI") is skipped up to a "but". Labels such as "security
   reminder" hide nothing, so a scammer cannot borrow them. The genuine bank reminders in the tests are not flagged. A
   detector DANGEROUS verdict is never cleared because the call sounds protective, unless the only harm
   is telling the listener to block their own card in the official app. `callguard.fuse()` combines both and is shared by the desktop and Android code.
4. **Explanation.** Llama 3.2 1B (the configured `llama32-1b-qlora` `.pte`) writes the warning through
   ExecuTorch. For a scam it starts with "STOP — This call is DANGEROUS: …" and adds one sentence telling
   the listener to hang up and report it. The wording varies: the model does not always name 1930 or
   Chakshu, so the vetted action list below always does. Chat-template control tokens are stripped from the transcript
   before it is quoted in the prompt. The existing post-processing removes unsafe advice.
5. **Actions and read-aloud.** Vetted steps: hang up; never move money to a "safe account"; tell family;
   report on Sanchar Saathi Chakshu (sancharsaathi.gov.in) or cybercrime.gov.in; call 1930 if money was
   lost. `--speak` reads a short fixed STOP script aloud with `espeak-ng`/`spd-say` on Linux. The spoken
   script never repeats the caller's words.

## Run (Linux / aarch64)

```sh
# once, with network: download and SHA-256-verify the Whisper .pte and tokenizer (not committed)
candidates/BEST/bin/callguard --setup-model          # or set PRAHARI_WHISPER_DIR to an existing copy
# offline from here on
candidates/BEST/bin/callguard --demo                 # four synthetic calls in candidates/BEST/demo/call_guard/
candidates/BEST/bin/callguard --file voice-note.ogg  # JSON on stdout (native runner logs go to stderr)
candidates/BEST/bin/callguard --transcript "This is CBI, do not disconnect…" --no-explain
candidates/BEST/bin/callguard --record 30 --consent  # speakerphone, only with consent
candidates/BEST/bin/app --call-guard                 # web UI with POST /api/callguard (transcript)
```

The feature is behind a flag. The web endpoint returns 404 unless `PRAHARI_CALL_GUARD=1` or
`--call-guard` is set. `PRAHARI_CALL_GUARD=0` disables the CLI. The SMS, URL, flow and injection paths
do not import Call Guard.

## Measured on Arm (Oracle A1, 2 vCPU Neoverse-N1, ~11 GB RAM)

Run on 2026-11-23 with `bin/callguard --demo` on the final code. The unedited `--out` files are
`candidates/BEST/artifacts/callguard_demo_neoverse_n1.json` (with Llama) and
`callguard_demo_asr_only_neoverse_n1.json`. `/usr/bin/time` figures and the import-order runs are in
`callguard_demo_neoverse_n1.meta.json`. The VM is shared: load average rose from 1.7 to 3.7 during
the runs, so per-clip times vary, and the slow rows were not investigated further.

| Clip | Audio | ASR (Whisper Tiny INT8) | Real-time factor | Llama prefill / decode | End to end (ASR + rules + Llama) |
|---|---|---|---|---|---|
| digital arrest (CBI) | 17.9 s | 3.73 s | 4.8x | 57 / 21 tok/s | 13.3 s |
| TRAI + customs parcel | 11.6 s | 3.16 s | 3.7x | 87 / 20 tok/s | 6.8 s |
| SBI security reminder | 13.5 s | 5.03 s | 2.7x | 44 / 11 tok/s | 11.8 s |
| clinic + courier | 11.4 s | 3.36 s | 3.4x | 86 / 21 tok/s | 6.8 s |

- Whisper model load: 0.24 s. Rules plus detector: 29–84 ms per call (2.0 s on the first call while the
  detectors load). Every transcript was complete (each window ended on end-of-text).
- Peak process RSS (`/usr/bin/time -v`, four clips): **832 MiB ASR only**; **2,611 MiB ASR + Llama** in
  one process. The Llama runner reports about 2,609 MiB RSS after load.
- All four clips got the expected verdict (2 scam → STOP, 2 benign → no risk found).
- Import order matters. If `executorch.extension.llm.custom_ops` is not imported before the Whisper
  program loads, Whisper decode is about 1.8x slower, and a Llama runner loaded later in the same
  process drops from about 82 to about 18 prefill tokens/s. `asr.py` now imports it first. Those runs are
  recorded under `import_order_check` in the `.meta.json` file.

**Not measured:** Galaxy S23 or any physical phone. That needs a phone session. Android
numbers must not be quoted from these Linux results.

## Android (preview, not wired into the UI)

- `android/python/callguard_mobile.py` is the Chaquopy adapter. It needs only NumPy: mel features, a
  pure-Python Whisper token decoder, `callguard.fuse()`, Hindi action strings, and the existing
  `BridgeExplainer` for the Llama STOP warning. `android/tools/test_callguard_bridge.py` runs it with
  torch, executorch, sklearn and tokenizers blocked, as on the phone, in the Android CI job.
- `android/app/.../CallGuardPreview.kt` has shared-audio intent parsing, offline MediaCodec decoding to
  PCM, and an ExecuTorch `Module` Whisper encoder/decoder loop. Its output feeds the adapter above. It
  compiles with the app (the Android CI `apk` job builds it), but no button or share target in `MainActivity` calls it yet, its
  `FEATURE_FLAG_ENABLED` constant is `false`, and it has not run on a device. It returns a `truncated`
  flag (audio cut at 30 s) and a `partial` flag (decoding stopped before end-of-text), which
  `callguard_mobile.verdict_call(transcript, truncated=..., partial=...)` uses so a cut call is never cleared.
  Before it is wired up, it still needs a check that the shared URI is a granted content URI and a
  digest or size check on the pushed `.pte`. The Whisper `.pte` and `tokenizer.json` must be pushed to the app's files dir with
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
- Call Guard inherits the core SMS detector's false positives. For example, "credited to your settlement
  account" reads as a safe-account demand. When the detector's DANGEROUS reading comes only from a question
  or reported speech ("did the caller ask for your OTP?"), the verdict is SUSPICIOUS instead.
- The existing post-processing filters unsafe advice on DANGEROUS and SUSPICIOUS verdicts only, not on
  NO RISK FOUND.
- A phrase repeated three times ("hello? hello? hello?") trips the decoder's loop guard and ends that
  30 s window early. The transcript is then marked incomplete, so the call can be SUSPICIOUS at worst.
- `--lang auto` chooses only between English and Hindi.
- Whisper is a second neural model in the entry, used only for speech-to-text. The rules require Llama for
  the advisory component, and Llama still writes every explanation.
- Only 2 minutes per file are transcribed (30 s on the Android path, and its notes say so). A longer recording is cut and
  can at best be SUSPICIOUS, never cleared.
- The model can still word the advice imperfectly ("report to authorities" rather than naming 1930).
  The vetted action list always names 1930 and Chakshu.

## Fixture provenance

`candidates/BEST/demo/call_guard/*.wav` are synthetic. Its `generate.py` reads the `script` field in
`manifest.json` aloud with Piper `en_US-libritts_r-medium` (training data LibriTTS-R, CC BY 4.0; the
Piper maintainers state it was retrained from scratch; SHA-256 pinned) and stores 16 kHz mono PCM. No real call audio or
real person's voice is used. An earlier draft used `en_US-lessac`. That voice was dropped because its
Blizzard 2013 training corpus is licensed for research use only.
