# India dev set v4: held-back result for #48 (fp-fix-neon)

Source for the figure "held-back 79 messages: false-alarm rate 0.340 → 0.277, recall 0.969 unchanged".

## Set
- Written 23 Nov 2026 by Gemini 4 Neon (xhigh) as an independent set for this round: 240 Indian SMS/WhatsApp
  messages (140 genuine, 100 scams; 60% English, 25% Hinglish, 15% Hindi), focused on links, bank/OTP alerts,
  bills, advisories and personal chats. Never used to train or tune any model.
- Split by (label, category) with seed 20261123: tuning 161 (93 genuine, 68 scams), held-back test 79
  (47 genuine, 32 scams). The tuning split was offered to the false-alarm thread; the test split was kept by
  the integrator and scored once per candidate, before merging #48.
- The message files are not committed, so the test split stays held back. SHA-256:
  - `india_dev_v4.jsonl` (all 240): `3416c9f6a105d936b3602b1aa72c5b8a1310a6e96f46a58a4f3d2daaa60e10b2`
  - `v4_tune.jsonl` (161): `a45e6beeadda1860a719e6c05af944584437016713ccbfe8a5f56920318543b7`
  - `v4_test.jsonl` (79): `a1e7cef790f9556b1785412a53a7bc0214e5d0f30bfe8913747bb4e47f068efc`

## Scoring
`research/v3score.py` from the false-alarm project with the file name changed: `triage.detect.predict_text` on
each message; a message counts as flagged when the detector label is 1 (the scorer would count `uncertain` as not
flagged, but no message came out `uncertain` in these four runs). False-alarm rate = FP / (FP + TN) over genuine
messages. Run on oracle-a1, 24 Nov 2026.

| Candidate | Split | F1 | Recall | False-alarm rate | TP | FP | TN | FN |
|---|---|---|---|---|---|---|---|---|
| main 1eb8916 (before #48) | tuning 161 | 0.834 | 0.926 | 0.215 | 63 | 20 | 73 | 5 |
| #48 head 78e1e355 | tuning 161 | 0.857 | 0.926 | 0.172 | 63 | 16 | 77 | 5 |
| main 1eb8916 (before #48) | **held-back 79** | 0.785 | 0.969 | **0.340** | 31 | 16 | 31 | 1 |
| #48 head 78e1e355 | **held-back 79** | 0.816 | 0.969 | **0.277** | 31 | 13 | 34 | 1 |

False alarms on the held-back split by category:

| Category | before #48 | #48 |
|---|---|---|
| govt/telecom advisory | 4 | 3 |
| personal chat | 3 | 1 |
| bank/OTP alert | 2 | 2 |
| delivery/travel notice | 2 | 2 |
| official-site link | 2 | 2 |
| small-business link | 2 | 2 |
| bill/EMI reminder | 1 | 1 |

The one miss on the held-back split is a `hard_impersonation_scam` in both. Reviewer adversarial suite for #48:
22/24 scams caught, 5/13 harmless flagged (unchanged).

Note: the app adds a rule on top of the detector (#45): a bank debit/OTP alert that names its own unofficial
link or private number is shown as SUSPICIOUS even when the detector clears it. That rule is not part of these
numbers.
