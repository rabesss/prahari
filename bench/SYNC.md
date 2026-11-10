# Audited syncs (controller-owned)

Each push of OMP history or of this branch is checked with `bench/audit_push.py` (allowlist mode) and, on
oracle-a1, `--hidden-check` (advisory). Format: date, range, result.

- 2026-11-10: `d81a866..6f55000` (OMP main, pushed to `omp` and fast-forwarded `main`): 16 commits, 0 failures; hidden check 0 matches (canary planted in a throwaway branch was detected).
- 2026-11-10: `6f55000..ci/benchmark`: 0 failures; hidden check 0 matches.
