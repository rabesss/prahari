# Phase 1 submission checklist

The owner submits the entry and decides repository visibility. Confirm the final form, access, formats, deadline and time zone with the organiser before submission.

- [ ] Prepare source code on GitHub with setup instructions, the application, a demonstration video and the technical report. Confirm the application format and any outstanding real-device requirements; the Linux application is Python and the Android draft has not demonstrated on-device model generation.
- [ ] Deadline: the organiser email says **25 November 2026**, while the [website](https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html) still says **23 November 2026**. The cutoff time and time zone are unknown. Be ready by **22 November 2026, 23:59 IST**, and confirm the actual deadline.
- [ ] Build the report PDF from the repository root with `pandoc docs/phase1/report.md -o docs/phase1/report.pdf --pdf-engine=xelatex --resource-path=docs/phase1:.`, as documented in the root README. Review the rendered PDF; it is ignored by Git and must not be committed.
- [ ] Decide repository visibility and ensure judges can access the chosen source and application. Judges must obtain model access through Hugging Face and follow the Llama 3.2 licence and access terms; weights are not included in the repository.
- [ ] Verify Llama 3.2 Community License notices, including **Built with Llama**, and applicable acceptable-use and model-access terms. Verify each dataset attribution and licence in [DATA.md](../../candidates/BEST/DATA.md), including NSL-KDD's stated research-use status. Verify ExecuTorch and Chaquopy licence notices for the Android draft before distributing it.
- [ ] Freeze the source commit, build the report PDF from it, and record the commit SHA and SHA-256 hashes of the report, application, model files and video in a submission manifest kept outside that commit (so the recorded SHA stays valid). Paste the manifest into the submission form notes.
- [ ] Report links point to `main` on GitHub; judges need repository access (see visibility above) for them to open.
