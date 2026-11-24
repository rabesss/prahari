# Prahari Android app

Prahari is an experimental offline Android port of the BEST candidate. It uses the shipped
rules and explanation prompt/checks, portable exported detector parameters, Chaquopy 17.2.0
(Python 3.10, NumPy 1.26.2) and Maven ExecuTorch Android 1.5.1. No Llama model or tokenizer is
included in the APK or repository. **The detector and Llama have run end to end on an Android 14 x86_64 emulator. A physical Arm phone run remains pending.**

## Build

The build runs in GitHub Actions (`Android spike`). It generates detector JSON from the
trusted checked-in joblib files using Python 3.12 and scikit-learn 1.9.1, runs parity and fake
runner tests, and builds a debug APK. Download `prahari-debug-apk` from a successful run.

The parallel `executorch-aar` job attempts an arm64 ExecuTorch v1.6.0 source AAR with XNNPACK
and KleidiAI, caches the resulting AAR, and uploads `executorch-1.6.0-arm64-aar` with a build-time
record. If the exact model fails to generate on 1.5.1, request an additional 1.6 APK through
Actions, without running Gradle on the owner's PC:

```sh
gh workflow run android.yml --ref main -f source_apk=true
```

Download `prahari-debug-apk-executorch-1.6` from that run. A successful AAR or APK build is not
evidence of model execution: the fallback also needs phone testing.

## Model files

The original registry identifies the QLoRA INT4 EO8 model. These hashes were measured on
oracle-a1, not on an Android phone:

| Filename | SHA256 |
| --- | --- |
| `Llama-3.2-1B-Instruct-QLORA_INT4_EO8.pte` | `ab7b7ebf97421c7770ad97d4abfdf8650a7d9f9dc1ce9a0c4663d49f7b7a08ac` |
| `tokenizer.model` | `82e9d31979e92ab929cd544440f129d9ecd797b69e327f80f17e1c50d5551b55` |

The model is approximately 1.18 GB. The source is the [ExecuTorch community model](https://huggingface.co/executorch-community/Llama-3.2-1B-Instruct-QLORA_INT4_EO8-ET), subject to the Llama 3.2 Community License. Maven Central [lists 1.5.1 as the newest AAR](https://repo.maven.apache.org/maven2/org/pytorch/executorch-android/maven-metadata.xml); [1.6 release notes](https://github.com/pytorch/executorch/releases/tag/v1.6.0) do not establish forward compatibility with 1.5.1. The same model has run using the Python 1.6 runner on Oracle and the Android 1.5.1 AAR on an x86_64 emulator. If 1.5.1 fails, first try the 1.6 source AAR. One alternative for 1.5.1 is the [community SpinQuant INT4 EO8 export at revision 911221e](https://huggingface.co/executorch-community/Llama-3.2-1B-Instruct-SpinQuant_INT4_EO8-ET/tree/911221e0f49d3354cbd4697a9c09feee25cadec7): an [independent Android test](https://meetprajapati.com/blogs/executorch-android-offline-llama-chat-benchmarks/) reports generation with 1.5.1 on a Pixel 8a. It is a different model, not a verification of Prahari or a Galaxy phone. The app currently expects the QLoRA filename; if trying SpinQuant, verify its matching tokenizer and hashes separately, then copy the model under that expected filename and record the substitution.

The joblib pickles record scikit-learn 1.9.1. Chaquopy's [Android wheel index](https://chaquo.com/pypi-13.1/scikit-learn/) lists scikit-learn through 1.3.2 for Python 3.10 arm64, not 1.9.1; its index also lists NumPy 1.26.2 and SciPy 1.8.1 for Python 3.10 arm64, while joblib 1.6.0 is a pure-Python wheel requiring Python 3.10+. Cross-version loading is unsupported. CI exports all four models from the reference environment and tests portable probabilities and final scores/labels against visible fixtures. No cross-version unpickling occurs on Android.

## Remote phone checklist

1. On a computer with `adb` on `PATH` and the model files locally available, reserve an arm64 Galaxy phone in Samsung Remote Test Lab, open its web client and download its Remote Debug Bridge (RDB) client. Extract it and run `./rdb` on Linux (or run `rdb.exe` on Windows); leave it running. See [Samsung's RDB instructions](https://developer.samsung.com/remotetestlab/docs/70/tests-on-devices).
2. In the RTL web client choose **Remote Debug Bridge → Connect**, approve the USB debugging prompt, then run `adb devices -l`. Set the actual serial shown by that command, e.g. `export ANDROID_SERIAL=localhost:PORT`; do not guess the port. Check `adb shell getprop ro.product.model`, `adb shell getprop ro.product.cpu.abilist`, and `adb shell getprop ro.build.version.sdk` (arm64 and API 28+ required).
3. Download and unzip the CI APK artifact on the computer. Install and launch once to create the app-specific directory:

   ```sh
   adb install -r app-debug.apk
   adb shell am start -n in.prahari.app/.MainActivity
   adb shell mkdir -p /sdcard/Android/data/in.prahari.app/files
   ```

4. Time the model transfer and verify both files on the phone; replace the two local paths:

   ```sh
   time adb push /path/to/Llama-3.2-1B-Instruct-QLORA_INT4_EO8.pte /sdcard/Android/data/in.prahari.app/files/
   adb push /path/to/tokenizer.model /sdcard/Android/data/in.prahari.app/files/
   adb shell sha256sum /sdcard/Android/data/in.prahari.app/files/Llama-3.2-1B-Instruct-QLORA_INT4_EO8.pte /sdcard/Android/data/in.prahari.app/files/tokenizer.model
   ```

   Match both digests to the table before testing. Allow time and storage for the model transfer.
5. In Prahari press **Prove it’s offline**, record the failure and inspect the CI `aapt` and merged-manifest audit. Test the SMS, URL and flow presets; confirm actual generated Llama text, evidence, action, timing, and no crash or empty explanation. Include a flow JSON example and verify its model verdict is retained by the prompt. Test the exact model and tokenizer above; loading alone is insufficient.
6. Before any long benchmark, measure PSS and sustained inference. After first generation and after several consecutive checks, run `adb shell dumpsys meminfo in.prahari.app` and record TOTAL PSS, process survival, elapsed time, thermal throttling and results. Sample repeatedly during generation to estimate peak PSS; the app's displayed PSS is a post-inference sample, not peak. Stop on memory pressure, a crash, or unacceptable thermal/latency behaviour.
7. Only if the phone is stable, run a small benchmark: the 28 chosen visible prompts, one repeat, recording each detector time, TTFT, runtime decode tok/s, total and sampled peak PSS. The hidden 28-item evaluation set is not in this repository; use a fixed visible set and label the result as such, not as the original benchmark. No automated phone benchmark is included yet.
8. If generation fails on 1.5.1, try the separately built 1.6 AAR APK only after its CI build succeeds; repeat the generation, memory and stability checks. Report the exact AAR and APK used.

## Report card and send to family

A DANGEROUS or SUSPICIOUS message or link result shows two more buttons under the report row. The
verdict never depends on them, and neither sends anything by itself.

* **Copy report** puts a short plain-text report on the clipboard for the Sanchar Saathi Chakshu form:
  the medium, the Chakshu category, the sender (only when the shared text names it), the date, up to
  three evidence lines with short quotes (4+ digit runs masked, links defanged as `hxxp://` and
  `[.]`; the clipboard entry is marked sensitive so Android hides its preview), and
  "Already lost money? Call 1930 / cybercrime.gov.in". The category is one of the 11 in the
  [Sanchar Saathi FAQ](https://sancharsaathi.gov.in/) and comes from the detector's scam type, with
  text cues only to name the impersonated party; a mechanism that does not fix a category maps to
  "Any Other Suspected Fraud". Nothing is submitted.
* **Send to family** (परिवार को बताएं) opens the Android share sheet (`ACTION_SEND`) with a short
  warning in the app language: what the scam is, one safety step, and the link's registered domain
  only (`hxxp://in-verify[.]top` for `http://sbi-kyc.in-verify.top/u?m=...`), defanged. Subdomains,
  paths and queries are dropped because a scammer can personalise them per victim, and a domain
  that still carries a number is left out. It never carries the message body, the sender, names or
  numbers. The user picks the app and the person; no contacts
  permission is used, and Prahari is excluded from the chooser.

The medium is a hint only: QR scan, or the sharing app reported by the optional Android referrer
(WhatsApp, Google or Samsung Messages); otherwise "SMS or WhatsApp message". An ordinary bank debit
alert gets no report; an alert the app raises to SUSPICIOUS because it names its own link or number
does. Logic and templates are in `android/python/report_card.py`; tests in
`android/tools/test_report_card.py` and `android/tools/test_bridge.py`. Pending a Galaxy S23 re-test.

## Screen-sharing app warning

When a result names a bank, wallet, KYC, UPI, OTP, card, refund or customer-care desk (or is a UPI
item, an OTP/safe-account scam or a debit alert), or the text asks the reader to
install a remote-control app (the detector's `remote_app` rule in `triage/rules.py`), the result
screen checks whether one of a fixed list of screen-sharing apps is installed. If one is, an amber
note says: "A screen-sharing app (X) is installed. Scammers use these to watch your bank app.
Uninstall it if a 'support agent' asked you to install it." (Hindi in Hindi mode.)

The list is AnyDesk, TeamViewer QuickSupport, TeamViewer Host, TeamViewer, RustDesk, AirDroid,
AirDroid Remote Support and AirDroid Cast (`RemoteApps.kt`). Each package is named in the
manifest's `<queries>`, which is Android's narrow package-visibility path. This feature looks up
only those packages, and the app does not request `QUERY_ALL_PACKAGES` (Android still exposes a few
system packages to every app automatically). Play IDs were checked
against their Play listings on 24 Nov 2026; RustDesk is not on Play, so its ID comes from F-Droid
and its upstream `applicationId`. The installed-app result is shown on screen only: it is never
logged, stored in History or sent anywhere, and the verdict never depends on it. Tests:
`android/tools/test_remote_apps.py`. Pending a Galaxy S23 re-test.

## Known limits

* The Android 1.5.1 and 1.6 `LlmGenerationConfig.maxNewTokens` field is not passed by the Android `generate` overload to the native runner. The bridge stops after 40 UTF-8 callbacks, which can each contain multiple token fragments; this is **not a guaranteed 40-token cap**. The exact budget needs a fixed upstream Android binding or a custom native bridge before claiming parity. TTFT is measured to the first callback, and decode tok/s comes from native stats.
* The UI accepts flow descriptions (the candidate's rule path) or a JSON feature record (the trained flow model). Both pass the actual detector verdict and evidence to the explanation; no verdict is recomputed by the bridge.
* The portable implementation and JNI have run on an x86_64 emulator; they have not been verified on a physical Arm phone. Parity fixtures are small and do not prove equivalent behaviour on all inputs or Android NumPy. Model memory plus Python can exceed a mid-range phone's available RAM. Android can kill the app; temperature, storage and cold-start time may be limiting.
* The HTTPS button tries a real connection and reports the exception. A failed connection alone does not prove absence of network capability; review the merged manifest and permissions alongside it.
