# Prahari: offline scam and phishing triage on Arm

Bharat AI-SoC Challenge 2026, PS3 entry. It checks pasted SMS/WhatsApp-style messages, web links and network-event descriptions. Local inference was measured on an Arm Linux VM; the Android port is experimental and has not been verified on a phone. The web interface accepts pasted inputs and does not monitor a network; on Linux, `bin/monitor` summarises the device's own live connections for one window (see "Live connection monitor" below). It uses **Llama 3.2 1B through ExecuTorch**. Inputs reach the local app over loopback; downloading the model needs network access. The app itself does not block outbound traffic, and offline claims cover only what was tested.

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
bin/monitor --seconds 6               # Linux: one live window of this device's TCP connections (JSON)
```
Python 3.12 venv with `executorch==1.6.0`, `torch` (CPU), `scikit-learn`, `pandas`, `joblib`.
Model files are not in git. See DATA.md for provenance and licences.

## Live connection monitor (Linux)

`bin/monitor [--seconds N] [--explain]` watches this device's own TCP connections for one window (default 10 s,
a sample every 0.5 s) and prints one JSON document: the numbers, the findings, a one-sentence description, and
the verdict the flow text rules give that description through `detect.classify_any("flow", ...)`, the same check
a pasted description gets. With `--explain` Llama explains it, exactly as `bin/explain` does for one item. It
needs no root and captures no packets. It reads `/proc/net/tcp` and `/proc/net/tcp6` (the kernel's socket table)
at every sample and `/proc/net/snmp` (the kernel's TCP counters for the whole device) at the start and the end.

```sh
# from the repository root
python candidates/BEST/bin/scan_demo.py --ports 150 &       # harmless demo traffic, loopback ports only
candidates/BEST/bin/monitor --seconds 6       # start it in the same second
```

It reports connections opened to many ports on one host (a port scan), repeated new connections to a login port
(22, 23, 3389, 21) from or to one address, half-open sockets piling up on a port, new connections to one remote
at regular intervals, and bursts of failed connects or resets. Thresholds are per window and sit above ordinary
desktop traffic (12 ports opened on one host during the window, or 40 listed on one host at once; 8 new
connections to one login port; 40 half-open sockets; 100 failed connects; 200 resets). Below them the counts
stay in the JSON, and a quiet window is described as quiet and comes out benign.

Limits to keep in mind:
- Each sample is a snapshot. A refused connect, or a connection that opens and closes between two samples, is in
  no snapshot. Open sessions, connects still waiting for a reply and time-wait entries (which last a minute) are
  what get counted.
- The counters carry no address or port. A scan of closed ports, the common kind, therefore shows only as a jump
  in `AttemptFails` (plus `OutRsts` on loopback, or when this device is the one being probed). The monitor says
  so ("...sampling caught too few of them to name a target"), which the rules treat as rejected and report as
  suspicious rather than as a port scan. `bin/scan_demo.py --open` uses its own throwaway listeners so the
  ports stay visible, and the verdict is "a port scan".
- A socket table shows connections, not what they carried. Automation that opens many ssh sessions (Ansible, CI)
  looks to it like password guessing, and a local tool probing local ports looks like a port scan.
- It names addresses, never programs, and blocks nothing. The description quotes peer addresses, which also go
  into the local Llama prompt with `--explain`.
- Linux only. Android 10+ restricts `/proc/net` for apps, so the Android port does not include the monitor, and
  connections in other network namespaces (containers) are not visible.

## Results

Historical detection F1, precision, recall, FPR and language accuracy from `eval/run_eval.py` are half-credit proxy metrics: an uncertain verdict contributes ½ to each side of the confusion counts, or ½ credit to language accuracy ([lines 143–163](../../eval/run_eval.py#L143-L163), [419–426](../../eval/run_eval.py#L419-L426)). Published aggregates do not include abstention counts. Conventional metrics with abstention counts for the evaluated candidates are in [the comparison](../../research/evals/C_fix1-vs-BEST.md).

The following 90.73 proxy describes the old BEST at `best-omp-final-9073`, not the promoted candidate. The promoted correctness candidate scored 90.49; see `research/evals/C_fix1-vs-BEST.md` for the comparison and conventional metrics.

`bin/eval` proxy (two repeats, hidden round-2 set): 90.73 (internal proxy, not a judging score) — D 0.9024, E 0.9473, P 0.7486, C 1.0,
promotable. SMS F1 0.9015, URL F1 0.9948, indic F1 0.9665 (FPR 1.25%), flow F1 0.8505. Explanation:
3.67 s/item, 2.256 GB peak RSS, 20.8 decode tokens/s on 2x Neoverse-N1. See REPORT.md for the full
table, generalisation checks and limitations.

Network descriptions in the UI and demo use text rules; the trained flow model accepts NSL-KDD feature records through `bin/predict --task flow` as dataset replay. Packet capture is not implemented; `bin/monitor` summarises live connections from the kernel's socket table and counters instead. The explanation flow independently classifies text and can disagree with the trained model. See `../../docs/phase1/report.md`.

## Call Guard (preview, behind a flag)

`bin/callguard --demo | --file AUDIO | --transcript TEXT | --record N --consent | --setup-model`
transcribes a voice note on the device (ExecuTorch Whisper Tiny INT8), checks it with the detector and
the digital-arrest rules in `triage/callrules.py`, and has Llama write a STOP warning. The web UI
endpoint `/api/callguard` exists only with `--call-guard` or `PRAHARI_CALL_GUARD=1`. See
`../../docs/call-guard.md`.
