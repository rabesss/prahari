# Phase 1 Submission Checklist

- **Submission deadline:** **Wednesday, 25 November 2026, 11:59 PM IST** (ONE submission only — **the owner alone** flips repo visibility and submits the form).
- **Required form deliverables:**
  1. **PUBLIC GitHub repository URL** containing code, documentation, and final report (`https://github.com/rabesss/arm-bharat-ai-soc`).
  2. **PUBLIC 2-minute demo video** (1080p, 16:9, MP4) showcasing real-time on-device operation on target Arm hardware (see [demo-video.md](demo-video.md)).
  3. **Final technical report PDF** (`<= 10 MB`, `docs/phase1/report.pdf`) detailing methodology, results, hardware utilization, and optimization techniques.

## Pre-submission checklist (owner execution order)

- [ ] **1. Merge final parallel feature PRs into `main`:** Wait for integration of `fp-fix-neon`, `feat/arm-perf`, `feat/upi-qr`, `feat/call-guard`, and `feat/hindi-explain` (whichever pass CI and measurement gates).
- [ ] **2. Final docs/report refresh & PDF rebuild:** Rebase `docs/phase1-final` on final `main`, absorb only merged & measured results into `README.md`, `docs/phase1/report.md`, `docs/phase1/EVIDENCE.md`, and `docs/phase1/LIMITATIONS.md`, run `python3 docs/phase1/build_report.py`, visually inspect every page of `docs/phase1/report.pdf`, confirm `< 10 MB` and green CI, and merge into `main`.
- [ ] **3. Complete release-audit cleanups before making repo public** (see [RELEASE-AUDIT.md](RELEASE-AUDIT.md)):
  - [x] Remove `docs/design/COMPETE.md` and `docs/design/RATING-r1.md` from the tree (done on `docs/phase1-final`); optionally scrub them from history via `git filter-repo` (RELEASE-AUDIT §5).
  - [ ] Add a root `LICENSE` file (e.g., MIT or Apache-2.0) or explicit copyright notice.
  - [ ] Decide whether to rewrite personal Gmail in commit `721209c7bf` and whether to remove internal scratch notes (`AGENTS.md`, `docs/BRAINSTORM.md`, `research/QUESTIONS.md`).
  - [ ] Run `gitleaks detect --source . --no-banner --redact` and confirm zero real secrets.
- [ ] **4. Verify third-party licences & attributions:** Confirm **Built with Llama** and Llama 3.2 Community License links, CC BY 4.0 dataset citations and NSL-KDD non-redistribution in `candidates/BEST/DATA.md`, and zero weights/raw datasets in Git.
- [ ] **5. Record & verify the 2-minute 1080p 16:9 MP4 demo video** following [demo-video.md](demo-video.md):
  - [ ] Download final green `arm64-v8a` APK from `main` CI (`prahari-debug-apk`), install on physical Samsung Galaxy S23 (RTL), stage verified `.pte`/`tokenizer.model`, enable **Airplane Mode (`✈`)**, and record live checks + `SecurityException` + Arm Linux `--demo` / `bin/monitor`.
  - [ ] Confirm `1920x1080`, `16:9`, `<= 120 s`, H.264 + AAC audio via `ffprobe`.
  - [ ] Upload to a **PUBLIC** link and verify playback in an **incognito browser window** (no login wall).
- [ ] **6. Flip GitHub repository to PUBLIC** and verify in an **incognito browser window** that `README.md`, `docs/phase1/report.pdf`, and all screenshots render cleanly with zero 404 links.
- [ ] **7. Freeze submission manifest (keep outside the frozen commit):** Record final `main` commit SHA and SHA-256 digests of `docs/phase1/report.pdf`, final `prahari-debug-apk`, demo MP4, and model files (`ab7b7ebf…` / `82e9d319…`).
- [ ] **8. Submit ONCE on the Phase 1 form well before 11:59 PM IST on Wed 25 Nov 2026** and save the confirmation receipt.
