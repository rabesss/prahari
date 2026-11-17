# Prahari Android spike

Prahari is an experimental offline Android port of the BEST candidate. It uses the unchanged
rules and explanation prompt/checks, portable exported detector parameters, Chaquopy 17.2.0
(Python 3.10, NumPy 1.26.2) and Maven ExecuTorch Android 1.5.1. No Llama model or tokenizer is
included in the APK or repository. **No device generation has been verified. This is not yet a
phone go decision.**

## Build

The supported build is GitHub Actions (`Android spike`): the APK job generates detector JSON
from the trusted checked-in joblib files with Python 3.12 and scikit-learn 1.9.1, runs parity and
fake-runner tests, then builds a debug APK. Download the `prahari-debug-apk` artifact. Building
locally requires the same Python reference environment, JDK 17, Android SDK 35, Gradle 8.10.2
and the Chaquopy build Python 3.10; generate the inputs first:

```sh
python -m pip install numpy==2.5.4 scipy==1.18.1 scikit-learn==1.9.1 pandas==3.1.1 joblib==1.6.0
mkdir -p android/build/generated/python
cp -R candidates/BEST/triage android/build/generated/python/triage
python android/tools/export_models.py android/build/generated/python/models
python android/tools/test_parity.py android/build/generated/python/models
python android/tools/test_bridge.py
cd android
gradle :app:assembleDebug
```

The parallel `executorch-aar` job attempts an arm64 ExecuTorch v1.6.0 source AAR with XNNPACK
and KleidiAI, caches the resulting AAR and uploads `executorch-1.6.0-arm64-aar`, including a
build-time record. To try it only if the existing model fails on 1.5.1, download the AAR and build
with `gradle :app:assembleDebug -PprahariAar=/absolute/path/executorch.aar`; this is a distinct
APK that also needs phone testing. A successful source build is not evidence of model execution.

## Model files

The original registry identifies the QLoRA INT4 EO8 model. These hashes were measured on
oracle-a1, not on an Android phone:

| Filename | SHA256 |
| --- | --- |
| `Llama-3.2-1B-Instruct-QLORA_INT4_EO8.pte` | `ab7b7ebf97421c7770ad97d4abfdf8650a7d9f9dc1ce9a0c4663d49f7b7a08ac` |
| `tokenizer.model` | `82e9d31979e92ab929cd544440f129d9ecd797b69e327f80f17e1c50d5551b55` |

The model is approximately 1.18 GB. The source is the [ExecuTorch community model](https://huggingface.co/executorch-community/Llama-3.2-1B-Instruct-QLORA_INT4_EO8-ET), subject to the Llama 3.2 Community License. Maven Central [lists 1.5.1 as the newest AAR](https://repo.maven.apache.org/maven2/org/pytorch/executorch-android/maven-metadata.xml); [1.6 release notes](https://github.com/pytorch/executorch/releases/tag/v1.6.0) do not establish forward compatibility with 1.5.1. The model has been run using the Python 1.6 runner on Oracle but not this Android AAR. If 1.5.1 fails, first try the 1.6 source AAR; do not assume another community export is compatible without checking its exact export version and running it.

The joblib pickles record scikit-learn 1.9.1. Chaquopy's [Android wheel index](https://chaquo.com/pypi-13.1/scikit-learn/) lists scikit-learn through 1.3.2 for Python 3.10 arm64, not 1.9.1; cross-version loading is unsupported. CI exports all four models from the reference environment and tests portable probabilities and final scores/labels against visible fixtures. No cross-version unpickling occurs on Android.

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
5. In Prahari press **Network check**, record the failure and inspect the CI `aapt` and merged-manifest audit. Test the SMS, URL and flow presets; confirm actual generated Llama text, evidence, action, timing, and no crash or empty explanation. Include a flow JSON example and verify its model verdict is retained by the prompt. Test the exact model and tokenizer above; loading alone is insufficient.
6. Before any long benchmark, measure PSS and sustained inference. After first generation and after several consecutive checks, run `adb shell dumpsys meminfo in.prahari.app` and record TOTAL PSS, process survival, elapsed time, thermal throttling and results. Sample repeatedly during generation to estimate peak PSS; the app's displayed PSS is a post-inference sample, not peak. Stop on memory pressure, a crash, or unacceptable thermal/latency behaviour.
7. Only if the phone is stable, run a small benchmark: the 28 chosen visible prompts, one repeat, recording each detector time, TTFT, runtime decode tok/s, total and sampled peak PSS. The hidden 28-item evaluation set is not in this repository; use a fixed visible set and label the result as such, not as the original benchmark. No automated phone benchmark is included yet.
8. If generation fails on 1.5.1, try the separately built 1.6 AAR APK only after its CI build succeeds; repeat the generation, memory and stability checks. Report the exact AAR and APK used.

## Known limits

* The Android 1.5.1 and 1.6 `LlmGenerationConfig.maxNewTokens` field is not passed by the Android `generate` overload to the native runner. The bridge stops after 40 UTF-8 callbacks, which can each contain multiple token fragments; this is **not a guaranteed 40-token cap**. The exact budget needs a fixed upstream Android binding or a custom native bridge before claiming parity. TTFT is measured to the first callback, and decode tok/s comes from native stats.
* The UI accepts flow descriptions (the candidate's rule path) or a JSON feature record (the trained flow model). Both pass the actual detector verdict and evidence to the explanation; no verdict is recomputed by the bridge.
* The portable implementation and JNI have not run on-device. Parity fixtures are small and do not prove equivalent behaviour on all inputs or Android NumPy. Model memory plus Python can exceed a mid-range phone's available RAM. Android can kill the app; temperature, storage and cold-start time may be limiting.
* The HTTPS button tries a real connection and reports the exception. A failed connection alone does not prove absence of network capability; review the merged manifest and permissions alongside it.
