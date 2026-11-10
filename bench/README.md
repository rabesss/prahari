# Detector checks and visible development measurements

`HC_PY` must point to the Python interpreter with the pinned detector dependencies.
`python bench/gate.py [candidate]` runs synthetic fixtures through the candidate's
`bin/predict` and checks each gated row. `python bench/stress.py [candidate]`
reuses the tracked project-written stress suites. Both validate output IDs and
labels. An abstention is not correct for either class; it is reported separately.
Fixture and stress file hashes, counts and per-row outcomes are pinned in
`reference.json`. Use `python bench/update_reference.py [candidate]` only after a
promotion, then review every changed flag and reference before committing.
Fixture flags that agree on aarch64 are provisional until the first x86 CI run
confirms each row; investigate differences before treating them as portable.
Timing and detector artifact size are informational, not gates.

`python bench/readiness.py [candidate]` provides **HEURISTIC** checks only. A
pass does not establish safety, offline operation, competition eligibility,
licensing or completion of a demo. `bin/app --selftest` is a separate check.

For a controller measurement, run `python bench/run.py --cand candidates/BEST
--data /path/to/data/dev`. It measures the named visible dev splits, fails the
relevant task on duplicate/missing/extra IDs or invalid predictions, and writes
aggregate JSON and Markdown under `bench/results/`; the keyword baseline is
untrained. Indic dev was used for tuning and its results are optimistic. Peak
RSS for the in-process keyword baseline is the benchmark process high-water
mark, including previously loaded input; it is not an isolated baseline peak.
These are development measurements on an Arm cloud VM, not a device demo.
No third-party raw inputs or per-item dev outputs are committed.

These tests do not replace private `bin/eval`: they do not run the hidden test,
Llama explanations, the offline end-to-end measurement, or promotion scoring.
Private eval aggregates may be published only under the disclosure policy below.

## Disclosure and controller sync

`python bench/audit_push.py BASE SHA` examines every added/modified historical
blob on an ancestral, complete range using a fail-closed path/content policy.
It lists detector artifacts, rejects unsupported paths, scans for common secret
patterns, constrains eval records and logs, and never prints matched contents.
This does not prove absence of secrets, personal data, hidden content, or
training data in serialized artifacts. A joblib model's provenance must be
reviewed by the owner. CI runs the allowlist audit as an advisory; failures must
be investigated, not assumed safe. Only the controller may run the optional
`--hidden-check` on the appropriately provisioned Oracle host, under `nice`;
it is secondary and cannot prove absence of leaks. Do not send hidden inputs,
per-item hidden predictions, explanations, private evaluation files, raw data,
model weights or credentials to the repository.

The controller audits a fixed OMP SHA before an immutable fast-forward push to
`origin/omp`; integration merges happen in this clean clone through review,
never in the live OMP tree. Record each audited base and SHA in the
controller-owned `research/SYNC.md`. The controller can run these tools from
this clone against the live candidate and visible dev paths without editing the
live tree. Audit failures, including aggregate report paths not explicitly
allowlisted by the current v3 policy, require a controller decision.

## Data and licences

Fixtures in `bench/fixtures` are hand-written for this project, with invented
messages, URLs and NSL-KDD-schema feature values. They are not copied from dev,
hidden or third-party datasets. Stress suites are project-written. The keyword
baseline and benchmark code are project contributions; this directory does not
assert a licence grant beyond the repository's own terms. The candidate's
`DATA.md` and `research/RULES.md` identify source attribution and licences;
missing sources remain readiness failures and require human review.
