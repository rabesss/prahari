# Validation gate (`bin/validate`)

One command for every detector change: it scores the holdout sets, then runs the CI test suites.
Later feature PRs rerun it and paste the table into the PR body.

```sh
# 1. On the base commit, save a baseline (outside the repository):
HC_PY=/path/to/python bin/validate --no-tests --json /var/tmp/<task>/base.json
# 2. On your branch, compare; the gate fails on any recall drop or FPR rise:
HC_PY=/path/to/python bin/validate --baseline /var/tmp/<task>/base.json --json /var/tmp/<task>/head.json
```

`HC_PY` defaults to `.venv/bin/python`, then `python3`. The interpreter needs the packages in
`bench/requirements-ci.txt`.

## What it scores

`uncertain` counts as an error on both sides (a false alarm on a genuine message, a miss on a scam),
as in `research/fpfix/score.py`.

| Set | Rows | Role | Where |
|---|---|---|---|
| `fp_val_v1` | 240 | blind validation, never tuned on | committed (`research/fpfix/fp_val_v1/`) |
| `india_dev_v2` | 120 (24 injection) | visible dev | committed (`bench/dev/`) |
| `v3_test` | 81 | India v3 held-back split | local, `PRAHARI_V3_DIR` |
| `v3_tune`, `v4_tune` | 159, 161 | tuning splits | local, `PRAHARI_V3_DIR`, `PRAHARI_V4_DIR` |
| `v4_test` | 79 | v4 held-back split (integrator copy) | local, `PRAHARI_V4_TEST` |
| `stress_*` | 21-58 each | blind paraphrase suites | committed (`research/stress/`) |
| `r4_injection` | 24 | injection set, `classify_any("injection")` | committed |
| `sealed_v1_1` | 184 | sealed final holdout | local, only with `--sealed` |

SMS rows go through `detect.predict_text`; rows with `route: injection` go through
`classify_any("injection")`, as in `eval/india_v2_runner.py`.

The local sets are not committed (they stay held back). Their SHA-256 is pinned in
`eval/validate.py`. A missing local set is reported as not scored (CI has none of them); a file whose
hash does not match fails the gate, and so does a set the baseline scored that is missing now.

## Protocol rules it enforces

- Per-item errors print only for visible, tuning and blind sets named in `--errors`, never for
  held-back or sealed sets.
- `--sealed` scores the sealed holdout. The protocol allows that once per frozen candidate, with no
  tuning afterwards; record each use in `research/LOG.md`.
- `--baseline` fails on any recall drop or FPR rise on any set (reject your own change if recall
  drops anywhere).
- Tests: the candidate's own `tests/`, `bench/gate.py`, `bench/stress.py`, the evaluator tests and
  `bench/tests`. The bench steps need GNU `time` at `/usr/bin/time`; without it they are skipped and
  the result says `GATE PASS (partial ...)`. CI runs them.

The explanation audit (20 blind items rated correct / weak / wrong, `research/explain-audit.md`) needs
Llama and a judge model, so it is not part of this command.
