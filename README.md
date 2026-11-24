# Prahari

Prahari is an offline, on-device scam, phishing, and network-anomaly triage assistant built for the **Arm Bharat AI-SoC Challenge 2026–27 (PS3)** using **Llama 3.2 1B Instruct (INT4 QLoRA)** running through **ExecuTorch** on Arm CPUs. Small local detectors and Indian-context mechanism rules classify messages, URLs, and network events first; Llama 3.2 1B turns that structured evidence into plain-language explanations and safety guidance without cloud inference. Results are advisory and can be wrong. **Built with Llama** ([Llama 3.2 Community License](https://www.llama.com/llama3_2/license/)).

- **Final Phase 1 report:** [docs/phase1/report.pdf](docs/phase1/report.pdf) ([Markdown source](docs/phase1/report.md), reproducible build via `python3 docs/phase1/build_report.py`)
- **2-minute demo script:** [docs/phase1/demo-video.md](docs/phase1/demo-video.md)
- **Hardware performance write-up & harness:** [docs/perf/README.md](docs/perf/README.md) (raw captures in [docs/perf/evidence/](docs/perf/evidence/README.md), harness in [bench/perf/](bench/perf/README.md))
- **Evidence ledger & Q&A:** [docs/phase1/EVIDENCE.md](docs/phase1/EVIDENCE.md) (raw logs in [docs/phase1/evidence/](docs/phase1/evidence/)) · [docs/phase1/LIMITATIONS.md](docs/phase1/LIMITATIONS.md) · [docs/phase1/RELEASE-AUDIT.md](docs/phase1/RELEASE-AUDIT.md)

## Physical Arm hardware & offline results

Prahari has been measured end to end on three Arm targets (all running the exact verified `Llama-3.2-1B-Instruct-QLORA_INT4_EO8.pte` via ExecuTorch XNNPACK):

| Target hardware | Runtime / setup | Warm TTFT | Decode speed | End-to-end / item | Memory | Offline proof |
|:--|:--|--:|--:|--:|--:|:--|
| **Samsung Galaxy S23 (`SM-S911B`)** (Snapdragon 8 Gen 2, `arm64-v8a`, Android 14, Samsung RTL), **APK from `5b59ee2`, 24 Nov evening** | ExecuTorch Android 1.5.1 XNNPACK, Chaquopy portable detectors | **879 ms** (prefill, 165 tok/s) | **32.5 tok/s** warm | **1.857 s** median warm KYC (n = 2); six-item median 1.984 s; gated benign items 0.19–0.31 s | **1,795 MiB PSS** sampled peak | No `INTERNET` permission |
| Same phone, **round-3 build (APK from `b3d61f9`), 24 Nov** | same | ~1.5 s (1.42–1.52 s warm) | 21.5–22.5 tok/s | 2.90 s median warm (2.64–2.80 s airplane mode) | 1,774 MiB PSS | Airplane mode (`airplane_mode_on=1`) |
| Same phone, **earlier r1 APK, 23 Nov** | same | 510 ms (499–510 ms warm) | 43.4 tok/s | 1.20 s (1.42 s airplane mode) | 1.66 GiB PSS (`dumpsys`) | Airplane mode + `SecurityException` |
| **Arm Neoverse-V2 Linux** (8 online vCPUs, Debian 12, `i8mm` + `asimddp`) | ExecuTorch 1.6.0 XNNPACK, Python 3.12 (`perf` profiled) | **540 ms** (2T) / **159 ms** (8T), warm items; all-item mean 922 / 527 ms | **46.7 tok/s** (2T) / **104.3 tok/s** (8T) | **1.27 s** (2T) / **0.53 s** (8T) warm; all-item mean 1.73 / 0.98 s | **2,392 MiB** runner RSS | OS network namespace cut (`unshare -n`: HTTPS/DNS/TCP fail; 6/6 inference succeeds) |
| **Oracle Arm Neoverse-N1 VM** (2 vCPUs, Ubuntu 24.04, eval baseline) | ExecuTorch 1.6.0 XNNPACK, Python 3.12 | — | **19.9 tok/s** | **3.84 s** (eval range 3.8–4.8 s) | **2.05 GB** cgroup `memory.peak` | Evaluation import-time network guard |

- **KleidiAI kernel dispatch confirmed (`perf record -F 99 -g`, Neoverse-V2, 2 threads, 2,222 samples, 0 lost):** named `kai_*` leaf functions accounted for **54.17% of sampled whole-process CPU time**, led by `kai_kernel_matmul_clamp_f32_qai8dxp4x8_qsi4c32p4x8_16x4x32_opt32_neon_i8mm` (**23.27%**, prefill) and `kai_kernel_matmul_clamp_f32_qai8dxp1x8_qsi4c32p4x8_1x4x32_neon_dotprod` (**20.57%**, token decode), traced through `xnn_invoke_runtime` to ExecuTorch's XNNPACK delegate.

## Detection & explanation results (honest summary)

Both holdout benchmarks are reported directly so the current false-alarm trade-off is transparent:

- **Fewer false alarms on genuine messages (PR #48 `c17f753`, PR #65 `dbd7086`):** a contact gate, negated-warning clearing, and (PR #65) Hindi completed-deposit wording read as a record. Recall is unchanged on every set. Figures are for the detector on `main` `5683773`:
  - **India v3 held-back split (`n = 81`):** F1 **0.970**, recall **0.941**, false positive rate **0.000** (0.889 / 0.128 after PR #42; 0.761 / 0.213 before it).
  - **New blind validation set `research/fpfix/fp_val_v1` (`n = 240`, 150 genuine + 90 scam SMS):** FPR **0.207 → 0.107**, recall **1.000**, F1 **0.918**.
  - **v4 held-back split (`n = 79`, never seen by the fixing thread, scored once per candidate; [record](research/v4-heldout/RESULTS.md)):** FPR **0.340 → 0.298**, recall **0.969**, F1 0.785 → 0.805 (0.277 at PR #48's head; PR #54's copied-alert rule added one false alarm). The smaller gain here is the most realistic estimate.
- **Sealed final holdout (`n = 184`: 155 SMS-route, 29 injection-route; scored at several checkpoints, last once for PR #65):** combined F1 **0.812**, recall **0.929**, combined FPR **0.300**, **SMS-route FPR 0.322** (28/87 genuine SMS flagged, down from 35/87; injection FPR 0.154). Earlier: PR #42 0.784 / FPR 0.37, `gen51` 0.802 / 0.31, PR #21 0.709 / 0.29. The remaining false alarms are mostly advisories with a placeholder `.example` link and chats warning relatives about scams. PR #65's validation gate (`bin/validate`) now scores every holdout and fails a change on any recall drop or FPR rise.
- **Repeatedly used project evaluation sets (Oracle, last `bin/eval` after PR #42):** SMS F1 **0.925** (`n = 1,162`), URL F1 **0.994** (`n = 7,997`, FPR 0%), Indic F1 **0.969** (`n = 320`, FPR 3.1%), NSL-KDD flow replay F1 **0.850** (`n = 22,544`, FPR 3.03%). Reviewer adversarial suite: **22/24** scams caught, **5/13** harmless flagged. India v2 adaptive validation: **0.839**.
- **Explanation quality (PR #41):** After blind manual audits (20-item holdout audit: 5 correct, 8 weak, 7 wrong; plus 40-item shuffled audit and S23 inspection), PR #41 removed repeated openings, false absence assertions on `NO RISK` verdicts, and stray generated questions. Automated proxy explanation score rose **0.929 → 0.932**, consistency v2 **0.929 → 0.964**, grounding **27/28**. **PR #50** (`c0fcdc7`) grounds Llama's second sentence in a vetted per-scam-type fact, drops generated sentences that claim things the message lacks, and adds a fixed-text Hindi summary (labelled as not AI-written; Llama's text stays English). Its blind audits (3 × 20 fresh items, at pre-merge revisions; later changes not re-audited) still rated about 5 of 20 English explanations wrong, mostly by repeating a wrong detector evidence phrase, and the longer prompt is ~12% slower.
- **New checks (merged 24 Nov):** an offline **UPI QR / `upi://pay` scam checker** (PR #46 via #51, `105f7e6`) and a **Call Guard preview** for shared voice notes (separate `bin/callguard` CLI; off in the web app unless `PRAHARI_CALL_GUARD=1`) (PR #49, `92c1117`: Whisper Tiny INT8 ASR + digital-arrest rules + Llama; 6.8–13.3 s per call on the Oracle N1 VM, not yet on a phone; see [docs/call-guard.md](docs/call-guard.md)).
- **More checks (merged 24 Nov):** a **typosquat check** for 56 Indian official domains plus direct `.apk` link flagging (PR #70; 2 hits on the Tranco top-1M list, no holdout changed), and on Android a **Copy report** for the Chakshu form and **Send to family** share (PR #64) and a **screen-sharing app banner** when AnyDesk, TeamViewer, AirDroid or RustDesk is installed during a bank/UPI/OTP scam (PR #66, `<queries>` for 8 packages only). An optional **sender check** (PR #67) warns when a bank-style SMS comes from a personal mobile number; a DLT header never makes a message look safer. The Android additions pass CI but have not yet been run on a phone.
- **Tests:** 1,355 candidate and LLM-safety tests pass on `main` at `5683773`.

## Android app

The app in [`android/`](android/) declares **no `INTERNET` permission** and runs portable NumPy/JSON detectors (exported from scikit-learn with zero cross-version unpickling) plus Llama 3.2 1B through ExecuTorch Android XNNPACK.

- **Physical Galaxy S23 (`SM-S911B`, `arm64-v8a`):** the round-3 build (APK from `b3d61f9`) ran on 24 Nov (PR #60): 9 of 10 checks produced a Llama explanation, warm KYC median 2.90 s at ~22 tok/s, Airplane Mode 2.64–2.80 s. That is about half the speed of the r1 APK run on 23 Nov (1.20 s, 43.4 tok/s); the battery read 45.9–46.9 °C and the cause is not established. On the lookalike link every Llama reply failed the explanation checks (the check ended in under 8 s with an error the benchmark read as still running); PR #69 now falls back to the detector's fixed text, and PR #68 skips Llama for NO RISK results by default. A later run the same evening (APK from `5b59ee2`, PR #75) confirmed both on the phone: warm KYC median 1.857 s at 32.5 tok/s, gated benign items 0.19–0.31 s, and the lookalike check ending in the labelled detector fallback in 5.0–6.4 s. That is still slower than the 23 Nov r1 run; no run started on a cool phone (41.7–46.9 °C), samples are small, and the cause is not established. Details: [`docs/perf/s23-gating-20261124.md`](docs/perf/s23-gating-20261124.md). Raw data and four demo clips: [`docs/perf/s23-final-20261124.md`](docs/perf/s23-final-20261124.md), [`evidence/galaxy-s23-20261124/`](evidence/galaxy-s23-20261124/).
- **Round-2 UX additions on `main` (PR #43, verified on Android 14 x86_64 emulator, pending S23 re-test):** Android Share-sheet intake (`ACTION_SEND`, `ACTION_PROCESS_TEXT`), full `EN | हिंदी` UI/steps/evidence toggle (Llama prose remains English with explicit note), offline `Listen / सुनें` text-to-speech of vetted verdict and steps, quoted non-clickable evidence spans with defanged links and masked OTPs, safety-filter replacement badge, opt-in redacted local history (off by default), and an on-device pure-Python QR photo decoder (no camera/storage permission).
- **Round 3 (PR #45, merged `82fe61d`):** Hindi mode with no English chrome, a share preview that runs nothing until you tap Check, an amber **CHECK THIS ALERT** banner for genuine-looking bank alerts (SUSPICIOUS if the alert carries an unofficial link or private number), layout that holds at font scale 2.0, TalkBack labels and memory-hygiene changes (model-creation lock, context reset after each check, capped QR bitmaps); on the emulator, memory held steady over 10 checks (−4.8 MiB from check 2 to 10, PR #55). Re-tested on an Android 14 emulator on 24 Nov (parcel scam DANGEROUS, genuine SBI alert CHECK THIS ALERT, refund UPI link DANGEROUS, Hindi KYC screen) and then on the physical S23 (above).

For APK setup and model staging on a physical phone, see [android/README.md](android/README.md#remote-phone-checklist).

| Physical Galaxy S23 in Airplane Mode (`✈`) | On-device Arm64 ExecuTorch Stats (r1 APK, `43.4 t/s`) | OS Offline Permission Proof (`SecurityException`) |
| :---: | :---: | :---: |
| ![KYC scam result in airplane mode on physical Samsung Galaxy S23](docs/phase1/img/s23-kyc-airplane-top.png) | ![Warm Llama 3.2 1B ExecuTorch arm64-v8a stats on physical Samsung Galaxy S23](docs/phase1/img/s23-kyc-warm1-stats.png) | ![Android missing INTERNET permission SecurityException on physical Samsung Galaxy S23](docs/phase1/img/s23-prove-offline.png) |

## Run on aarch64 Linux

Use Python 3.12 (see [`candidates/BEST/requirements.txt`](candidates/BEST/requirements.txt)). Network access is required only once for package installation and model download, never for inference.

```sh
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r candidates/BEST/requirements.txt
pip install 'huggingface_hub[cli]'
```

Visit the [ExecuTorch-community Llama 3.2 1B QLoRA model page](https://huggingface.co/executorch-community/Llama-3.2-1B-Instruct-QLORA_INT4_EO8-ET), request access, and accept the [Llama 3.2 Community License](https://www.llama.com/llama3_2/license/) and [Acceptable Use Policy](https://www.llama.com/llama3_2/use-policy/). Authenticate locally with the Hugging Face CLI (never commit tokens), download the `.pte` and tokenizer, and verify SHA-256 digests:

```sh
hf download executorch-community/Llama-3.2-1B-Instruct-QLORA_INT4_EO8-ET --local-dir "$PWD/.venv/models/qlora"
sha256sum .venv/models/qlora/Llama-3.2-1B-Instruct-QLORA_INT4_EO8.pte .venv/models/qlora/tokenizer.model
```

- `Llama-3.2-1B-Instruct-QLORA_INT4_EO8.pte` SHA-256: `ab7b7ebf97421c7770ad97d4abfdf8650a7d9f9dc1ce9a0c4663d49f7b7a08ac`
- `tokenizer.model` SHA-256: `82e9d31979e92ab929cd544440f129d9ecd797b69e327f80f17e1c50d5551b55`

Upstream files can change; stop if either hash differs. On a fresh Debian 12 Arm box (the Neoverse-V2 run) two extra steps were needed: `apt install libatomic1`, and replacing the default Torch wheel with the matching CPU-only wheel.

Create a local registry pointing to those files (keeping the tracked `models/registry.json` untouched):

```sh
python - <<'PY'
import json
from pathlib import Path
r = json.loads(Path('models/registry.json').read_text())
p = Path('.venv/models/qlora').resolve()
r['llama32-1b-qlora']['pte'] = str(p / 'Llama-3.2-1B-Instruct-QLORA_INT4_EO8.pte')
r['llama32-1b-qlora']['tokenizer'] = str(p / 'tokenizer.model')
Path('.venv/prahari-registry.json').write_text(json.dumps(r, indent=2))
PY
export HC_PY="$PWD/.venv/bin/python" HC_MODEL_REGISTRY="$PWD/.venv/prahari-registry.json"
```

Run Prahari on Linux:

```sh
candidates/BEST/bin/app --selftest                     # fast detector smoke test
candidates/BEST/bin/app --demo --out .venv/demo.json   # 6-item CLI demo with Llama 3.2 explanations + timings
candidates/BEST/bin/app --port 8765                    # local web UI on http://127.0.0.1:8765
```

### Rootless Linux live connection monitor (PR #40)

On Linux, `candidates/BEST/bin/monitor` samples `/proc/net/tcp`, `/proc/net/tcp6`, and `/proc/net/snmp` every 0.5 s without root or packet capture, summarises anomalies (port scans, login-port repeats, half-open socket bursts, periodic connections, failed-connect/reset surges), and feeds the summary through the flow rules (and optionally `--explain` via Llama 3.2). NSL-KDD 41-feature records are scored separately as dataset replay via `bin/predict --task flow`.

```sh
python3 candidates/BEST/bin/scan_demo.py --open --ports 150 &
candidates/BEST/bin/monitor --seconds 6                # add --explain for local Llama guidance
```

## Build the final report PDF

The PDF at [`docs/phase1/report.pdf`](docs/phase1/report.pdf) is built reproducibly (charts + XeLaTeX layout, verified `< 10 MB`) via:

Needs `matplotlib` and `numpy` (`pip install matplotlib`), `pandoc`, XeLaTeX (TeX Live with `fontspec`, `titlesec`, `fancyhdr`, `lastpage`, `mdframed`, `enumitem`), the fonts IBM Plex Sans, JetBrains Mono and Noto Sans Devanagari, and `pdfinfo` (poppler) for the page count.

```sh
python3 docs/phase1/build_report.py
```

## Call Guard (preview)

`candidates/BEST/bin/callguard` checks a shared voice note or a recording made with consent for the Indian "digital arrest" call script. It transcribes the audio on the device with Arm's INT8 Whisper Tiny through ExecuTorch, applies the existing detector plus call-script rules, and has Llama 3.2 1B write a STOP warning, alongside vetted steps that name 1930 and Sanchar Saathi Chakshu. On the Neoverse-N1 VM, speech-to-text ran 2.7–4.8x faster than real time, and peak RSS was 832 MiB for ASR alone and 2,611 MiB with Llama. Apps cannot tap live call audio. Hindi is not reliable, and the Android hook has not run on a phone. Details, measurements and limits: [docs/call-guard.md](docs/call-guard.md).

## Repository map

- **Phase 1 submission package:** [report.pdf](docs/phase1/report.pdf), [report.md](docs/phase1/report.md), [EVIDENCE.md](docs/phase1/EVIDENCE.md), [LIMITATIONS.md](docs/phase1/LIMITATIONS.md), [demo-video.md](docs/phase1/demo-video.md), [SUBMISSION.md](docs/phase1/SUBMISSION.md), [RELEASE-AUDIT.md](docs/phase1/RELEASE-AUDIT.md), [build_report.py](docs/phase1/build_report.py).
- **Application & Android port:** [candidates/BEST/](candidates/BEST/) (detectors, rules, Llama runner, live monitor, web UI, tests) · [android/](android/) (Kotlin + Chaquopy + ExecuTorch Android app).
- **Provenance & benchmarks:** [candidates/BEST/DATA.md](candidates/BEST/DATA.md) · [bench/README.md](bench/README.md) · [research/stress/README.md](research/stress/README.md) · [docs/challenge-brief.md](docs/challenge-brief.md).

## License

Code is MIT ([LICENSE](LICENSE)). Models and datasets keep their own licences: Llama 3.2 is under the Llama 3.2 Community License (**Built with Llama**), and the weights are not committed or relicensed. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Licences and credits

- **Built with Llama:** Llama 3.2 1B Instruct weights are obtained separately from Hugging Face and governed by Meta's [Llama 3.2 Community License](https://www.llama.com/llama3_2/license/) and [Acceptable Use Policy](https://www.llama.com/llama3_2/use-policy/). No weights or tokenizers are committed to this repository.
- **Datasets:** All training/evaluation datasets are separately acquired and documented in [candidates/BEST/DATA.md](candidates/BEST/DATA.md): UCI SMS Spam Collection (Almeida et al., 2011; CC BY 4.0), Mendeley SMS Phishing Dataset (Mishra & Soni, 2022; CC BY 4.0), PhiUSIIL Phishing URL Dataset (Prasad & Chandra, 2024; CC BY 4.0), NSL-KDD (Tavallaee et al., 2009; UNB permits redistribution with citation; not redistributed here), `karanverma19/Indian_Multilingual_Scam_Message_Dataset` (Apache-2.0), `bolewara/hinglish-scam-text-dataset` (CC BY 4.0), and original project-generated Indian-context synthetic sets.
- **Call Guard ASR model (optional, not committed):** Arm `whisper-tiny-int8-xnnpack-executorch` (Apache-2.0), downloaded by `bin/callguard --setup-model` with a pinned SHA-256.
- **Call Guard demo voice:** the demo clips were synthesised offline with Piper's `en_US-libritts_r-medium` voice (voice model MIT; trained on LibriTTS-R, CC BY 4.0, Koizumi et al. 2023).
- **Upstream frameworks:** ExecuTorch and PyTorch (BSD-3-Clause), Arm KleidiAI (Apache-2.0), Chaquopy (MIT), scikit-learn / NumPy / SciPy / pandas / joblib (BSD-3-Clause), Kotlin / Android Gradle Plugin (Apache-2.0). The Android QR decoder (`android/python/qrdec.py`) is original pure-Python project code.
- **Project licence:** Prahari's own source code, tests, documentation and original data are released under the [MIT License](LICENSE). The MIT License does not cover the Llama 3.2 weights, the Whisper model, the datasets or the frameworks above: they remain under their own licences, listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
