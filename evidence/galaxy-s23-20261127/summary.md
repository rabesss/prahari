# Samsung Galaxy S23 phone follow-up — 27 November 2026

This is partial evidence. The phone connection was interrupted during model transfer, before the model files could be verified or inference could be run. No timing or CPU sample results were obtained.

## Build and device

- Samsung Galaxy S23 phone, `SM-S911B`, `SM8550`, Android 14.
- Debug APK: Android CI run `45945461952`, commit `3b7575c2165289b099d9b0bf9184a294b6ab6082`; SHA-256 `54815f5074c39173a001a028e33d17132d7786f7ff43acfee2bbad26af2259bd`.
- Local model SHA-256: `ab7b7ebf97421c7770ad97d4abfdf8650a7d9f9dc1ce9a0c4663d49f7b7a08ac`.
- Local tokenizer SHA-256: `82e9d31979e92ab929cd544440f129d9ecd797b69e327f80f17e1c50d5551b55`.
- Airplane mode was verified enabled for the permissions clip; battery temperature was 33.7 °C at that point.

## Captured

`permissions.mp4` is a 7.02-second real-time H.264 screen recording of Prahari's Android app-permissions screen, with the airplane icon and clock visible. The screen says no permissions are allowed or denied. Android's screen lists runtime permissions, so the package dump is the evidence for the requested-permissions claim: `permissions-dumpsys.txt` shows only the app's dynamic receiver permission and no `android.permission.INTERNET` request.

## Not completed

The model transfer ended with an error and neither device-side model hash was verified. The share-to-verdict take, the warm and cold checks, CPU profile, newer-check clips and offline request proof were not captured. There are no medians, ranges, p90s, decode rates, or sampled CPU shares to report. No conclusion about inference or performance follows from this partial session.

The bundled arm64 `libexecutorch.so` has a dynamic symbol table but no full symbol table; `nm -D` and `strings` found no `kai_` names in the shipped arm64 libraries. This is a file inspection, not a CPU profile and not proof that no KleidiAI code is present.

Phone-side removal of the test apps and files, restoration of airplane mode and screen timeout, and return of the phone could not be verified after the connection was lost.

## Retry session

A second Samsung Galaxy S23 phone (`SM-S911B`, `SM8550`, Android 14) was used. Before setup, the two test packages and the app's external files directory were absent, airplane mode was off, and the screen timeout was 300000 ms. All 18 model chunks were checked individually; the concatenated model and tokenizer matched the local SHA-256 values above on the phone. Airplane mode was then verified on. The battery temperature at the start of the attempted inference was 32.1 °C.

The app's preload telemetry recorded `state: error` after 21 ms; the cause was not established. The model file created by concatenation was displayed with mode `660`, but the effect of this on app access was not verified. The phone connection was lost during the attempted access check. No model-ready event, inference, timing results, CPU profile, or new screen recording was obtained. The synthetic text was successfully selected and shown in the Android share sheet, where Prahari appeared in the app list; that rehearsal was not recorded.

After the connection loss, phone-side cleanup and settings restoration could not be verified. The staged model, tokenizer and test apps may remain, and airplane mode and screen timeout may still be changed. The session could not be confirmed ended or returned.
