# Kavach Lite: offline scam and phishing triage on Arm

Bharat AI-SoC Challenge 2026, PS3 entry. It checks SMS/WhatsApp messages, web links and network-event
records **entirely on the device**. It flags scams, phishing and intrusions, then explains the verdict in plain
language using **Llama 3.2 1B running through ExecuTorch** on an Arm CPU. Nothing is sent to the internet.

## How it works
1. **Evidence layer (fast, explainable):** transparent rules (KYC threats, OTP/PIN requests, lookalike
   domains, URL shorteners, urgency) plus small scikit-learn classifiers for messages, URLs and network flows.
2. **Advisory layer:** Llama 3.2 1B Instruct (INT4 QLoRA, ExecuTorch `.pte`) turns the verdict and evidence
   into a short explanation. Fixed remediation steps (1930 helpline, cybercrime.gov.in) are added.
   The model treats the input as untrusted data, which defends against prompt injection.

## Run
```sh
bin/app --selftest                 # quick check
bin/app --port 8765                # web UI on http://127.0.0.1:8765
bin/predict --task sms --in in.jsonl --out out.jsonl
bin/explain --in items.jsonl --out explained.jsonl
```
Python 3.12 venv with `executorch==1.6.0`, `torch` (CPU), `scikit-learn`, `pandas`, `joblib`.
Model files are not in git. See DATA.md for the download commands and licences.

## Results
See REPORT.md.
