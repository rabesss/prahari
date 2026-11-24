# Release Audit: Public-Repository Readiness (`rabesss/arm-bharat-ai-soc`)

- **Re-checked 24 Nov 2026 on `main` `28bdb6b` (after PRs #48–#51):** `gitleaks git --log-opts=--all` over all 474 local commits found only the same public-hash false positives; the author-email list is unchanged (one personal-Gmail commit).
- **PR #44 raw captures (`docs/perf/evidence/`, merged `5498500`):** unedited by design. They include the terminated cloud box's ephemeral hostname (`env.txt`) and the RTL phone's `logcat.txt` (render and system lines; no account, e-mail or serial found). Neither is a secret; trim them only if you want a cleaner public tree.
- **Audited commit:** `1eb8916` (`docs/phase1-final`, branched from `main`). First pass scanned the 177 commits reachable from `main`; a second `gitleaks git --log-opts=--all` pass on 23 Nov 2026 covered all 197 local commits (every branch, including the parallel feature branches).
- **Audit date:** 23 November 2026
- **Scope:** Full Git history (all commits, messages, headers, blobs, tags) and working tree — secrets/credentials, personal information (PII), licences/attributions, large files, hidden/third-party data leakage, and content unsuitable for a public competition repository.
- **Policy:** No secrets were printed; Git history was **not** rewritten. Fixes within our branch scope (`README.md`, `docs/phase1/**`) are applied in the tree; out-of-scope tree cleanups and optional history-rewrite commands are listed below for the repository owner.

## Executive verdict: Is it safe to make the repo public?

| Category | Status | Summary |
|---|---|---|
| **Secrets, tokens & private keys** | **PASS (Safe)** | Zero real secrets in any commit or the working tree. Two `gitleaks` false positives, both public model SHA-256 digests: the tokenizer hash in `README.md` (commit `19038f4c`) and the Whisper model hash in `candidates/BEST/triage/asr.py` (commits `5a4231dd` and `5a12e297`; the latter is on `main` since PR #49). |
| **Model weights & third-party raw data** | **PASS (Safe)** | Zero `.pte`, `.bin`, `.safetensors`, `.apk`, `.mp4`, or raw third-party datasets in history or tree. |
| **Large files & repo size** | **PASS (Safe)** | Working tree is 15 MB; largest blob in full history is `1.92 MB` (`url.joblib`). Zero files > 2 MB. |
| **Licences & attributions** | **ACTION NEEDED (High)** | Llama 3.2 attribution + dataset/runtime licences updated in `README.md` and `docs/phase1/report.md`, **but no root `LICENSE` file exists yet** (owner decision). |
| **Content fit for public** | **FIXED IN TREE / history optional** | `docs/design/COMPETE.md` (teardown of 13 rival competition entries + local `/var/tmp` paths) and `docs/design/RATING-r1.md` are removed from the tree on this branch; they remain in history (commit `ef1e619`) unless the owner scrubs it (§5). |
| **Personal info (PII) & local paths** | **REVIEW (Medium)** | One historical commit (`721209c7bf`) uses personal Gmail (`a personal address`) as Git author/committer; 95 `research/evals/*/summary.json` files record `~/...`; `AGENTS.md` mentions unrelated local project `an-unrelated-local-project`. |

**Bottom line:** There are **no leaked credentials, API keys, model weights, or hidden evaluation items**, so making the repo public carries **no credential-exposure risk**. However, **before toggling visibility to Public**, the owner should:
1. Merge this branch (it removes `docs/design/COMPETE.md` and `docs/design/RATING-r1.md` from the tree); optionally scrub them from history.
2. Add a root `LICENSE` file (e.g., MIT or Apache-2.0, or an explicit copyright notice).
3. Decide whether to rewrite the single commit `721209c7bf` that carries a personal Gmail address (and optionally strip `~/` paths and internal scratch docs such as `AGENTS.md`, `docs/BRAINSTORM.md`, `research/QUESTIONS.md`).

---

## 1. Secrets, tokens, keys and credentials scan

**Methods run:**
1. `gitleaks detect --source . --no-banner --redact` across full Git history (177 commits, 4.46 MB scanned) and `--no-git` across the working tree (11.12 MB scanned).
2. Custom Python scanner across all 949 distinct historical paths, commit messages, commit headers, blobs, and decompressed `.joblib` pickles (checking AWS, GitHub, Hugging Face, OpenAI/Anthropic, Slack, Google API, PEM private keys, Oracle OCIDs, JWTs, HTTP Bearer tokens, credentialed URLs, SSH public keys, session cookies, Tailscale/private CGNAT hosts, and generic secret assignments).
3. Existing repository disclosure gate (`bench/audit_push.py` rules verified).

**Findings:**
- **Zero real secrets found** in any commit, commit message, source file, config file, or `.joblib` artifact.
- **Second false positive (all-refs pass):** `generic-api-key` on `candidates/BEST/triage/asr.py:37` in commits `5a4231dd` and `5a12e297` (on `main` since PR #49, so it also shows in a working-tree scan): the pinned public SHA-256 of the Arm `whisper-tiny-int8-xnnpack-executorch` model, not a credential.
- **Evidence bundle added on this branch (`docs/phase1/evidence/`):** raw S23 and Neoverse-V2 logs plus aggregate sealed-holdout scores were scanned before commit (`gitleaks dir`: no leaks). The cloud box's ephemeral hostname was replaced with `<box>`; no holdout item text, logcat, or `perf.data` is included.
- **One confirmed false positive:** `gitleaks` (`generic-api-key`) flags `README.md` (`Tokenizer: \`82e9d319...\``) in commit `19038f4c` and HEAD because the word `Tokenizer` precedes a 64-character hex string. This is the public SHA-256 digest of Meta's `tokenizer.model`, not a credential. Rewording the label in `README.md` to `tokenizer.model SHA-256` resolves the working-tree scanner hit; the historical commit hit is benign.
- **Test fixtures verified synthetic:**
  - `candidates/BEST/tests/test_live.py` contains only documentation/public example IPs (`1.1.1.1`, `93.184.216.34`, `18.161.124.81`) used as mock socket-table rows.
  - `candidates/BEST/tests/test_terra_review.py:193` contains only the standard synthetic Indian placeholder number `+91 9876543210`.

---

## 2. Licences and third-party attribution audit

### Fixed in this branch (`README.md`, `docs/phase1/report.md`, `docs/phase1/SUBMISSION.md`)
- **Llama 3.2 Community License:** Added prominent **Built with Llama** attribution and direct links to Meta's [Llama 3.2 Community License](https://www.llama.com/llama3_2/license/) and [Acceptable Use Policy](https://www.llama.com/llama3_2/use-policy/). Confirmed zero model weights or tokenizers are committed in Git.
- **Dataset provenance & CC BY 4.0 attribution:** Verified `candidates/BEST/DATA.md` lists all six external datasets plus project-generated synthetic data and Llama 3.2; added full author/year citations in `docs/phase1/report.md` and `README.md`:
  - UCI SMS Spam Collection — Almeida, Hidalgo & Yamakami (2011), CC BY 4.0
  - Mendeley SMS Phishing Dataset — Mishra & Soni (2022), CC BY 4.0
  - PhiUSIIL Phishing URL Dataset — Prasad & Chandra (2024), CC BY 4.0
  - NSL-KDD — Tavallaee et al. (2009); UNB permits redistribution with citation (raw data not redistributed here; only trained `flow.joblib` parameters are committed). `candidates/BEST/DATA.md` still says "research use", a stricter reading that can be updated.
  - `karanverma19/Indian_Multilingual_Scam_Message_Dataset` — Apache-2.0
  - `bolewara/hinglish-scam-text-dataset` — CC BY 4.0
- **Runtime & Android dependencies:** Verified and documented upstream licences: ExecuTorch 1.6.0 / `executorch-android:1.5.1` (BSD-3-Clause), PyTorch (BSD-3-Clause), Arm KleidiAI (Apache-2.0), Chaquopy 17.2.0 (MIT), scikit-learn / NumPy / SciPy / pandas / joblib (BSD-3-Clause), Kotlin / Android Gradle Plugin (Apache-2.0). Verified `android/python/qrdec.py` is an original pure-Python ISO/IEC 18004 decoder with zero third-party QR dependency.

### Requires owner decision (not changed automatically)
- **Missing root `LICENSE` file (HIGH):** No `LICENSE` file exists at the repository root. Adding an explicit licence (e.g., MIT or Apache-2.0) or an explicit copyright/all-rights-reserved notice before making the repository public is strongly recommended so judges and downstream readers know reuse terms.

---

## 3. Large files and repository footprint

- Working tree size: **15 MB** total; zero files above 2 MB.
- Top historical blobs:
  1. `candidates/BEST/artifacts/url.joblib` — 1.92 MB (duplicated in `candidates/indic1/artifacts/url.joblib`)
  2. `candidates/BEST/artifacts/indic.joblib` — 1.64 MB
  3. `research/evals/ledger.jsonl` — 0.69 MB
  4. `candidates/BEST/artifacts/sms.joblib` — 0.67 MB
  5. `candidates/BEST/artifacts/flow.joblib` — 0.31 MB
  6. `docs/phase1/img/*.png` — 0.18–0.25 MB each
- No `.pte`, `.bin`, `.safetensors`, `.apk`, `.mp4`, or dataset archives exist anywhere in Git history.
- Rendered report PDF (`docs/phase1/report.pdf`) is checked by `docs/phase1/build_report.py` to stay well under the 10 MB form cap.

---

## 4. Personal info (PII) and content not fit for public

| ID | Severity | Location | Finding | Recommended action |
|---|---|---|---|---|
| **C1** | **HIGH (tree fixed)** | `docs/design/COMPETE.md`, `docs/design/RATING-r1.md` (added in commit `ef1e619`, PR #43) | Detailed competitive intelligence teardown naming 13 rival Bharat AI-SoC PS3 entries, their GitHub URLs, and 25 local `/var/tmp/...` paths (`bharat-intel`, `prahari-rivals`, `prahari-compete`). | Removed from the tree on `docs/phase1-final` (`git rm`); still in history, so optionally purge (commands in §5). |
| **P1** | **MEDIUM** | Commit `721209c7bf8e2b17714010f2078a169a317655e7` (author & committer headers) | Personal Gmail address (`a personal address`) appears in the initial hillclimb setup commit; all other 176 commits use GitHub noreply or tool emails. | Optional: rewrite author/committer email to `26330469+rabesss@users.noreply.github.com` before going public (§5). |
| **C2** | **MEDIUM** | `AGENTS.md`, `docs/BRAINSTORM.md`, `research/QUESTIONS.md`, `research/BRIEF.md` | Internal agent orchestration notes: `AGENTS.md` mentions unrelated local repo `~/projects/an-unrelated-local-project`; `docs/BRAINSTORM.md` mentions personal Google AI Pro entitlement, BME background, and `"ChatGPT dot"`; `research/QUESTIONS.md` discusses private strategy and internal hosts (`instabox`, `oracle-a1`, `boxd`, `sail`). | Either remove internal scratch files from `main` before going public or edit out personal/unrelated-project lines. |
| **P2** | **LOW** | `research/evals/*/summary.json` (95 files) | Records `"candidate": "..."` (OS username and local path; no secrets). | Acceptable if first name is already public on the submission; otherwise sanitize `~/` -> `<workspace>/` or archive `research/evals/` outside the public repo. |
| **C3** | **LOW** | `candidates/BEST_prev_*`, `candidates/gen2`, `candidates/gen7`, `candidates/gen11`, `candidates/indic1` | 8 superseded candidate directories (~5 MB, including a duplicate 1.9 MB `indic1/artifacts/url.joblib`). | Optional cleanup after final freeze; confirm `bench/` and `eval/` tests do not reference them before removing. |
| **C4** | **LOW** | `models/registry.json`, `candidates/BEST/tests/read_explain.py`, `eval/*.py`, `bench/audit_push.py` | Contains `/var/tmp/arm-bharat-ai-soc-*` measurement-host paths. | Already documented in `README.md`; harmless for public visibility. |

---

## 5. Exact remediation commands (for owner — run ONLY after all PRs merge and before making repo public)

> **Warning:** History rewriting (`git filter-repo`) changes commit SHAs and invalidates open PRs and local worktrees. Run **tree-only cleanup** if you do not need to scrub history, OR run **history rewrite once** on a fresh mirror clone right after the final `main` merge and before switching repository visibility to Public.

### Option A — Tree-only cleanup (no history rewrite; fastest and safest)

```sh
# From main after all parallel feature PRs have merged:
git checkout main && git pull --ff-only
# (docs/design/COMPETE.md and RATING-r1.md are already removed by the docs/phase1-final PR)
# Optional: also remove internal scratch/orchestration notes if not needed by judges
# git rm AGENTS.md docs/BRAINSTORM.md research/QUESTIONS.md

# Add your chosen root LICENSE file (e.g., MIT or Apache-2.0), then commit:
git commit -m "chore: remove internal competitive/design scratch files before public release"
```

### Option B — Full history scrub (removes rival dossier AND replaces personal Gmail in `721209c7bf`)

Requires `git-filter-repo` (`pip install git-filter-repo` or OS package). Run on a **fresh bare/mirror clone** outside your active worktrees:

```sh
# 1. Create a fresh mirror backup first
mkdir -p /var/tmp/prahari-public-scrub
git clone --mirror https://github.com/rabesss/arm-bharat-ai-soc.git /var/tmp/prahari-public-scrub/repo.git
cp -a /var/tmp/prahari-public-scrub/repo.git /var/tmp/prahari-public-scrub/repo-backup.git

cd /var/tmp/prahari-public-scrub/repo.git

# 2. Prepare mailmap to replace personal Gmail in commit 721209c7bf
# Replace <PERSONAL_EMAIL> with the address shown by: git show -s --format='%ae' 721209c7bf
cat > /var/tmp/prahari-public-scrub/mailmap <<'EOF'
rabesss <26330469+rabesss@users.noreply.github.com> <PERSONAL_EMAIL>
EOF

# 3. Scrub rival intelligence files + rewrite author/committer email
git filter-repo \
  --mailmap /var/tmp/prahari-public-scrub/mailmap \
  --invert-paths \
  --path docs/design/COMPETE.md \
  --path docs/design/RATING-r1.md

# Optional: if you also want to remove AGENTS.md / docs/BRAINSTORM.md / research/QUESTIONS.md from history,
# add --path AGENTS.md --path docs/BRAINSTORM.md --path research/QUESTIONS.md above.

# 4. Verify zero occurrences remain before force-pushing
git log --all --format='%an <%ae>' | sort -u
git log --all --stat -- docs/design/COMPETE.md docs/design/RATING-r1.md
gitleaks detect --source . --no-banner --redact

# 5. Force-push rewritten history (re-add origin since filter-repo strips it)
git remote add origin https://github.com/rabesss/arm-bharat-ai-soc.git
git push --force --all origin
git push --force --tags origin
```

> **GitHub note after Option B:** Historical commits may remain cached briefly in merged PR diffs on GitHub until GitHub support clears unreachable commits or the public release is pushed to a fresh public repo. If completely clean public history is desired without GitHub PR cache residue, creating a fresh public repository (or force-pushing an orphan squash commit to a release branch) avoids PR-diff caching entirely — confirm the submitted GitHub URL matches the competition form.
