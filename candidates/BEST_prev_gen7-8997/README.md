# Prahari: offline scam and phishing triage on Arm

Bharat AI-SoC Challenge 2026, PS3 entry. It checks SMS/WhatsApp messages, web links and network-event
records **entirely on the device**. It flags scams, phishing and intrusions, then explains the verdict in plain
language using **Llama 3.2 1B running through ExecuTorch** on an Arm CPU. Nothing is sent to the internet.

## How it works
1. **Mechanism layer (fast, explainable):** transparent rules decide what a message asks the reader to
   do (share an OTP or PIN, pay a personal number or lookalike host, approve a UPI collect request,
   install a remote-access app, respond to an authority threat, pay an upfront job or prize fee) and
   what it says about itself (completed receipt, OTP notice, bill, appointment, official app, explicit
   protection clause). A decisive harmful mechanic wins over a protection sentence; a lookalike link
   plus an action on it is decisive even when the text says "we never ask". Small scikit-learn
   classifiers score the wording: SMS TF-IDF, URL character n-grams and an NSL-KDD flow model with
   three high-precision intrusion signatures on top.
2. **Advisory layer:** Llama 3.2 1B Instruct (INT4 QLoRA, ExecuTorch `.pte`) turns the verdict, type
   and top evidence phrase into a short explanation. The compact prompt neutralises live links,
   forces a verdict-first sentence and asks for the evidence phrase verbatim; a contradiction filter
   removes a sentence that claims the opposite of the verdict, and a refusal falls back to an
   evidence-only prompt. Fixed remediation steps (1930 helpline,
   cybercrime.gov.in) are added. The model treats the input as untrusted data, which defends against
   prompt injection.

## Setup (one command on a fresh aarch64 Linux box)
```sh
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
bin/app --selftest        # reads ../../models/registry.json, or $HC_MODEL_REGISTRY if set
```
The Python package, entry scripts and joblib detectors in this directory are the **compiled application**
for Phase 1: `bin/app` is the single documented entry (UI, `--demo`, `--selftest`), and `bin/predict` /
`bin/explain` are the batch entry points. The Llama `.pte` and tokenizer are read from the model registry
(`models/registry.json`, `llama32-1b-qlora`); model files are not committed.

## Run
```sh
bin/app --selftest                 # quick check
bin/app --demo                     # six detections; prints verdict/evidence/explanation/latency/RSS,
                                   # writes demo_output.json
bin/app --port 8765                # web UI on http://127.0.0.1:8765
bin/predict --task sms --in in.jsonl --out out.jsonl
bin/explain --in items.jsonl --out explained.jsonl
```
Python 3.12 venv with `executorch==1.6.0`, `torch` (CPU), `scikit-learn`, `pandas`, `joblib`.
Model files are not in git. See DATA.md for provenance and licences.

## Results
`bin/eval` proxy (two repeats, hidden round-2 set): **89.87** — D 0.9024, E 0.9348, P 0.7215, C 1.0,
promotable. SMS F1 0.9015, URL F1 0.9948, indic F1 0.9665 (FPR 1.25%), flow F1 0.8505. Explanation:
4.00 s/item, 2.256 GB peak RSS, 20.4 decode tokens/s on 2x Neoverse-N1. See REPORT.md for the full
table, generalisation checks and limitations.
