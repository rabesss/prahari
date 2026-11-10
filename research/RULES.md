# Rules: Bharat AI-SoC Student Challenge 2026-27, PS3

Checked 9 Nov 2026. Tags: **[S]** sourced (quoted, linked), **[I]** inferred, **[U]** unknown publicly.
Primary source: the official page https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html
(snapshot in `docs/challenge-brief.md`). Full research notes with every quote: `research/sources/research-A-rules.md`
(rules, timeline, IP), `research/sources/research-B-judging.md` (judging), `research/sources/research-C-approaches.md`
(approaches, datasets, ExecuTorch practice).

## 1. What it is
- 2nd edition, theme "Applied AI on SoC"; run by MeitY through the Chips to Startup (C2S) Programme with Arm, and IIT Delhi as
  mentor institute; supported by Meta. [S]
- Five problem statements. **One winner per problem statement**, chosen "after the final live virtual demo and jury Q&A". Students
  and professionals "compete on equal terms". [S] "Winner selection is at the sole discretion of the challenge organisers." [S]
- The entry: the owner, solo (teams of 1-3 are allowed [S]), registered for **PS3** before registration closed on 19 Oct 2026. [S per
  docs/BRAINSTORM.md] A change of challenge area was allowed only within 15 days of registration, so PS3 is effectively fixed. [I]

## 2. Timeline (dates only; no cutoff hour or timezone is published [U])
| Date | Event |
|---|---|
| 23 Nov 2026 | **Phase 1 (Open Qualifying) deadline**: report, source code and demo [S]. Moved from 30 Nov by the 16 Oct page edit [S]. |
| mid-Dec 2026 | Phase 1 shortlist announced [S] |
| 5 Feb 2027 | Phase 2 PoC deadline (shortlisted teams, with mentorship) [S] |
| 15-16 Feb 2027 | Finals: live virtual demo and jury Q&A; winners announced [S] |
No extension or deadline change was found after 23 Oct (none found, not proof of none) [U].

## 3. PS3 requirements (hard constraints)
- Objective: an on-device cybersecurity assistant that runs "entirely on Arm-based edge hardware without cloud dependency". [S]
- Required functions [S]: monitoring/classifying **network traffic for anomalies and intrusions**; detecting **phishing URLs**;
  detecting **scam SMS**; **explaining threats to non-expert users in plain language**; **recommending remediation actions**;
  **processing data locally** without cloud services.
- **Fatal if broken:** "A model from the Llama family must be used for the advisory or reasoning component and deployed on-device
  using ExecuTorch as the reference runtime." [S] Llama need not do the detection itself; extra non-LLM classifiers fit the
  wording. [I] Fine-tuned, distilled or quantised Llama variants are named only as PS1 examples ("Llama 3.2 1B/3B-Instruct or a
  fine-tuned or distilled variant"). For PS3 they are probably fine but not ruled on. [I] Another LLM (e.g. Qwen) cannot replace
  Llama, and adding one is unaddressed [U]. Conservative default: Llama only.
- Hardware options [S]: Arm Android phones, Raspberry Pi 5 CPU-only, Pi 5 + AI HAT+/HAT+ 2 (Hailo through HailoRT, a separate pipeline
  that must be documented), or Arm Linux devices.
- Optional technologies [S]: CICIDS / UNSW-NB15 / NSL-KDD, PhishTank / OpenPhish, the UCI SMS Spam Collection, libpcap / Scapy, the Hailo SDK.

## 4. Submission (human-only: the owner submits)
- Phase 1 deliverables: "report, source code and demo"; PS3 lists "Source code", "Application", "Demonstration video",
  "Technical report". [S] The project "must be hosted on GitHub and submitted using the challenge submission form". [S]
- Registration email (29 Oct, to the owner) [S]: PS3 assigned; submit "initial solution, source code, demo and report" by
  23 Nov 2026; the submission form "will be shared in the 1st or 2nd week of November, 2026" by email. No portal or login exists.
- PS3 mentoring video (Dr. Vijay Kumar, IIT Delhi, linked from that email) [S]: deliverables are source code on GitHub with
  setup instructions, a working compiled application ("such as an Android APK or a Linux executable"), a demo video
  "showing three detection on the actual device working offline", and a technical report (hardware setup, model
  configuration, measured performance). "Test your system on the actual device such as the Android phone, Raspberry Pi 5
  ... or another arm-based Linux device. Do not rely on the laptop simulation." Show where each model runs. Focus on one main
  use case and keep it modular. Never auto-click links; never claim predictions are always correct. Evaluation: detection
  quality (accuracy, false alarms), on-device performance (response time, memory, offline), user effectiveness.
- PS3 training session: 12 Nov 2026, 17:00-18:00 (timezone unstated, probably IST); the owner attends [S].
- Still unknown [U]: the cutoff hour and timezone, form fields, report template or page limit, video length or format, and
  whether the repo must be public. Whether an Arm cloud VM counts as "the actual device" is unconfirmed [U].
- Questions to organisers go to tech-queries@armbharatchallenge.com with "PS3" in the subject. [S] (Not contacted; that is the owner's call.)

## 5. IP, data and disqualification risks
- Entries must "Be the original work of the entrant(s)", "Be solely owned by the entrant(s)" and "Not violate the intellectual
  property rights of any other person". [S] FAQ 9: participants are responsible for rights and permissions for all code, data and
  materials. [S] How "solely owned" applies to third-party weights and libraries is unclear [U]; the conservative course is to
  cite every third-party asset with its licence in DATA.md and never commit weights or non-redistributable datasets.
- "Incorrect or duplicate entries may result in disqualification." "Duplicate registrations may result in rejection or
  disqualification." [S]
- No rule on AI-assisted coding was found [U]. Conservative: disclose it in the report.
- Licences: UCI SMS Spam, the Mendeley SMS phishing set and PhiUSIIL are CC BY 4.0 (attribution needed) [S per dataset pages]. NSL-KDD
  is UNB research data with no clear redistribution grant, so it is used locally and not redistributed [I]. Llama 3.2 is under the
  Llama 3.2 Community License (attribution "Built with Llama"; acceptable-use policy) [S per the model card]. The owner must accept it [U].

## 6. Judging (no official weights are published) [U]
- The 1st-edition FAQ says judges "may look into": understanding/alignment with the problem statement, technical correctness, novelty, use of
  Arm tools, performance and optimisation, documentation quality and completeness, and demo and presentation. [S]
  https://arm-education.github.io/Arm-Developer-Labs/Challenge_Page.html
- The 2nd-edition theme stresses engineering a product end to end: "AI algorithm development, Optimisation, System integration, Edge
  deployment, Benchmarking, Validation, Product engineering". [S]
- The closest quantitative precedent (the 1st-edition PS5 briefing) judged "completeness, performance, and novelty", with performance measured by "accuracy,
  latency, resource utilization, and power consumption". [S]
- Proxy weights from research B [I]: completeness 15, detection quality 20, Arm integration/compliance 15, performance 15, offline/privacy 10,
  explanation grounding/remediation 10, novelty 8, docs/reproducibility 6, demo/Q&A 6.

## 7. How `bin/eval` maps to this [I]
`score = 100 x (0.30 D + 0.25 E + 0.20 P + 0.25 C)`. The weights are in `eval/weights.json`. It covers the machine-checkable 86% of the
proxy above; novelty and the demo (14%) are human-judged and not scored.
- **D (detection quality, validation):** hidden test sets for SMS (UCI + Mendeley), URLs (PhiUSIIL), an **Indian-context hard set** (the
  largest weight) and NSL-KDD flows (official KDDTest+). Per task, F1 is multiplied by a false-positive penalty, because false alerts cost
  non-expert users.
- **E (plain-language explanation and remediation):** deterministic checks on a hidden explain set covering verdict correctness, agreement between the text and the truth,
  required concepts (with close synonyms), forbidden or hallucinated content (US-centric terms, injected tokens), no invented URLs or phone numbers, safe actions, and length.
- **P (performance and optimisation on Arm):** measured on Oracle's Neoverse-N1, the same Cortex-A76 class as the Pi 5: explain latency, peak
  RSS, detector throughput and footprint.
- **C (compliance, offline, completeness, docs):** a hard gate that a Llama-family `.pte` is actually loaded by ExecuTorch (checked in
  /proc), otherwise the score is capped at 20; plus the offline guard, tests, an app self-test, and README/REPORT/DATA completeness.
- **Known gaps:** no human judging of novelty, clarity or demo quality; the PhiUSIIL URL test is easy (legitimate rows are mostly bare
  homepages); the Indian set is synthetic and templated (320-message sets from one generator: set A, now visible for training, and set B, the hidden test since round 2;
  their `.invalid` link hosts are rewritten to realistic TLDs, but link presence still predicts the label; a third set C from a
  different spec, with balanced links and lengths, is kept by the controller as the final overfitting check); the explain set is small (28 items), so an E change under about 0.04 is noise; Oracle is not a Pi 5 (similar
  cores, different memory system, and other jobs share the machine); the offline guard is an in-process proxy, and the real proof is airplane
  mode on the device.

## 8. Track and approach choice
PS3 is fixed (see §1). To maximise the chance of winning within PS3:
1. Cover **every** PS3 function (SMS + URL + network flows + explanation + remediation + local); research B notes that completeness is
   judged and PS3 lists distinct detection jobs.
2. Make it unmistakably **India-relevant** (KYC/UPI/digital-arrest/courier scams, Hinglish), which a jury at IIT Delhi will value as
   product/social value and novelty.
3. Keep the hybrid design: a fast classical evidence layer plus a Llama 3.2 1B ExecuTorch advisory layer. Ground the explanations in
   detector evidence, which is cheaper, more accurate and more defensible in Q&A than LLM-only classification.
4. Show **measured** Arm optimisation (quantisation variant choice, prompt and KV budget, threads, latency/RSS tables), which the theme and
   1st-edition criteria reward.

## 9. Known strong approaches and precedent (from research C)
- 1st edition: the PS3 winner was **VigiaSENSE** (NIT Rourkela, road anomaly detection on a Pi; a different PS3 topic). Public
  write-ups of the winners stress complete offline pipelines with measured latency on the device. No jury scoresheets are public. [S]
  No public 2nd-edition PS3 repo was found on 9 Nov. [U]
- SMS: char 3-5 + word 1-2 TF-IDF with LR is the standard cheap baseline (UCI F1 of about 0.94 under 10-fold CV). Cross-domain recall on
  new scam styles is the weak spot; a small BiGRU reports better transfer at 5 MB / 0.25 ms. Evaluate English, Devanagari Hindi and
  Hinglish separately; keep OTP/UPI/"abhi" cues (no stemming or stopword removal). [S/I]
- Indian scam categories from RBI/DFS advisories: KYC/account block, UPI refund/collect, electricity disconnection, parcel/courier,
  lottery/reward, OTP/PIN requests. [S] Small public seed sets: karanverma19/Indian_Multilingual_Scam_Message_Dataset (120 rows,
  Apache-2.0) and bolewara/hinglish-scam-text-dataset (only 63 Hinglish rows, CC BY 4.0). [S]
- URLs: lexical-only features (no page fetch). In-dataset accuracy above 0.99 is common and misleading; subdomain injection drops LR,
  XGB and CharCNN to about 0.43 accuracy. Robustness tests (added subdomains, homoglyphs, punycode, encoding, query padding) are
  a real differentiator. [S]
- Flows: small boosted trees on flow summaries; report macro-F1, per-attack recall, FPR and alert volume. Random splits overstate
  results; NSL-KDD KDDTrain+ to KDDTest+ is a real distribution shift. [S/I]
- Calibration plus an abstain ("uncertain") state, and risk-coverage reporting. [S]
- Llama explanations: the detector is authoritative; Llama paraphrases typed evidence; structured output validated (in this entry a failed
  validation may trigger a retry, light post-processing or an abstain/error message, never a templated explanation in place of Llama's); fixed action list (do not click, do not share OTP/PIN, verify through the official app or number, 1930 /
  cybercrime.gov.in); treat inputs as untrusted (prompt injection), and generated text never triggers actions. [S per OWASP LLM01, RBI]
- ExecuTorch: 1.6.0 has aarch64 wheels; KleidiAI low-bit kernels are on by default in XNNPACK. SpinQuant / QAT+LoRA are the
  better-quality 4-bit recipes. Llama 3.2 1B KV cache is about 32 KiB/token in FP16, so set a short context window. Reference speeds:
  Pi 5 llama.cpp Q4_K_M at 10.8 tok/s decode; OnePlus 12 SpinQuant at 50 tok/s. No N1 numbers are public; we measured about 17-21 tok/s
  decode on Oracle. [S/I]
