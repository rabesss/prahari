# Jury Q&A: limitations

1. **What is Prahari?** An advisory prototype for pasted messages and URLs, plus two separate network-input experiments; it is not an automatic security service.
2. **Does it satisfy the Llama requirement?** Its explanation uses Llama 3.2 1B through ExecuTorch on an Arm Linux VM. Acceptance of this VM as the required edge demonstration is unconfirmed.
3. **Is an Android app ready?** A draft Android APK reportedly builds in CI at PR #18 head `e74c950`; [CI build and limited parity](https://github.com/rabesss/arm-bharat-ai-soc/actions/runs/44122552734) do not establish on-device model generation. Real-phone execution, exact runtime/model compatibility and measurements remain unverified.
4. **Is it offline?** Inference runs locally and inputs reach the local app over loopback. Downloading the model requires network access; the app itself does not block outbound traffic. The controller tested with an import-time network guard. Offline claims cover only what was tested; a separately blocked-egress demo is still needed.
5. **Does it monitor live traffic?** No. There is no live capture or flow-feature extraction.
6. **What does the flow model do?** It scores supplied NSL-KDD feature records as dataset replay, using a trained model and signatures.
7. **Does Llama explain that model's flow verdict?** No. The explanation interface reclassifies a text description with rules. Its result can disagree with the feature model; present the two separately.
8. **What is the flow false-alarm rate?** 3.03% in the 22,544-record NSL-KDD replay of the shipped version, not a false-alarm rate per hour on a real network. The UI flow-text demo uses separate rules and can disagree with replay.
9. **How well do SMS and URLs work?** The shipped conservative SMS F1 is 0.922 and FPR 0.41% (n=1,162); URL F1 is 0.994 and FPR 0 (n=7,997). Dataset and sampling limits apply; a zero observed FPR is not a guarantee.
10. **Does LOCO prove generalisation?** No. pooled binary F1 1.0 on project-generated synthetic categories; fixed rules active; uncertain mapped to benign; not a category average or real-world estimate.
11. **How broad is language support?** The synthetic evaluation includes English, Hinglish, mixed and Hindi; coverage of other Indic languages is not established.
12. **Are explanations always correct?** No. A blind manual audit of 20 holdout explanations found 5 correct, 8 weak and 7 wrong. Four made false claims about the input; 16 offered generic or misdirected advice, especially in Hindi and Hinglish. User comprehension remains unmeasured.
13. **Can input override the assistant?** There are prompt and pattern-based mitigations and a contradiction filter. They can fail; treating text as data is not a security guarantee.
14. **Can a safe verdict be trusted?** No verdict guarantees safety. Messages that mix an official channel with an unofficial WhatsApp, mobile number or link can still be marked safe. Reviewers wrote 24 scams to beat the rules, and the shipped version still missed 4 of them. Verify independently using a known official app or number; never share secrets on request.
15. **Are the results real-world clinical or field validation?** No. The hidden sets were used repeatedly during development. India v2 was authored blind but used aggregate feedback for tuning, so it is adaptive validation. The separately sealed holdout was kept off the dev box until freeze and scored on the baseline, gen51 and one gen51 review-fix revision; the final PR #30 rule fixes were not scored on it. No field trial is claimed.
16. **What does KleidiAI contribute?** The installed backend is reported to contain `kai_` symbols, but dispatch on this CPU and any speedup are unverified. The controller recorded the symbol inspection and counts in the evidence ledger.
17. **How fast is it on a phone?** Unknown. The shipped version's 3.8 s/item and 2.05 GB peak cgroup memory (systemd scope memory.peak, including page cache; not process RSS) are from a two-vCPU Neoverse-N1 cloud VM; phone timing, memory and power are TODO.
18. **What is next?** A real Android phone app, live capture and feature extraction, broader Indic coverage, representative licensed data, and independently evaluated usability and safety are planned.

Historical detection F1, precision, recall, FPR and language accuracy from `eval/run_eval.py` are half-credit proxy metrics: an uncertain verdict contributes ½ to each side of the confusion counts, or ½ credit to language accuracy ([lines 143–163](../../eval/run_eval.py#L143-L163), [419–426](../../eval/run_eval.py#L419-L426)). Published aggregates do not include abstention counts. The final conventional results count uncertain as an error; coverage is reported in the [report](report.md).

Source paths, timestamps and measurement details: [report](report.md) and [ledger](EVIDENCE.md).

**Hard benign look-alikes.** On the sealed holdout, combined FPR was 0.29 for the baseline and 0.31 for gen51 (the later PR #30 fixes were not scored on it). About 12 of gen51’s 31 false positives contained placeholder `.example` links; the rest were genuine benign notices, especially safety advisories mentioning scam tactics.

**Abstention.** SMS, Indic and injection paths no longer output `uncertain` because conservative scoring counts abstention as an error. The owner-approved flow-text demo retains it for a benign cue next to an attack signal and a lone rejected connection. The earlier exposed v1 challenge set is exploratory only.
