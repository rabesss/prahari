# Research report: PS3 Kavach Lite optimisation

Living log of the hillclimb. `bin/eval` is the only source of truth; every number below comes from a
`research/evals/` run. Infrastructure problems go to `INFRA_ISSUES.md`, never fixed here.

## Current best

| Rank | Candidate | Eval | Score | D | E | P | C | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | `candidates/indic1` | `20261109-195205-indic12-final` | **84.36** | 0.8537 | 0.8129 | 0.6711 | 1.00 | rules + TF-IDF, compact Llama prompt |
| 2 | `candidates/BEST` | `20261109-183806-baseline` | 69.33 | 0.6720 | 0.7511 | 0.5195 | 0.80 | starting baseline |

Detection detail for the best full run: sms F1 0.9613 (FPR 0.0057), url F1 0.9949 (FPR 0),
indic F1 0.9455 with **FPR 0.0357** (score after penalty 0.8239), flow F1 0.8034.
Explanation: 28/28 valid, verdict 0.829, mention 0.357, forbidden 1.0, fabrication 1.0,
actions 0.929, length 1.0. Performance: 4.78 s/item, peak RSS 2.217 GB, detector 0.376 ms/item,
size 1.184 GB, prompt 177 tokens median, decode 19.9 tok/s. Documentation rewrite lifted C from
0.80 to 1.00.

## What worked

1. **Indian-context rule layer** (`candidates/indic1/triage/indicrules.py`): request mechanics
   (OTP/PIN demand, UPI collect pressure, KYC threat, fake authority, prize, job/task, screen share)
   plus protection mechanics genuine alerts use ("never ask for OTP", "no fee is needed", official
   app pointer, routine receipt/bill wording). Combined with the SMS TF-IDF probability this moved
   indic F1 from 0.7406 to 0.9455 with no English SMS regression (0.9601 -> 0.9613). The trade is
   explicit: FPR rose from 0.57% to 3.57%, which the proxy's per-point penalty turns into a 13% cut
   on the indic F1; indic's 0.40 weight still makes the move strongly net-positive.
2. **Injection detection** for the explain task's `injection` kind: explicit instruction-override
   patterns classify it as malicious with a named reason.
3. **Compact, protective Llama prompt**: system prompt keeps the "cautious cyber-safety assistant
   for Indian phone users / help people understand" framing, then a short untrusted-content block,
   detector verdict, scam type and 2-3 compact evidence phrases. Median prompt fell 217 -> 176
   tokens, generation 79 -> 39 tokens, explain latency 7.78 -> 4.77 s/item (P 0.5195 -> 0.6713).
4. **Evidence compaction**: duplicate long rule descriptions replaced with one short phrase per
   concept, keeping OTP/PIN/KYC/prize/police/port-scan/domain tokens that demos and readers need.
5. **Benign receipt protection**: the seed set's hard negatives append stray urgency ("Your payment
   of ₹899 has been received please act now"). Completed receipts now stay benign unless they also
   threaten the reader or push a link; urgency alone no longer vetoes the receipt. Seed FPs fell
   5 -> 0 with no recall loss on seed or dev. The hidden FPR did not move (its five equivalents come
   from other templates), so this is robustness rather than a measured proxy gain.
6. **Documentation rewrite**: candidate REPORT sections were all below the 40-word floor, capping C
   at 0.80. Rewritten to the eight required sections, each over 40 words; local check reproduces the
   eval's docs score at 1.0.

## What failed, and why

- **Aggressive system-prompt shortening without protective framing**: the 1B Llama refused on
  4/6 dev explain examples ("I cannot provide an explanation that could be used to commit a scam").
  Refusals score near zero on mention/verdict. Restoring the cautious-helper framing and the
  "help people understand" goal ended refusals on all 6 dev examples.
- **Merging old generic rules with the new Indian rules**: produced near-duplicate evidence strings,
  wasted prompt tokens and read badly. Text detection now uses the Indian rule set alone when it has
  a hit, generic rules only as fallback.
- **Duplicate rule entries in `PROTECTIVE`**: one block was inserted twice; removed. It had been
  returning the same evidence twice for genuine bank alerts.
- **Uncapped generation**: 43-79 tokens every item with no EOS; `tidy()` now cuts at the last complete
  sentence so the cap does not ship half sentences or domain-name fragments.
- **Stricter indic threshold (0.66)**: no FPR change (the false positives are above the old threshold
  or strong-rule hits) and it shaved English SMS F1; reverted to 0.60.
- **Clearing low-band uncertain text to benign**: no hidden FPR change; reverted.
- **"Quote exact numbers and domains" prompt instruction**: did not make the 1B model cite the flow
  count/IP or URL host, grew the prompt, and made a benign item read like phishing. Reverted.
- **"Begin with the verdict and type" prompt instruction**: E stayed exactly 0.8129 on the full set
  (mention 0.357 unchanged) and explain latency rose 4.78 -> 4.94 s/item, so P fell 0.6711 -> 0.6608.
  Reverted to the indic12-final prompt.
- **KV cache cap 512**: measured peak RSS unchanged (2.219 -> 2.217 GB); no benefit, config removed.

## Open risks

- **P0 — indic false positives**: 3.57% FPR on the hidden set costs about 13% of the indic F1 via
  the per-point penalty. 5 of 140 benign messages are flagged. Remaining headroom is larger than
  any latency win.
- **P0 — explanation mentions**: only 35.7% of hidden explanations contain a required mention.
  Flow and URL items are weakest (by-kind 0.672 / 0.730). The prompt carries concrete flow counts/IPs
  and URL domain+TLD; indic12-final ran with them and E/mention were unchanged (0.8129 / 0.357), so
  the remaining mention gap is model behaviour, not missing evidence.
- **P1 — flow detection**: hidden NSL-KDD (KDDTest+) F1 is 0.8034, while the visible dev split scores
  0.9988. The dev split shares the KDDTrain+ distribution, so it cannot measure the real shift and its
  labels cannot guide adaptation. KDDTest+ labels are hidden, so no verifiable tuning lever was
  available in this round; a labelled shifted validation set is the prerequisite for flow work.
- **P2 — latency**: 4.77 s/item. Each 10 prompt tokens ~0.12 s; generation ~20 tok/s. Further
  gains need a shorter system prompt without reintroducing refusals, or fewer evidence phrases.

## Evidence paths

- `research/evals/20261109-183806-baseline/` — starting BEST, 69.33.
- `research/evals/20261109-195205-indic12-final/` — best full run before the type-first prompt trial, 84.36.
- `research/evals/20261109-193740-indic7-full/` — 79.36 with the old docs.
- `research/evals/` — every quick iteration with the same ledger as `research/LOG.md`.

## Recommendation

Submit `candidates/indic1` (docs rewritten, C 1.00). `candidates/BEST` stays untouched as the baseline.

Submission steps for the owner:

1. Copy `candidates/indic1` to the submission repo root (keep `bin/`, `triage/`, `artifacts/`,
   `config.json`, `tests/`; the three `.joblib` files are now tracked by the repo ignore rules, so
   the app runs without retraining; do not ship `__pycache__`).
2. Verify `bin/app --selftest`, `pytest tests`, and a fresh `bin/eval candidates/indic1` on the
   submission host.
3. Record the demo: SMS scam, benign bank alert, phishing URL, port-scan explanation, UI selftest,
   and the on-device latency/RSS numbers above.
4. Use `candidates/indic1/REPORT.md` as the report source; keep `DATA.md` provenance.
