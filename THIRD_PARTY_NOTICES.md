# Third-party notices

The source code, tests, documentation and original data written for this project are released under the
MIT License in [`LICENSE`](LICENSE). That licence covers only this project's own work. The models,
datasets, frameworks and other third-party material listed below stay under their own licences. Nothing in
this repository relicenses them, and using Prahari means following their terms as well.

## Models (not committed to this repository)

| Model | Use | Licence | Notes |
|---|---|---|---|
| Llama 3.2 1B Instruct, QLoRA INT4 ExecuTorch export (`executorch-community/Llama-3.2-1B-Instruct-QLORA_INT4_EO8-ET`) | Writes every explanation | [Llama 3.2 Community License](https://www.llama.com/llama3_2/license/) and [Acceptable Use Policy](https://www.llama.com/llama3_2/use-policy/) | **Built with Llama.** Llama 3.2 is licensed under the Llama 3.2 Community License, Copyright © Meta Platforms, Inc. All Rights Reserved. The `.pte` weights and tokenizer are not in this repository and are not covered by the MIT License. Each user downloads them from Hugging Face after accepting Meta's licence. Only their public SHA-256 digests are recorded here. |
| Arm `whisper-tiny-int8-xnnpack-executorch` (INT8 ExecuTorch export of OpenAI Whisper Tiny) | Call Guard speech-to-text (optional preview) | Apache-2.0 per the Arm model card; the original OpenAI Whisper code and weights are MIT | Downloaded by `bin/callguard --setup-model` with a pinned SHA-256; not committed. |

## Datasets

Raw third-party datasets are not committed. The trained detector files in `candidates/*/artifacts/*.joblib`
are scikit-learn models fitted on the datasets below; their attribution follows. The TF-IDF vectorisers in
the SMS and Indian-language models store vocabulary terms and n-grams taken from the training text, so short
fragments of those messages are present inside the `.joblib` files. The flow model stores no rows.

| Dataset | Use | Licence | Source and citation |
|---|---|---|---|
| UCI SMS Spam Collection | SMS detector training and test | CC BY 4.0 | Almeida, Hidalgo and Yamakami (2011). https://archive.ics.uci.edu/dataset/228/sms+spam+collection |
| Mendeley SMS Phishing Dataset | SMS detector training and test | CC BY 4.0 | Mishra and Soni (2022). https://data.mendeley.com/datasets/f45bkkt8pr |
| PhiUSIIL Phishing URL Dataset | URL detector training and test | CC BY 4.0 | Prasad and Chandra (2024). https://archive.ics.uci.edu/dataset/967 |
| NSL-KDD | Network-flow detector training and test | Free to use and redistribute with a citation of the dataset and of Tavallaee et al. (UNB CIC terms) | Tavallaee, Bagheri, Lu and Ghorbani, "A Detailed Analysis of the KDD CUP 99 Data Set", IEEE CISDA 2009. https://www.unb.ca/cic/datasets/nsl.html |
| Indian Multilingual Scam Message Dataset (`karanverma19`) | Seed rows for Indian-language training | Apache-2.0 | https://huggingface.co/datasets/karanverma19/Indian_Multilingual_Scam_Message_Dataset |
| Hinglish and English Financial Scam/Fraud Text Dataset (`bolewara`) | Seed rows for Indian-language training | CC BY 4.0 | https://huggingface.co/datasets/bolewara/hinglish-scam-text-dataset |
| LibriTTS-R, through the Piper voice `en_US-libritts_r-medium` | Voice used to synthesise the Call Guard demo clips (`candidates/BEST/demo/call_guard/*.wav`) | Voice model MIT (`rhasspy/piper-voices`); training data LibriTTS-R CC BY 4.0 (OpenSLR 141) | Koizumi et al. (2023). https://huggingface.co/rhasspy/piper-voices |

Licence texts: CC BY 4.0 https://creativecommons.org/licenses/by/4.0/ ; Apache-2.0
https://www.apache.org/licenses/LICENSE-2.0 . Changes: the data was filtered and used only to fit the models.

The project's own synthetic messages, test fixtures, stress sets and the Call Guard scripts are original work
under the MIT License. `research/fpfix/fp_val_v1/` is additionally dedicated to the public domain under
CC0 1.0, as its README says. Full per-asset provenance is in
[`candidates/BEST/DATA.md`](candidates/BEST/DATA.md).

## Frameworks and libraries (installed separately, not vendored)

| Component | Licence |
|---|---|
| ExecuTorch 1.6.0 and `org.pytorch:executorch-android` 1.5.1 | BSD-3-Clause |
| PyTorch | BSD-3-Clause |
| Arm KleidiAI (through ExecuTorch's XNNPACK backend) | Apache-2.0 |
| scikit-learn, NumPy, SciPy, pandas, joblib | BSD-3-Clause |
| Chaquopy 17.2.0 (Android Python runtime) | MIT |
| Kotlin, Android Gradle Plugin | Apache-2.0 |
| `com.facebook.soloader:soloader`, `com.facebook.fbjni:fbjni` | Apache-2.0 |
| CPython 3.10 and NumPy 1.26.2, bundled into the Android APK by Chaquopy at build time | PSF-2.0 / BSD-3-Clause |
| Piper TTS (`piper-tts`, run once offline to synthesise the demo clips; not shipped, linked or a runtime dependency) | GPL-3.0 for current releases (older `rhasspy/piper` releases: MIT) |

No third-party source code or font files are vendored. The report PDF (`docs/phase1/report.pdf`) embeds
subsets of IBM Plex Sans and JetBrains Mono (SIL Open Font License 1.1). The Android QR decoder
(`android/python/qrdec.py`) is original project code. If an APK is published, these notices should also be
shown in the app.
