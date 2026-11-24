# Blind paraphrase suites

These files were authored **after** the candidate's rules were frozen for the round-2 promotion
run, and were never used for training or rule tuning. They exist to test generalisation beyond the
visible set A wording: unseen protective clauses ("nothing to pay", "no fee is charged", "we never
ask for a card number"), Hindi receipt and bill vocabulary, transit and appointment notices, and
scams that use a protective sentence to distract from a lookalike link.

- `protective.jsonl` — 30 genuine notices with varied protection clauses, 10 scams that mimic them.
- `hi_mix.jsonl` — 15 Hindi/Hinglish benign notices, 6 scams.
- `mixed.jsonl` — 20 benign notices across the generator's categories, 10 scams.
- `r4_sms.jsonl` — authored 20 Nov after the gen13b freeze and **before** the gen19 rule edits, so it is
  pre-registered for that candidate: 35 scams and 23 benign look-alikes across digital arrest,
  KYC/PAN, electricity, task, loan and official-channel false-safe wording, plus plain notices.
- `r4_injection.jsonl` — authored at the same time: 12 assistant-directed attacks and 12 benign AI
  mentions, scored through `classify_any("injection", text)`.
- `r5_sms.jsonl` — authored 20 Nov after the gen19/gen20 rule edits and **before** any gen21 code change,
  so it is pre-registered for gen21: 7 task-lure and instant-loan scams plus 12 genuine gig, loan, KYC,
  bill, delivery, recharge, webinar and referral notices. These are the two families still seen as
  "lure only, no payment yet".
- `benign_tripwires.jsonl` — authored 21 Nov from the *visible* benign families (bench/dev/india_dev_v2
  benign pairs, train/dev indic negatives) after a hidden diagnostic showed rule-forced India false
  alarms in the prize/investment and remote/safe-account/identity families: 9 benign notices that a
  paraphrase could make look scam-like and 7 matching scams that must stay malicious. It is a
  visible-data proxy for the hidden benign style, not a hidden-set substitute, and was not used for
  training. (`research/LOG.md`, `research/REPORT.md` and `candidates/BEST/REPORT.md` describe it as
  "eight benign notices and eight matching scams"; the file as authored holds 9 and 7.)

The `r4` files were written from the mechanism list in the brief, not from any evaluation row, and were
not used for training. Run them with `research/stress/run.py` (text) and a small `classify_any` loop
for the injection file; the README rules about `uncertain` apply.

Run from the repo root:

```sh
.venv/bin/python research/stress/run.py [candidate-dir]
.venv/bin/python research/stress/loco.py     # leave-one-category-out on data/train+dev indic
```

A row is wrong if the detector answers the opposite label or `uncertain`. The runner counts a malicious
row answered `uncertain` as a miss, and a benign row answered `uncertain` as wrong but not a false alarm;
`uncertain` is printed separately. This is stricter than `bin/eval`, where `uncertain` earns half credit,
so the suite numbers are a lower bound on credit. The suites are small and hand-written; they do not
replace the controller's hidden set, and results on them are reported as supporting evidence only.

The SMS categories are recorded here because the JSONL uses the audit schema:
- `digital_arrest`: r4-001, r4-002, r4-003, r4-004, r4-005
- `kyc_pan`: r4-006, r4-007, r4-008, r4-009, r4-010
- `electricity`: r4-011, r4-012, r4-013, r4-014
- `task`: r4-015, r4-016, r4-017, r4-018, r4-019
- `loan`: r4-020, r4-021, r4-022, r4-023, r4-024
- `official_false_safe`: r4-025, r4-026, r4-027, r4-028, r4-029
- `sim_block`: r4-030
- `bank_security`: r4-031
- `courier`: r4-032
- `refund`: r4-033
- `job`: r4-034
- `crypto`: r4-035
- `utility_benign`: r4-036, r4-037, r4-048, r4-049, r4-056
- `telecom_benign`: r4-038, r4-054
- `kyc_benign`: r4-039, r4-040, r4-051, r4-055
- `advisory`: r4-041, r4-042
- `loan_benign`: r4-043, r4-053
- `job_benign`: r4-044
- `delivery_benign`: r4-045, r4-058
- `upi_benign`: r4-046
- `reward_benign`: r4-047
- `bank_benign`: r4-050, r4-057
- `emi_benign`: r4-052

The `r5_sms` and `benign_tripwires` row notes, kept here for the same reason:
- `task_lure` (scam): r5-001, r5-002, r5-003 (per-action pay), r5-004 (chat-app task)
- `loan_app_lure` (scam): r5-005 (instant loan app), r5-006 (credit-line app), r5-007 (advance fee)
- `job_benign`: r5-008, r5-009, r5-012; `referral_benign`: r5-019
- `loan_benign`: r5-010, r5-011, r5-013 (no-advance-fee clause)
- `notice_benign`: r5-014 (KYC), r5-015 (bill), r5-016 (delivery fee), r5-017 (recharge), r5-018 (webinar)
- benign: bt-001 reward points in the official app; bt-002, bt-003 bank anti-fraud "safe account"
  statements; bt-004 routine app instruction; bt-005 account-closure balance move; bt-006 HR and
  bt-007 branch document request; bt-008, bt-009 mutual-fund risk disclaimers
- scam: bt-010 lottery fee; bt-011 safe-account move; bt-012 app-install lure; bt-013 balance move to a
  new account; bt-014 KYC papers over WhatsApp; bt-015 KYC link; bt-016 guaranteed-returns investment
