# Project report (draft)

## Problem statement
PS3: on-device cybersecurity assistant for scam SMS, phishing URLs and network intrusions, with plain-language
explanations and remediation, fully local on Arm.

## Architecture
TODO: diagram plus a description of the evidence layer, the advisory LLM and the UI.

## Models
- Llama 3.2 1B Instruct, QLoRA INT4 (EO8), ExecuTorch .pte (official Meta export, executorch-community).
- TF-IDF + logistic regression (SMS, URLs); histogram gradient boosting (NSL-KDD flows).

## Datasets
See DATA.md.

## Results
TODO: per-task F1 / FPR, explanation-quality checks.

## Performance on Arm
TODO: latency, tokens/s, peak memory and model size on Arm Neoverse-N1 (Cortex-A76 class, as in the Raspberry Pi 5).

## Limitations
TODO

## Responsible AI, privacy and safety
No data leaves the device. The assistant only advises: it never blocks, replies, clicks or pays.
