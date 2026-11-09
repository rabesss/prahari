# Research report: PS3 Kavach Lite (9 Nov 2026)

## Current best

**Candidate:** `candidates/indic1` (the only promoted candidate; `candidates/BEST` is the 69.33
baseline and must not be edited in place).

**Full `bin/eval` proxy:** **86.23** — D 0.9144, E 0.8129, P 0.6736, C 1.0, promotable, no
failures or infra errors. Evidence: `research/evals/20261109-203912-indic31-full-utility/`.

| Run | Score | D | E | P | C |
|---|---|---|---|---|---|
| baseline `BEST` | 69.33 | 0.6720 | 0.7511 | 0.5195 | 0.80 |
| rule layer (`indic16-full`) | 84.36 | 0.8563 | 0.8129 | 0.6673 | 1.00 |
| utility gate + flow 0.10 (`indic31-full-utility`) | **86.23** | **0.9144** | **0.8129** | **0.6736** | **1.00** |

Detection at the current best: SMS F1 0.9613 (FPR 0.0057), URL F1 0.9949 (FPR 0), indic F1 0.967
(FPR 0.0071, no penalty), flow F1 0.8265 (FPR 0.0299, penalised score 0.7444). Explanation on 28
items: 28 valid and plausible, verdict 0.829, mention 0.357, forbidden 1.0, fabrication 1.0,
actions 0.929, length 1.0. Performance: 4.75 s/item, peak RSS 2.211 GB, decode 20.2 tok/s, prefill
83.6 tok/s, detector 0.376 ms/item, bundle 1.184 GB.

## What worked

1. **Indian-context rule layer** (seed rules plus recall patterns). Indic F1 rose from 0.7406 to
   0.9455, then 0.967. Hinglish money requests, postfixed block threats (`card block ho gaya`),
   `details update` ordering, customs/parcel payment requests and Devanagari verify-plus-urgency
   combinations were the useful additions. English SMS did not regress.
2. **Routine utility-bill gate.** A message that names a utility (`bill`, `electricity`, `water`,
   `gas`, `broadband`, `consumer`, `autopay`), carries a link on a plain non-risky host, and makes
   no threat, secret request or deadline is treated as a genuine reminder. This cut indic FPR from
   3.57% to 0.71% (4 false positives removed) and lifted indic F1 from 0.9531 to 0.967, without
   changing visible seed/dev recall.
3. **Flow threshold 0.10.** Recall on KDDTest+ rose from 0.6857 to 0.7202 while FPR moved only from
   0.0281 to 0.0299; flow score rose from 0.7306 to 0.7444. The model's benign scores are
   concentrated well below 0.10, so the lower threshold is cheap.
4. **Compliance and packaging.** C reached 1.0 (offline guard, tests, app selftest, docs) after the
   candidate report/README were brought in line with the measured run.

## What failed, and why

- **Flow threshold 0.05:** recall 0.7330 but FPR jumped to 0.0670; score collapsed to 0.5875
  (`indic20-flow005`). 0.10 is the useful end of the curve.
- **Broad `transaction_update` protection in the utility gate:** made scam and receipt rows benign;
  indic F1 fell to 0.9493 and SMS to 0.9587 (`indic29-utility-txn`). Reverted.
- **Changing protective weights when a link is present:** no indic gain, SMS fell to 0.9587 and E
  fell to 0.7362 (`indic24-linkweight`). Reverted.
- **Evidence-steering prompt:** asking the model to repeat evidence words made it contradict the
  supplied verdict on a benign bank alert; the combined evidence + verdict-pin prompt triggered
  refusals (`I cannot provide...`). Reverted. Verdict-pin alone reduced E from 0.8129 to 0.8057
  (`indic32-full-verdictpin`), so the original prompt is kept.
- **Earlier prompt shortening** (history, c35) caused refusals; the compact prompt is at its safe
  lower bound.

## Open risks (ranked)

- **P0 — explanation mention coverage is 0.357.** This is the largest remaining scoring gap:
  mention is 20% of E, so perfect coverage would add about 0.13 E (about 3.2 proxy points). The
  1B model paraphrases instead of naming the required concept. A grounded concept sentence or a
  better prompt is the next lever; both must keep all six dev examples healthy (no refusals, no
  verdict contradiction).
- **P0 — utility gate generalisation.** The gate is deliberately narrow (no threat, secret request
  or deadline; plain host), but a scam that avoids threat words and uses a plain domain can still
  pass. Visible seed/dev recall is unchanged; re-check on any new data before submission.
- **P1 — Hindi recall.** Hindi rows score 0.679 accuracy (28 rows), while Hinglish, English and
  mixed are 1.0. Bank-security, KYC and refund categories still miss about two rows each.
- **P1 — flow distribution shift.** F1 0.8265 with FPR 2.99% costs about 9% through the FPR
  penalty. More feature engineering or class weighting could help, but every change needs a full
  eval because precision is already 0.97.
- **P2 — latency and memory.** 4.75 s/item and 2.211 GB peak RSS on 2× Neoverse-N1. Re-measure on
  the actual demo hardware (Pi 5 or phone) before the live demo; the bundle includes the shared
  1.1 GB Llama PTE.
- **P2 — docs must track the final run.** Candidate REPORT/README currently quote 86.23; update
  them if the owner runs a different final eval.

## Evidence paths

- Best full run: `research/evals/20261109-203912-indic31-full-utility/` (summary, details, logs).
- Rule-layer full run: `research/evals/20261109-200745-indic16-full/`.
- Baseline: `research/evals/20261109-183806-baseline/`.
- Flow threshold trials: `research/evals/20261109-201032-indic17-flow040/`,
  `...-201148-indic18-flow030/`, `...-201305-indic19-flow015/`, `...-201423-indic20-flow005/`,
  `...-201603-indic21-flow010/`.
- Utility-gate trials: `...-202932-indic26-utility-plainlink/` (broad),
  `...-203756-indic30-utility-routine/` (final narrow form).
- Prompt trials: `...-204514-indic32-full-verdictpin/`; dev refusal checks are not scored.
- Ledger: `research/evals/ledger.jsonl`; auto log: `research/LOG.md`.

## Recommendation and submission steps

Submit **`candidates/indic1`** (86.23 full proxy), not the 69.33 `candidates/BEST`.

1. Copy the candidate tree to the submission repo root so that `bin/predict`, `bin/explain`,
   `bin/app`, `triage/`, `app/`, `artifacts/`, `tests/`, `config.json`, `train.py`, `README.md`,
   `REPORT.md` and `DATA.md` sit at the top level. Keep `candidates/BEST` out of the submitted app.
2. Do not commit model weights. `config.json` -> `model` names the shared registry entry
   `llama32-1b-qlora`; `DATA.md` holds the download commands and licences. Keep the import-time
   network guard and the hidden-data guard intact.
3. Run the owner-side checks once from the repo root: `pytest` (5 tests), `bin/app --selftest`,
   and a final full `bin/eval <candidate>` if the controller asks for a fresh stamp. Quote that
   stamp in REPORT/README.
4. Record the demo with the local UI: a malicious SMS (electricity/OTP), a genuine bank debit alert,
   a lookalike URL, a flow port scan and a prompt-injection text. Show verdict, evidence, actions
   and the offline/ExecuTorch metadata.
5. Use `candidates/indic1/REPORT.md` as the report source; it has the required sections (Problem,
   Architecture, Models, Datasets, Results, Performance, Limitations, Responsible AI).
6. The owner performs the portal registration, form and payment; agents never submit, register or
   publish. The repo may stay private during development; decide visibility before 23 Nov.
