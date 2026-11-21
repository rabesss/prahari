# Prahari: offline scam and phishing triage on Arm

Bharat AI-SoC Challenge 2026, PS3 entry. It checks pasted SMS/WhatsApp-style messages, web links and network-event descriptions. Local inference was measured on an Arm Linux VM; the Android port is experimental and has not been verified on a phone. The web interface accepts pasted inputs and does not monitor a network. It uses **Llama 3.2 1B through ExecuTorch**. Inputs reach the local app over loopback; downloading the model needs network access. The app itself does not block outbound traffic, and offline claims cover only what was tested.

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
   forces a verdict-first sentence and asks for the evidence phrase verbatim; a heuristic filter
   attempts to remove sentences that contradict the verdict, and a refusal falls back to an
   evidence-only prompt. Fixed remediation steps (1930 helpline,
   cybercrime.gov.in) are added. The model treats the input as untrusted data, which defends against
   prompt injection.

## Detector self-test after dependency setup

A full Llama run also requires model access, files and a configured registry.
```sh
# Full judge setup (venv at the repository root, model download, registry): see the top-level README.md.
# Standalone: create the venv here and point the launcher at it.
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
HC_PY="$PWD/.venv/bin/python" bin/app --selftest   # reads ../../models/registry.json, or $HC_MODEL_REGISTRY if set
```
The Python application, launchers and serialized detectors in this directory are the application
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

Historical detection F1, precision, recall, FPR and language accuracy from `eval/run_eval.py` are half-credit proxy metrics: an uncertain verdict contributes ½ to each side of the confusion counts, or ½ credit to language accuracy ([lines 143–163](../../eval/run_eval.py#L143-L163), [419–426](../../eval/run_eval.py#L419-L426)). Published aggregates do not include abstention counts. Conventional metrics with abstention counts for the evaluated candidates are in [the comparison](../../research/evals/C_fix1-vs-BEST.md).

The following 90.73 proxy describes the old BEST at `best-omp-final-9073`, not the promoted candidate. The promoted correctness candidate scored 90.49; see `research/evals/C_fix1-vs-BEST.md` for the comparison and conventional metrics.

`bin/eval` proxy (two repeats, hidden round-2 set): 90.73 (internal proxy, not a judging score) — D 0.9024, E 0.9473, P 0.7486, C 1.0,
promotable. SMS F1 0.9015, URL F1 0.9948, indic F1 0.9665 (FPR 1.25%), flow F1 0.8505. Explanation:
3.67 s/item, 2.256 GB peak RSS, 20.8 decode tokens/s on 2x Neoverse-N1. See REPORT.md for the full
table, generalisation checks and limitations.

Network descriptions in the UI and demo use text rules; the trained flow model accepts NSL-KDD feature records through `bin/predict --task flow` as dataset replay. Live capture is not implemented. The explanation flow independently classifies text and can disagree with the trained model. See `../../docs/phase1/report.md`.
