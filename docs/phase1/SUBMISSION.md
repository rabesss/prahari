# Phase 1 Submission Checklist

- **Submission deadline:** **Wednesday, 25 November 2026, 11:59 PM IST**, per the owner's Phase 1 form notes; the live challenge page (re-checked 25 Nov) gives 25 November 2026 with no time of day. ONE submission only — **the repository owner alone** flips repo visibility and submits the form.
- **Required form deliverables** (from the form notes and the guidelines e-mailed to the team leader; the public page lists only report, source code and demo):
  1. **PUBLIC GitHub repository URL** containing code, documentation, and final report (`https://github.com/rabesss/prahari`).
  2. **PUBLIC 2-minute demo video** (1080p, 16:9, MP4) showcasing real-time on-device operation on target Arm hardware (see [demo-video.md](demo-video.md)).
  3. **Final technical report PDF** (`<= 10 MB`, `docs/phase1/report.pdf`) detailing methodology, results, hardware utilization, and optimization techniques.

## Pre-submission checklist (owner execution order)

- [x] **1. Merge final parallel feature PRs into `main`:** (done; no open PRs on 25 Nov) Wait for integration of `fp-fix-neon`, `feat/arm-perf`, `feat/upi-qr`, `feat/call-guard`, and `feat/hindi-explain` (whichever pass CI and measurement gates).
- [ ] **2. Final docs/report refresh & PDF rebuild:** (docs refreshed and PDF rebuilt through PR #76 and PR #77; the owner still visually checks every PDF page before submitting) Rebase `docs/phase1-final` on final `main`, absorb only merged & measured results into `README.md`, `docs/phase1/report.md`, `docs/phase1/EVIDENCE.md`, and `docs/phase1/LIMITATIONS.md`, run `python3 docs/phase1/build_report.py`, visually inspect every page of `docs/phase1/report.pdf`, confirm `< 10 MB` and green CI, and merge into `main`.
- [x] **3. Complete release-audit cleanups before making repo public** (see [RELEASE-AUDIT.md](RELEASE-AUDIT.md)):
  - [x] Remove `docs/design/COMPETE.md` and `docs/design/RATING-r1.md` from the tree (done on `docs/phase1-final`); optionally scrub them from history via `git filter-repo` (RELEASE-AUDIT §5).
  - [x] Add the root MIT `LICENSE` and `THIRD_PARTY_NOTICES.md` (public-release cleanup PR).
  - [x] Remove the internal notes from the tree and scrub personal e-mail and local absolute paths (public-release cleanup PR).
  - [x] Confirm and run the prepared history rewrite (personal e-mail in one early commit, internal notes in older commits) before flipping visibility (RELEASE-AUDIT §5).
  - [x] Run `gitleaks detect --source . --no-banner --redact` and confirm zero real secrets (25 Nov, gitleaks 8.30.1 over `main` history and the tree: only the two public SHA-256 model digests listed in RELEASE-AUDIT §1).
- [ ] **4. Verify third-party licences & attributions:** Confirm **Built with Llama** and Llama 3.2 Community License links, CC BY 4.0 dataset citations and the NSL-KDD citation (UNB requires citing the dataset and Tavallaee et al. 2009) in `candidates/BEST/DATA.md`, and zero weights/raw datasets in Git.
- [ ] **5. Record & verify the 2-minute 1080p 16:9 MP4 demo video** following [demo-video.md](demo-video.md):
  - [ ] Download final green `arm64-v8a` APK from `main` CI (`prahari-debug-apk`), install on physical Samsung Galaxy S23 phone, stage verified `.pte`/`tokenizer.model`, enable **Airplane Mode (`✈`)**, and record live checks + `SecurityException` + Arm Linux `--demo` / `bin/monitor`.
  - [ ] Confirm `1920x1080`, `16:9`, `<= 120 s`, H.264 + AAC audio via `ffprobe`.
  - [ ] Upload to a **PUBLIC** link and verify playback in an **incognito browser window** (no login wall).
- [ ] **6. Flip GitHub repository to PUBLIC** and verify in an **incognito browser window** that `README.md`, `docs/phase1/report.pdf`, and all screenshots render cleanly with zero 404 links.
- [ ] **7. Freeze submission manifest (keep outside the frozen commit):** Record final `main` commit SHA and SHA-256 digests of `docs/phase1/report.pdf`, final `prahari-debug-apk`, demo MP4, and model files (`ab7b7ebf…` / `82e9d319…`).
- [ ] **8. Submit ONCE on the Phase 1 form well before 11:59 PM IST on Wed 25 Nov 2026** and save the confirmation receipt.
