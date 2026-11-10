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
`python bench/ratchet.py BASE` (CI, gating) fails when a row that gated in
`reference.json` at `BASE` no longer gates, has a different expected label or (stress) is no longer marked
correct, so
a regenerated or relabelled reference cannot silently ungate a regression. To accept a downgrade, add an entry
`{"suite", "file", "row", "reason"}` to `bench/accepted_downgrades.json` under
`downgrades` in the same change; entries already present at `BASE` do not count again.

Candidates run in a sandbox that mirrors `bin/eval`: working directory is the
candidate, a temporary directory outside the repository, a 900 s timeout that
kills the whole process tree, cloud/GitHub/Hugging Face credential variables removed, loopback-only proxies, offline flags,
and the `eval/guard` import hook with the hidden and private paths denied. Only
`id` and the task field reach `bin/predict`; gold labels never do. On failure the
stderr tail is printed.

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
blob and every commit message on an ancestral, complete range using a
fail-closed path/content policy, and never prints matched contents:
- code and docs only at the top level or under `candidates/`, `research/`,
  `bench/`, `docs/`, `eval/`, `bin/`, `models/` and `.github/workflows/`
  (never `data/`); `.txt` only as `requirements*.txt`; 20 or more data-shaped
  lines (JSON records with dataset keys, wide CSV rows) or 80 or more dataset keys
  (a one-line record dump) fail; JSON `\uXXXX` escapes are undone before the id and
  hidden checks;
- config JSON is parsed strictly (no duplicate keys, NaN or item ids);
- eval JSON: duplicate keys, integers of 2^53 or more, non-finite numbers,
  arrays of arrays, arrays over 50 items and documents over 5000 leaves fail;
- logs: only exact status lines and, in `app.log`, selftest results with scores
  in [0, 1];
- synthetic suites: fixed key sets and at most 500 rows;
- detector artifacts are listed and must be an uncompressed pickle or one complete
  zlib stream with no trailing bytes (gzip, lzma and other encodings fail); the inflated bytes are scanned for item ids and secrets;
- commit messages: at most 8 KB, no secrets, item ids or data-shaped lines;
- item ids include the hidden split formats, explain-set `X-NN` and Indian set
  `B-NNNN`;
- changes to and deletions of controller-owned paths (`bin/eval`, `eval/`,
  `models/registry.json`, `bench/`, `.github/`) are printed for review; the audit is a disclosure gate,
  not an integrity gate.
Exit 1 means policy failures; exit 2 means the audit could not run (including a
base that is not an ancestor).
This does not prove absence of secrets, personal data, hidden content, or
training data in serialized artifacts. A joblib model's provenance must be
reviewed by the owner. CI runs the allowlist audit as an advisory; failures must
be investigated, not assumed safe. Only the controller may run the optional
`--hidden-check` on the appropriately provisioned Oracle host, under `nice`;
it matches hidden ids and normalised hidden and visible third-party texts of 25
or more characters (also inside JSON-decoded strings, commit messages and
inflated artifacts). Flow rows are numeric and are covered by the path and
data-shape rules instead. A hidden match always fails. A visible-text match
fails unless that exact blob is listed with a reason in
`bench/hidden_check_allow.json` (read from the controller's own checkout);
any edit to the blob needs a fresh review. It is secondary and cannot prove
absence of leaks. Do not send hidden inputs,
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
