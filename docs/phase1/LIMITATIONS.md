# Jury Q&A: limitations

1. **What is Prahari?** An advisory prototype for pasted messages and URLs, plus two separate network-input experiments; it is not an automatic security service.
2. **Does it satisfy the Llama requirement?** Its explanation uses Llama 3.2 1B through ExecuTorch on an Arm Linux VM. Acceptance of this VM as the required edge demonstration is unconfirmed.
3. **Is an Android app ready?** No Android APK or physical-phone run is established in this evidence. Phone performance is TODO.
4. **Is it offline?** Inference is local. The controller tested with an import-time network guard, but normal app startup does not enforce that guard. A separately blocked-egress demo is still needed.
5. **Does it monitor live traffic?** No. There is no live capture or flow-feature extraction.
6. **What does the flow model do?** It scores supplied NSL-KDD feature records as dataset replay, using a trained model and signatures.
7. **Does Llama explain that model's flow verdict?** No. The explanation interface reclassifies a text description with rules. Its result can disagree with the feature model; present the two separately.
8. **What is the flow false-alarm rate?** 0.0303 in the 22,544-record aggregate evaluation, not a false-alarm rate per hour on a real network (stamp `20261111-075405`, `research/evals/20261111-075405-best-confirm/details.json`).
9. **How well do SMS and URLs work?** In that aggregate evaluation SMS F1 is 0.9015 and FPR 0.0078 (n=1,162); URL F1 is 0.9948 and FPR 0.0 (n=7,997). Dataset and sampling limits apply; a zero observed FPR is not a guarantee.
10. **Does LOCO prove generalisation?** No. It uses the visible synthetic Indian set and fixed rules. The record says 1.0 over 32 categories, but the script calculates pooled binary F1 rather than a category macro-average.
11. **How broad is language support?** The evaluated synthetic set includes English, Hinglish, mixed and Hindi. Hindi had 0.875 accuracy on 32 items; coverage of other Indic languages is not established.
12. **Are explanations always correct?** No. In the 28-item checks one verdict and one action failed; evidence mention was 0.714. These checks do not establish user comprehension.
13. **Can input override the assistant?** There are prompt and pattern-based mitigations and a contradiction filter. They can fail; treating text as data is not a security guarantee.
14. **Can a safe verdict be trusted?** No verdict guarantees safety. Verify independently using a known official app or number; never share secrets on request.
15. **Are the results real-world clinical or field validation?** No. They are dataset and synthetic tests, including a tuned development set and a limited separate evaluation. No field trial is claimed.
16. **What does KleidiAI contribute?** The installed backend is reported to contain `kai_` symbols, but dispatch on this CPU and any speedup are unverified. The supporting symbol record is TODO.
17. **How fast is it on a phone?** Unknown. The 3.67 s/item and 2.256 GB peak RSS are from a shared two-vCPU Neoverse-N1 cloud VM; phone timing, memory and power are TODO.
18. **What is next?** A real Android phone app, live capture and feature extraction, broader Indic coverage, representative licensed data, and independently evaluated usability and safety are planned.

Source paths, timestamps and measurement details: [report](report.md) and [ledger](EVIDENCE.md).
