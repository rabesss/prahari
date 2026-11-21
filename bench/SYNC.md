# Audited syncs (controller-owned)

Each push of OMP history or of this branch is checked with `bench/audit_push.py` (allowlist mode) and, on
oracle-a1, `--hidden-check` (advisory). Format: date, range, result.

- 2026-11-10: `d81a866..6f55000` (OMP main, pushed to `omp` and fast-forwarded `main`): 16 commits, 0 failures; hidden check 0 matches (canary planted in a throwaway branch was detected).
- 2026-11-10: `6f55000..ci/benchmark`: 0 failures; hidden check 0 matches.
- 2026-11-17: `6f55000..45fb11d` (OMP main, pushed to `omp`, merged into `main` via sync PR): 9 commits, 8 policy failures, all controller-reviewed and accepted: (a) `candidates/*/tests/explain_cases.jsonl` (4 copies) are not allowlisted paths; they hold the 28 authored visible explanation cases (keys id, kind, label, input, required_mentions, note; descriptive ids, no hidden ids); (b) `candidates/*/tests/test_basic.py` blob 96a5046 is a visible-text match from the previously allowed seed quotes plus authored strings, now listed in `hidden_check_allow.json`. Hidden check: 0 hidden matches.
- 2026-11-21: `67f6768..sync/omp-round3` (sanitized round-3 snapshot from Oracle main; BEST gen51, research logs, ledger, passing evaluation artifacts and stress sets): 1 commit, 0 failures; hidden check 0 matches. Intermediate gen13b and one non-status tests.log omitted; r4 SMS categories retained in the stress README. Full history and promotion tags remain on Oracle.
