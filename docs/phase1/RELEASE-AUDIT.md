# Release Audit: Public-Repository Readiness (`rabesss/arm-bharat-ai-soc`)

- **State audited:** `main` at `db72e92` (24 November 2026), after the history rewrite and force-push. Every commit SHA changed in that rewrite; the docs cite the new SHAs.
- **Scope:** full Git history reachable from the remote branches, and the working tree: secrets and credentials, personal information, licences and attribution, large files, and content unsuitable for a public competition repository.
- **Policy:** no secrets were printed while auditing.

## Verdict

| Category | Status | Summary |
|---|---|---|
| **Secrets, tokens and private keys** | **PASS** | `gitleaks` over all 313 commits on `main`: no real secrets. Two hits, both public SHA-256 model digests (details in §1). |
| **Model weights and raw third-party data** | **PASS** | No `.pte`, `.bin`, `.safetensors`, `.apk` or raw third-party dataset files in Git. |
| **Large files** | **PASS** | Tracked files total about 37 MB. The largest are the `url.joblib` detector (1.9 MB, two copies), `docs/phase1/report.pdf` (1.9 MB) and the S23 demo clips (6 MP4 files, 5.4 MB together, synthetic inputs). |
| **Licences and attribution** | **PASS** | Root `LICENSE` (MIT, the project's own code, docs and original data) and `THIRD_PARTY_NOTICES.md` (models, datasets and frameworks under their own licences). |
| **Personal information** | **PASS on the remote history** | The rewrite mapped every author and committer to the GitHub noreply address, removed internal notes from every commit and replaced absolute home-directory paths. No personal e-mail, personal name or home-directory path appears in any commit on `main`. |
| **Content fit for public** | **PASS** | The rival-entry teardown and internal planning notes are gone from every commit, not only from the tree. |

**One residual item for the owner:** GitHub keeps pre-rewrite commits reachable through `refs/pull/*` (old PR diffs) until GitHub Support purges them. Ask Support for a purge if those must disappear before the repository goes public.

---

## 1. Secrets scan

- `gitleaks git` over `origin/main` (313 commits) and `gitleaks dir` over the working tree, 24 Nov 2026.
- Two `generic-api-key` hits, both false positives:
  - `README.md` (commit `cfddecf5`): the public SHA-256 digest of Meta's `tokenizer.model`, matched because the line starts with "Tokenizer".
  - `candidates/BEST/triage/asr.py` (commit `0cc17bb8`, on `main` since PR #49): the pinned public SHA-256 of Arm's `whisper-tiny-int8-xnnpack-executorch` model.
- An earlier custom scan (23 Nov) of every historical path, commit message, header, blob and decompressed `.joblib` for AWS, GitHub, Hugging Face, OpenAI/Anthropic, Slack and Google keys, PEM keys, Oracle OCIDs, JWTs, bearer tokens, credentialed URLs, SSH keys, cookies and private hosts found nothing.
- Test fixtures are synthetic: `candidates/BEST/tests/test_live.py` uses documentation and public example IPs; `test_terra_review.py` uses the placeholder number `+91 9876543210`.

## 2. Licences and attribution

- **Project:** MIT (`LICENSE`), covering the project's own code, docs and original data. `THIRD_PARTY_NOTICES.md` lists everything that keeps its own licence.
- **Llama 3.2:** "Built with Llama" attribution and links to Meta's [Llama 3.2 Community License](https://www.llama.com/llama3_2/license/) and [Acceptable Use Policy](https://www.llama.com/llama3_2/use-policy/) in the README and report. No weights or tokenizer are committed.
- **Whisper (Call Guard):** Arm's `whisper-tiny-int8-xnnpack-executorch` (Apache-2.0), downloaded by `bin/callguard --setup-model` with a pinned SHA-256; not committed.
- **Datasets** (`candidates/BEST/DATA.md`, cited in the report): UCI SMS Spam Collection (Almeida, Hidalgo & Yamakami 2011, CC BY 4.0); Mendeley SMS Phishing (Mishra & Soni 2022, CC BY 4.0); PhiUSIIL Phishing URL (Prasad & Chandra 2024, CC BY 4.0); NSL-KDD (Tavallaee et al. 2009; UNB permits redistribution with citation; only trained `flow.joblib` parameters are committed); `karanverma19/Indian_Multilingual_Scam_Message_Dataset` (Apache-2.0); `bolewara/hinglish-scam-text-dataset` (CC BY 4.0).
- **Frameworks:** ExecuTorch 1.6.0 and `executorch-android:1.5.1`, PyTorch (BSD-3-Clause); Arm KleidiAI (Apache-2.0); Chaquopy 17.2.0 (MIT); scikit-learn, NumPy, SciPy, pandas, joblib (BSD-3-Clause); Kotlin and the Android Gradle Plugin (Apache-2.0). `android/python/qrdec.py` is original code with no third-party QR dependency.
- **Challenge page:** `docs/challenge-brief.md` is a summary in our own words with a link to Arm's page; older verbatim copies were replaced in every commit by the rewrite.

## 3. Personal information and internal content

| Item | Status |
|---|---|
| Personal author/committer e-mail on one early commit | Rewritten to the GitHub noreply address in every commit. |
| Internal notes (agent instructions, brainstorm, open questions, brief, infra issues, planning notes) | Removed from the tree and from every commit; ignored in `.gitignore`. |
| Rival-entry teardown and product rating | Removed from the tree and from every commit. |
| Absolute home-directory paths in `research/evals/` | Relative (`candidates/...`) in every commit. Future `bin/eval` runs still write absolute paths, so relativise new summaries before publishing them. |
| Personal name | None in the tree or in commit messages on `main`; the report author is "Prahari contributors". |
| Measurement-host paths (`/var/tmp/arm-bharat-ai-soc-*`) in `models/registry.json`, `eval/`, `bench/` | Not personal; documented in the README as host-specific. |
| Raw S23 and Neoverse-V2 captures (`docs/perf/evidence/`, `evidence/galaxy-s23-20261124/`) | Unedited by design except the cloud box hostname (`<box>`). They include the test phone's `logcat.txt` and device properties of a Samsung Remote Test Lab phone; no account, e-mail or serial was found. |
| Superseded candidate directories (`candidates/BEST_prev_*`, `gen*`, `indic1`) | Harmless; optional cleanup. |

## 4. Note for local clones

Clones and worktrees made before the rewrite still hold the old commits, including local-only refs (for example T3 checkpoint refs on the development machine). They are not on GitHub; delete or re-clone them rather than pushing from them.
