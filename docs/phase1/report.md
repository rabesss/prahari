---
title: "Prahari: offline threat triage on Arm"
subtitle: "Bharat AI-SoC Challenge 2026–27, PS3 | Phase 1 technical report"
date: "21 November 2026"
geometry: margin=0.85in
fontsize: 11pt
---

## Summary

Prahari is an Arm CPU prototype that helps people assess suspicious messages, links and described network events without a cloud inference service. Small trained detectors and transparent rules produce a verdict and evidence; a Llama 3.2 1B model running through ExecuTorch turns that evidence into plain-language guidance. Its Indian-context mechanism layer looks for actions such as sharing an OTP, paying an unverified recipient or responding to a service-disconnection threat, while recognising cues in ordinary notices. A separate trained network model scores NSL-KDD feature records as dataset replay. The system is designed to help a person decide what to check next, not to act automatically or certify safety [S1, S2].

## Highlights

Round-3 measurements are from Oracle, an Arm Neoverse-N1 VM with two vCPUs [S8].

- Shipped `candidates/BEST` is gen51 (content hash `46f30b36…`), promoted after a controller 3+3 interleaved confirmation.
- Conservative F1: SMS **0.904**, URL **0.994**, Indic **0.971**, NSL-KDD flow replay **0.851**. These evaluation sets were used repeatedly during development.
- On the sealed final holdout, combined F1 improved from **0.709 to 0.802**, while FPR rose from **0.29 to 0.31**. False alarms remain high.
- End-to-end time was about **3.8–4.8 s/item**; process-tree peak RSS was about **2.05–2.34 GB**, measured by systemd scope `memory.peak`, which includes page cache.
- A blind manual audit of 20 holdout explanations found 5 correct, 8 weak and 7 wrong; 4 made false claims about the input and 16 gave generic or misdirected advice.

**What is not done yet.** Live network capture and a measured physical-phone run remain unverified or planned. A draft Android APK reportedly builds in CI at PR #18 head `e74c950`; [CI build and limited parity](https://github.com/rabesss/arm-bharat-ai-soc/actions/runs/44122552734) do not establish on-device model generation. Real-phone execution, exact runtime/model compatibility and measurements remain unverified. The Arm results come from a shared cloud VM, and an independently blocked-egress demonstration is still needed. These datasets and automated checks do not establish field performance or guarantee safe advice [S2, S7].

\newpage

## Problem and Indian context

An Indian user may see a payment demand in Hinglish, a fake KYC notice, or a message threatening to cut electricity. A genuine receipt or protective bank notice can use similar vocabulary. Prahari therefore considers what the sender asks the recipient to do, alongside statistical scores, instead of treating every mention of a bank, OTP or payment as conclusive. Its evidence and next steps aim to make a result understandable to a non-expert. The PS3 brief calls for local threat detection, explanations and remediation, using Llama through ExecuTorch on Arm [S1, S2].

## Why India

India's digital payments and public services make familiar institutions useful pretexts for fraud. A UPI collect request can be disguised as a refund, while fake KYC or Aadhaar updates, electricity-disconnection threats and courier or customs fees urge immediate action. “Digital arrest” scams impersonate officials and threaten detention; the Ministry of Home Affairs has described both fake digital arrests and courier impersonation ([PIB, 2024](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2077948)). Hindi and Hinglish messages can mix scripts and English terms, making context and requested actions important alongside keywords.

NCRB recorded **101,928 registered cybercrime cases in 2024**. Separately, I4C reported **more than 6,589,201 financial-fraud complaints** and **more than Rs 55,050 crore reported** on the national portal for 2021–2025 ([PIB, 2026](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2287039)). Complaints and registered cases are different measures and do not measure this prototype's target population. Prahari examines pasted text for such mechanisms and offers verification steps; its synthetic language tests do not establish India-wide effectiveness.

## Architecture

```text
+-------------------------+     +------------------------------+
| Pasted message or URL   | --> | Rules + trained detectors    |
+-------------------------+     | and verdict fusion           |
                                +--------------+---------------+
+-------------------------+                    |
| Network description     | --> Text rules -----+--> verdict + evidence
+-------------------------+                    |            |
                                               |            v
                                               |  +-----------------------+
                                               |  | Llama / ExecuTorch    |
                                               |  | explanation + actions |
                                               |  +-----------------------+
+-------------------------+
| NSL-KDD feature record  | --> trained flow model + signatures
+-------------------------+       --> separate verdict + evidence
                                     (dataset replay only)
```

The message layer combines TF-IDF and a logistic classifier with Indian-context mechanism features and rules. The URL model uses character n-grams and indicators. The network feature model uses a histogram gradient-boosted tree and intrusion signatures [S2]. The UI's network description follows text rules, and `bin/explain` independently reclassifies that description. It does **not** receive or explain the feature-model verdict; the two results can disagree. Neither path performs live capture.

\newpage

## Arm and ExecuTorch optimisation

**Target and method.** Measurements were made on Oracle, an aarch64 Neoverse-N1 VM with two vCPUs. End-to-end processing took about 3.8–4.8 s per item; process-tree peak RSS was about 2.05–2.34 GB using systemd scope `memory.peak`, which includes page cache. Shared-host load can affect timing [S8].

**Model and backend.** Prahari uses the ExecuTorch XNNPACK CPU backend with Llama 3.2 1B Instruct QLoRA. The language model is used to explain detector evidence, not to classify inputs [S2].

**Keep detection fast.** Llama is invoked for explanation, not classification. The small detector produces a verdict and selected evidence first; the advisory model receives a compact prompt and generates at most 40 new tokens with greedy decoding in the Linux reference runner; the draft Android port uses callback-count stopping, not a guaranteed token cap. This makes the cost of the language model visible and keeps it out of the detector path [S2].

**Compact the prompt.** An evidence-first prompt and bounded generation reduce the amount of text passed to the model. Shared-host measurements do not establish a controlled latency gain from prompt compaction [S4].

**KleidiAI.** KleidiAI micro-kernels are linked into the installed ExecuTorch 1.6.0 XNNPACK backend; dispatch on Neoverse-N1 was not profiled; no speedup claimed. The 17 November symbol inspection found 517 `kai_` symbols in the XNNPACK backend library; its command, additional library counts and limitations are recorded in the evidence ledger [S5]. Symbol presence alone does not establish that a particular inference used those kernels.

## Android deployment (in progress)

A draft Android APK reportedly builds in CI at PR #18 head `e74c950`; [CI build and limited parity](https://github.com/rabesss/arm-bharat-ai-soc/actions/runs/44122552734) do not establish on-device model generation. Real-phone execution, exact runtime/model compatibility and measurements remain unverified. Device identity, permissions, latency, throughput and peak memory will be recorded after a real-phone run [S7].

\newpage

## Evaluation and data

Prahari evaluates detection independently from generated explanations. The following conventional metrics count `uncertain` as an error. Coverage is the fraction receiving a decided label; each `n` includes both classes. These hidden sets were used repeatedly during development and are not pristine holdouts. A zero observed FPR describes this sample, not a guarantee [S8].

| Set | n | Coverage | Precision | Recall | F1 | FPR |
|:--|--:|--:|--:|--:|--:|--:|
| SMS | 1,162 | 1.0 | 0.976 | 0.842 | 0.904 | 0.41% |
| URL | 7,997 | 0.998 | 1.000 | 0.988 | 0.994 | 0 |
| Indic | 320 | 1.0 | 0.994 | 0.950 | 0.971 | 0.63% |
| NSL-KDD flow replay | 22,544 | 1.0 | 0.971 | 0.757 | 0.851 | 3.03% |

Historical `eval/run_eval.py` detection metrics gave half credit to uncertain verdicts, and historical language accuracy gave half credit for abstentions. Those earlier aggregates do not include abstention counts and are not directly comparable to the conservative figures above [S3].

**Round-3 optimisation.** Proxy v3 is an internal engineering score on a 100-point scale, not an official judging score. Candidates were evaluated with gates and isolated runs; gen51 was promoted after a controller 3+3 interleaved confirmation. Mean proxy history: PR #21 baseline 73.4 → gen13b 84.7 (+11.31) → gen35b 85.1 (+0.85) → gen51 86.6 (+1.92). The rounded means and reported improvements are recorded separately [S8].

**India v2 adaptive validation.** A different agent authored 400 items blind. Aggregate-only feedback was used for tuning, making this a validation set, not a test. Penalized score I rose from 0.377 at baseline to 0.830 for gen51; injection recall was 0.70 and benign-AI-mention FPR was 0 [S8]. The earlier v1 challenge set was previously exposed and is exploratory only.

### Sealed holdout

The final holdout contained 184 items after independent label review: 84 malicious and 100 benign, with 155 SMS-route and 29 injection-route items. A different model family (Gemini) authored it blind in a different style. It was never seen during development, stayed off the dev box until freeze, and was scored once [S8].

| Metric | PR #21 baseline | gen51 |
|:--|--:|--:|
| Combined conservative F1 | 0.709 | 0.802 |
| Combined recall | 0.738 | 0.917 |
| Combined precision | 0.681 | 0.713 |
| Combined FPR | 0.29 | 0.31 |
| SMS-route F1 | 0.709 | 0.787 |
| SMS-route recall | 0.735 | 0.926 |
| SMS-route FPR | 0.264 | 0.333 |
| Injection-route F1 | 0.706 | 0.875 |
| Injection-route FPR | 0.46 | 0.15 |
| Per-language F1, en | 0.697 | 0.737 |
| Per-language F1, hi | 0.718 | 0.762 |
| Per-language F1, hinglish | 0.722 | 0.905 |

The pre-registered ship rule required F1 no more than 2 percentage points below baseline and FPR no more than 2 points above; gen51 passed at FPR +2.0 points. False alarms were high for both systems on hard benign look-alikes. About 12 of gen51's 31 false positives contain placeholder `.example` links; the rest are genuine benign notices, especially safety advisories mentioning scam tactics [S8].

**Data and splits.** SMS sources are UCI SMS Spam and Mendeley SMS Phishing, and the URL source is PhiUSIIL; their stated licences are CC BY 4.0. Flow records come from NSL-KDD, described as UNB research use. Indian seed datasets are credited to karanverma19 (Apache-2.0) and bolewara (CC BY 4.0); the categorised Indian-context evaluation uses project-generated synthetic messages [S6]. The model weights and datasets are separately acquired. Source terms should be checked before redistribution.

Training used 4,127 SMS, 40,000 URL, 113,273 flow, 256 categorised Indian and 136 seed rows; development used 607 SMS, 4,000 URL, 12,700 flow and 64 Indian rows [S2]. SMS splits group normalised text, URLs are split by domain, KDDTrain+ records supply train/dev, and the visible Indian set is split within each category. The separate flow evaluation uses KDDTest+; the separate Indian evaluation uses a second synthetic generator run [S4]. Indian development data was used for tuning.

## How we tested

| Dataset and source | Licence as recorded in [DATA.md](https://github.com/rabesss/arm-bharat-ai-soc/blob/main/candidates/BEST/DATA.md) | Split and n |
|:--|:--|:--|
| [UCI SMS Spam](https://archive.ics.uci.edu/dataset/228/sms+spam+collection) and [Mendeley SMS Phishing](https://data.mendeley.com/datasets/f45bkkt8pr) | CC BY 4.0 each | Combined SMS: train 4,127; dev 607; evaluation 1,162. Split by normalized text; per-source counts are not reported. |
| [PhiUSIIL URLs](https://archive.ics.uci.edu/dataset/967) | CC BY 4.0 | Train 40,000; dev 4,000; evaluation 7,997. Split by domain; evaluation sample is capped and approximately balanced. |
| [NSL-KDD](https://www.unb.ca/cic/datasets/nsl.html) | UNB research use; not redistributed | KDDTrain+ train 113,273 and dev 12,700; KDDTest+ evaluation 22,544 feature records. |
| [karanverma19 Indian seed](https://huggingface.co/datasets/karanverma19/Indian_Multilingual_Scam_Message_Dataset) and [bolewara Hinglish seed](https://huggingface.co/datasets/bolewara/hinglish-scam-text-dataset) | Apache-2.0 and CC BY 4.0, respectively | 136 combined seed rows in training; per-source counts are not reported. |
| Project-generated Indian-context messages | Original project work | Visible messages split within each category: train 256, dev 64; separate generator run for evaluation 320. |

Candidate selection repeatedly used feedback from the same hidden evaluation sets; they are not pristine holdouts. India v2 was adaptive validation; the separately sealed holdout was scored once after freeze. The separate LOCO stress test is described below. The recorded work did not test a real phone, live traffic, or messages collected from Prahari users in a field trial. The SMS, Indic and injection paths no longer output `uncertain`, because the conservative metric counts abstention as an error. The owner-approved flow-text demo retains `uncertain` for a benign cue next to an attack signal and for a lone rejected connection.

**Category holdout.** Leaving each of 32 visible categories out of text-model training yielded pooled binary F1 1.0 on project-generated synthetic categories; fixed rules active; uncertain mapped to benign; not a category average or real-world estimate [S4]. The script prints a misleading macro label.

\newpage

## Explanation, safety and user experience

Prahari separates a detector's verdict from the explanation so that users can inspect the evidence alongside the language model's advice. For a message, the mechanism layer can identify a request for a secret or a fee, a threat, or a benign transaction notice. The UI presents the verdict, score, evidence, Llama explanation, fixed actions and timing. For suspicious communications, the advice directs the user to avoid acting on the message and to use a trusted channel [S2].

The prompt identifies incoming content as data rather than instructions, neutralises live URLs, and requests a verdict-first explanation grounded in selected evidence. Injection patterns are recognised; refusal retries and a heuristic contradiction filter address some failure modes. These are practical guards, not a proof that untrusted content cannot influence generation or that advice is correct. The model can still make a wrong assertion or give unsafe advice [S2].

A blind manual audit of 20 sealed-holdout explanations found 5 correct, 8 weak and 7 wrong. Four made false claims about the input and 16 gave generic or misdirected advice. Common failures included flagging safety advisories that mention scam tactics, boilerplate advice especially in Hindi and Hinglish, and treating placeholder `.example` links as evidence [S8]. Earlier automated checks were narrow heuristics, not a factuality or safety rate. Understanding by non-experts has not been independently measured.

### Offline use

Inference runs locally; inputs reach the local app over loopback. Downloading the model requires network access, and the app itself does not block outbound traffic. The controller evaluation used an import-time guard that blocks non-loopback connections; offline claims cover only what was tested. An independently verified egress restriction remains needed for the demo. Inspect the installed Android APK permissions before making claims about it [S2, S7].

\newpage

## Limitations and Phase 2

Prahari is a triage prototype. It misses some attacks and raises false alarms; on the sealed holdout both systems raised many false alarms, including on safety advisories [S8]. An unfamiliar scam can bypass the rules, the legacy NSL-KDD distribution differs from modern traffic, and a benign verdict cannot prove safety. The flow model has no live packet-to-feature pipeline, and generated explanations need stronger validation. The cloud VM does not establish phone performance, physical edge deployment or organizer acceptance [S2, S4].

Phase 2 will turn the prototype into a more representative edge system:

1. Complete the Android app, run it offline on a real Arm phone, and record device identity, permissions, latency, throughput and peak memory.
2. Implement permission-aware live capture and a documented feature pipeline, then measure detection and false alarms on representative traffic.
3. Expand Indic-language coverage with consented, licensed data and independent evaluation, including difficult benign notices and new scam families.
4. Improve and test grounding, injection resistance, unsafe advice and comprehension with non-expert users; keep uncertainty and human verification visible.

These are planned activities rather than completed validation [S7].

## Sources

[S1] [Official Bharat AI-SoC Challenge page](https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html), PS3; repository snapshot `docs/challenge-brief.md`.

[S2] `candidates/BEST/REPORT.md`, `DATA.md`, `app/server.py`, `triage/{detect,cli,llm}.py`; repository baseline `2fdc142`, 17 November 2026.

[S3] `research/evals/20261111-075405-best-confirm/{details.json,run.log}`; stamp `20261111-075405`. Hardware and model context: `candidates/BEST/REPORT.md`.

[S4] `research/LOG.md` and `research/REPORT.md`, 10–11 November 2026; `research/stress/loco.py` and `eval/prep_data.py`, baseline `2fdc142`.

[S5] Controller-provided symbol inspection, oracle-a1 project venv, 17 November 2026; command and library counts in `docs/phase1/EVIDENCE.md`.

[S6] `candidates/BEST/DATA.md`, baseline `2fdc142`; original source and licence links are listed there.

[S8] Controller-provided round-3 aggregate results, confirmation, sealed-holdout run and blind explanation audit; provenance and holdout hash in `docs/phase1/EVIDENCE.md`. Item texts are withheld until after submission.

[S7] `docs/BRAINSTORM.md` and `candidates/BEST/REPORT.md`, baseline `2fdc142`; Android build status supplied by the controller, 17 November 2026.

The [evidence ledger](https://github.com/rabesss/arm-bharat-ai-soc/blob/main/docs/phase1/EVIDENCE.md) records commands, measurements and their limits. The rendered PDF is built locally from this source and attached at submission.
