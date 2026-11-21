> This directory is the exact tree measured at 89.25 (stamp `20261111-064233`). The promoted, documented copy with the 89.87 final stamp is `candidates/BEST`; the numbers in this file are from the earlier gen2 docs.

# Prahari — on-device scam triage for Indian users

## Problem

Indian phone users receive SMS, WhatsApp-style messages, links and calls crafted to steal OTPs, UPI
credentials and money. Genuine bank, delivery and utility alerts look similar, and the same message
can arrive in English, Hinglish or Devanagari. A useful assistant must separate scams from these
hard negatives without sending private content to a cloud. The Bharat AI-SoC PS3 brief asks for an
on-device cybersecurity assistant that runs on Arm hardware, explains its decision, and stays useful
offline. Prahari answers that: local detectors plus a small Llama explanation model, with no
network at inference time.

## Architecture

Two stages run entirely on the device. This is the mentor's reference pipeline - feature
extraction, then rule/ML detectors, then risk fusion, then Llama via ExecuTorch explaining -
implemented on the CPU; the Performance section lists where each stage runs and what it costs.

**Stage one — mechanism layer over small models.** The scikit-learn models score the wording (SMS
TF-IDF, URL character n-grams, NSL-KDD flows). The mechanism layer decides what the message asks the
reader to do and what it says about itself:

- *Harmful mechanics:* hand over an OTP, PIN, card or account detail; pay a personal number, UPI ID,
  "safe" account or lookalike host; approve a UPI collect request; install a remote-access app; move
  money into crypto; comply with a police/customs threat; pay an upfront job, loan, prize, customs
  or registration fee; open a lookalike page and act there.
- *Benign mechanics:* a completed transaction or delivery record, an OTP notification, a bill or
  insurance notice, an appointment or travel update, an official app/portal pointer, an explicit
  protection clause ("no advance fee", "we never ask for an OTP", "भुगतान लिंक नहीं है"), a promo
  with an opt-out.
- *Routing:* messages with an Indian marker (Devanagari, Hinglish function words, rupee amounts,
  Indian entities) or a strong benign cue use this layer; texts with no such cue keep the generic
  British-SMS model path, so its distribution shift is unchanged.

A decisive harmful mechanic wins over a protection sentence, because scammers write "no OTP needed,
just pay the fee". A lookalike link plus an action on it ("enter your PIN on this page") is decisive
even when the text also says "we never ask". Zero-width characters, full-width forms and spaced-out
capitals are normalised before matching. Three NSL-KDD signatures (failed logins, malformed
fragments, same source/destination) sit on top of the flow model.

**Stage two — grounded explanation.** Llama 3.2 1B turns the verdict, a short type and two evidence
phrases into one or two sentences. The prompt neutralises live URLs, forces a verdict-first sentence
("This message is DANGEROUS/SAFE.") and asks for one evidence phrase verbatim. A contradiction
filter removes a sentence that asserts the opposite of the verdict, and a refusal falls back to an
evidence-only prompt. Fixed remediation steps (1930 helpline, cybercrime.gov.in) are appended. The
CLI writes JSONL; a local web UI exposes the same pipeline.

## Models

The detectors are local joblib artifacts trained by `train.py` from `data/train`: SMS TF-IDF +
logistic regression (UCI SMS corpus), URL character n-grams + logistic regression (PhiUSIIL), and a
histogram gradient-boosted tree over NSL-KDD's 41 features. The Indian-context detector adds
character/word n-grams (an unseen Hindi or Hinglish word can still match on shared spelling) and a
19-dimension mechanism feature vector to a logistic regression, trained on the visible Indian set,
the seed messages and the English SMS corpus. The explanation model is the `llama32-1b-qlora` entry
in `models/registry.json`, run by ExecuTorch's `TextLLMRunner`. Generation is greedy, capped at 40
tokens. A rule layer detects prompt-injection inputs for the explain task.

## Datasets

Development used only `data/train` and `data/dev`: 4,127 SMS rows, 40,000 URL rows, 113,273 NSL-KDD
flow rows, 256 Indian-context rows with categories (plus a 136-row seed set), 607 dev SMS, 4,000 dev
URLs, 12,700 dev flow rows and 64 dev indic rows. Hidden test data and private evaluation files were
never read. `DATA.md` records provenance and licences, including NSL-KDD, the public SMS/URL corpora,
and the Llama 3.2 licence and tokenizer. Evaluation used the controller's `bin/eval` proxy only.

## Results

Historical detection F1, precision, recall, FPR and language accuracy from `eval/run_eval.py` are half-credit proxy metrics: an uncertain verdict contributes ½ to each side of the confusion counts, or ½ credit to language accuracy ([lines 143–163](../../eval/run_eval.py#L143-L163), [419–426](../../eval/run_eval.py#L419-L426)). Published aggregates do not include abstention counts. Conventional metrics with abstention counts: pending (see [EVIDENCE.md](../../docs/phase1/EVIDENCE.md)).

Full proxy run `20261110-081343-gen2-full-r2b` (two repeats, hidden round-2 set): **87.66**, D 0.9024,
E 0.8875, P 0.6701, C 1.0; promotable, no failures or infra errors. The run before the explanation
prompt/latency trim scored 86.97 (same D, E 0.8929, P 0.6289), so detection is unchanged and the
difference is the faster, shorter prompt.

| Detector | F1 | Precision | Recall | FPR | Score |
|---|---|---|---|---|---|
| SMS | 0.9015 | 0.957 | 0.852 | 0.0078 | 0.9015 |
| URL | 0.9949 | 1.000 | 0.9899 | 0.0000 | 0.9949 |
| Indic | 0.9665 | 0.987 | 0.9469 | 0.0125 | 0.9544 |
| Flow | 0.8505 | 0.9706 | 0.7568 | 0.0303 | 0.7643 |

Indic accuracy by language: English 0.977, Hinglish 0.975, mixed 1.0, Hindi 0.875. The starting
baseline scored 81.56 on the same proxy; the round-1 entry scored 85.84 on the previous hidden set.

Explanation checks on 28 items: 28 valid, verdict 0.9, consistency 0.964, mention 0.536, forbidden
1.0, fabrication 1.0, actions 0.929, length 0.946.

A flow-explanation variant was also scored: it treats a lone beaconing description as malicious
(round 1 called a beaconing flow safe) and gives benign flow descriptions an evidence phrase. It
raised E from 0.8875 to 0.8973 (flow by-kind 0.787 to 0.856) with identical detection (D 0.9024);
its overall 87.60 was 0.06 below, inside the latency noise band, so it was not promoted over the
87.66 run.

## Generalisation

Round 1 was the cautionary case: per-template Indian rules scored indic F1 0.967 on the visible set A
but only 0.443 on the rotated set B (F1 0.886, FPR 12.8%), and Hindi accuracy fell to 0.22. The rules
had memorised set A's wording. Round 2 replaces them with scam *mechanisms* (request-vs-statement
framing, secret/payment/threat/lookalike mechanics) over char n-gram features, so unseen Hinglish and
Hindi spellings still land on the same features: hidden indic F1 is 0.9665 with FPR 1.25% and Hindi
accuracy 0.875 on B.

- **Leave-one-category-out** on the visible Indian set (train on 15 categories plus the SMS corpus,
  test the held-out category, benign and malicious): pooled binary F1 1.0 on project-generated synthetic categories; fixed rules active; uncertain mapped to benign; not a category average or real-world estimate. The recorded per-category counts were 10/10 malicious and 0 benign false positives.
- **Three blind paraphrase suites** authored after the rules were frozen: 40 protective-clause
  cases, 21 Hindi/Hinglish rows, 30 mixed English/Hindi rows. Final tree: all correct, with zero
  `uncertain` answers (the runner counts `uncertain` as wrong for either label, stricter than
  `bin/eval`'s half credit). They use
  unseen wording ("nothing to pay", "no fee is charged", "रिफंड आ गया", "running late by 15
  minutes"), not slot swaps. Sources and runner: `research/stress/` at the repo root.
- **Flow signatures** fire on 75 of 74,112 normal train+dev rows (0.10%) and cover the
  guess_passwd/teardrop/pod families; hidden flow F1 moved 0.8265 -> 0.8505.

Remaining risk: 1.25% FPR is not zero, hidden SMS recall is 0.852, and Hindi is the weakest language at
0.875. A scam that asks for nothing and only states a false fact can still pass. The report does not
claim the set-B result proves generalisation to set C, which the controller scores separately.

## Performance on Arm

Measured by `bin/eval --repeats 2` on the Oracle A1 host (2x Neoverse-N1, about 11 GB RAM):
explanation latency **4.72 s per item** over two repeats (130.4 s and 132.2 s for 28 items), peak RSS
2.256 GB, decode 20.1 tokens/s, prefill 82.5 tokens/s, median prompt 199 tokens and 34 generated
tokens. Detector latency is 0.407 ms per item. The candidate bundle is 1.186 GB including the shared
1.1 GB Llama PTE. The UI, CLI and demo run offline; no network calls are made after import.

| Component | Configuration measured |
|---|---|
| Demo box | aarch64 Oracle A1 VM, 2 vCPU Neoverse-N1, about 11 GB RAM, Ubuntu 24.04, no GPU |
| Detectors | scikit-learn / joblib on the CPU; 0.407 ms per item for all four tasks |
| Explanation model | `llama32-1b-qlora`: Llama 3.2 1B Instruct, INT4 group-32 weights, 8-bit dynamic activations, XNNPACK backend, ExecuTorch 1.6 |
| Decoding | greedy (temperature 0), max 40 new tokens, context from the `.pte` |
| Measured run | prefill 82.5 tokens/s, decode 20.1 tokens/s, 4.72 s/item over 28 items, peak RSS 2.256 GB |

The registry's `llama32-1b-spinquant` entry was also measured on this box (about 58-63 prefill and
12-13.5 decode tokens/s under mixed co-tenant load), slower than `qlora`, so `qlora` stays configured.

## Limitations

The 1B model sometimes paraphrases instead of naming the required concept; mention coverage is
0.536, so a larger model or a stricter grounding prompt would help. Two hidden explanation items
still get the wrong verdict, which also costs consistency. Some British ad-spam is labelled benign
because it uses the same protective phrases as genuine Indian notices, so hidden SMS recall is 0.852.
Hindi accuracy on the hidden set is 0.875; other Indic scripts are outside the patterns. Flow
detection uses KDDTrain+ only, so the KDDTest+ shift keeps recall at 0.757 and F1 at 0.8505; novel
attack families (apache2, mscan, snmpget) still look normal. A scam that asks for nothing and only
states a false fact can pass. The explanation model can still produce a wrong detail; deterministic
guards catch fabricated domains and long numbers, not wrong advice.

## Demo plan

The demo device is **oracle-a1**, an Arm-based Linux VM (aarch64, 2x Neoverse-N1, about 11 GB RAM),
the same core class the rules list for Arm-based Linux devices; the owner is confirming with the
organisers that a cloud VM counts. Networking cannot be switched off wholesale because the owner
reaches the box through an SSH tunnel, and `unshare -rn` is not permitted on this host
(`/proc/self/uid_map`: Operation not permitted). The offline proof is therefore the controller's
import-time guard, which is what `bin/eval` injects: it blocks non-loopback connects/DNS and logs the
attempt. `tests/test_offline.py` shows that a socket connect fails under the guard while
`bin/predict` still classifies the lookalike URL correctly.

Three-minute video script:

1. `uname -m` (aarch64) and `lscpu` (Neoverse-N1), `free -h` and `df -h`.
2. Offline detections through the CLI: `bin/app --demo` runs six preset items (SMS electricity/OTP
   scam, genuine bank debit alert, lookalike URL, official IRCTC URL, port-scan flow, prompt-injection
   text). It prints verdict, evidence, the Llama explanation, latency and RSS, and writes
   `demo_output.json`. Show the guard blocking a connect first.
3. `bin/app --port 8765`, bound to 127.0.0.1, reached through the owner's tunnel: paste a message,
   a URL and a flow description; show verdict, evidence, explanation, actions and llm stats.
4. State that everything runs on the local CPU through ExecuTorch, with no network after import, and
   read the measured 4.72 s/item, 2.26 GB peak RSS and 20.1 decode tokens/s.

## Responsible AI, privacy and safety

All processing is local: no message, URL or flow leaves the device, and the import-time guard blocks
network access. Outputs are advisory, evidence is shown instead of hidden scores, and the UI tells
users to verify with the official app. Advice never asks for secrets or clicks in message links, and
scam advice points to cybercrime.gov.in and helpline 1930. The system has no access to OTPs,
credentials or payment APIs. A human can always ignore the verdict, and the tool does not block
communication by itself. The detector is not a substitute for reporting fraud to the bank or police.
