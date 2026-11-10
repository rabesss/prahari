# Blind paraphrase suites

These files were authored **after** the candidate's rules were frozen for the round-2 promotion
run, and were never used for training or rule tuning. They exist to test generalisation beyond the
visible set A wording: unseen protective clauses ("nothing to pay", "no fee is charged", "we never
ask for a card number"), Hindi receipt and bill vocabulary, transit and appointment notices, and
scams that use a protective sentence to distract from a lookalike link.

- `protective.jsonl` — 30 genuine notices with varied protection clauses, 10 scams that mimic them.
- `hi_mix.jsonl` — 15 Hindi/Hinglish benign notices, 6 scams.
- `mixed.jsonl` — 20 benign notices across the generator's categories, 10 scams.

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
