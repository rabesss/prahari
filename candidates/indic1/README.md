# Kavach Lite: offline scam and phishing triage on Arm

Bharat AI-SoC Challenge 2026, PS3 entry. It checks SMS/WhatsApp messages, web links and network-event
records **entirely on the device**. It flags scams, phishing and intrusions, then explains the verdict in plain
language using **Llama 3.2 1B running through ExecuTorch** on an Arm CPU. Nothing is sent to the internet.

## How it works
1. **Evidence layer (fast, explainable):** transparent Indian-context rules (OTP/PIN demands, UPI
   collect pressure, KYC and authority threats, lookalike domains, shorteners) plus small scikit-learn
   classifiers for messages, URLs and network flows. Genuine-alert protection phrases pull false
   positives down, and a separate rule set catches prompt-injection inputs.
2. **Advisory layer:** Llama 3.2 1B Instruct (INT4 QLoRA, ExecuTorch `.pte`) turns the verdict, scam
   type and compressed evidence into a short explanation. Fixed remediation steps (1930 helpline,
   cybercrime.gov.in) are added. The model treats the input as untrusted data, which defends against
   prompt injection.

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
`bin/eval` proxy: **86.23** (D 0.9144, E 0.8129, P 0.6736, C 1.0). SMS F1 0.9613, URL F1 0.9949,
indic F1 0.967 (FPR 0.0071), flow F1 0.8265. Explanation: 4.75 s/item, 2.211 GB peak RSS, 20.2
decode tokens/s on 2× Neoverse-N1. See REPORT.md for the full table and limitations.
