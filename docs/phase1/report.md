---
title: "Prahari: offline threat triage on Arm"
subtitle: "Bharat AI-SoC Challenge 2026–27, PS3 | Phase 1 technical report"
date: "17 November 2026"
geometry: margin=0.85in
fontsize: 11pt
---

## Summary

Prahari is an Arm CPU prototype that helps people assess suspicious messages, links and described network events without a cloud inference service. Small trained detectors and transparent rules produce a verdict and evidence; a Llama 3.2 1B model running through ExecuTorch turns that evidence into plain-language guidance. Its Indian-context mechanism layer looks for actions such as sharing an OTP, paying an unverified recipient or responding to a service-disconnection threat, while recognising cues in ordinary notices. A separate trained network model scores NSL-KDD feature records as dataset replay. The system is designed to help a person decide what to check next, not to act automatically or certify safety [S1, S2].

## Highlights

The following results are from the **11 November 2026** controller run on the specified Arm cloud VM and its separate evaluation, not a challenge judging score [S3]:

- **0.407 ms/record** URL detector batch wall time (7,997 records in one batch); **3.67 s/item** explanation time over two runs of 28 items.
- **2.256 GB** peak RSS during explanation; median prefill **82.5 tokens/s** and decode **20.8 tokens/s**.
- The detection figures below are **half-credit proxy metrics** (see Evaluation and data).
- URL false-positive rate **0.0000**, F1 **0.9948** on **7,997** records.
- SMS false-positive rate **0.78%**, F1 **0.9015** on **1,162** records.
- Hinglish half-credit accuracy **0.975** on **80** synthetic Indian-context items.
- A limited automated heuristic flagged none of **28** outputs for the specific fabrication patterns it checks; this is not a factuality or safety rate. Evidence mention was **0.714**; 27 of 28 verdicts were correct, one was `uncertain`, and one action list failed the action check [S2, S3].

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

**Target and method.** The recorded deployment is an aarch64 Oracle A1 VM: two Neoverse-N1 vCPUs, approximately 11 GB RAM, Ubuntu 24.04 and no GPU [S2]. The controller ran `bin/eval candidates/BEST --repeats 2`; the 28 explanation items took 99.797 and 102.636 seconds in the two runs. The aggregate result was 3.67 s/item and 2.256 GB peak RSS. The URL detector processed its 7,997-record batch at 0.407 ms per record (process wall time divided by records; not an interactive per-request latency). Median prompt and output lengths were 130 and 28 tokens respectively, with 82.5 prefill and 20.8 decode tokens/s [S3]. These are shared-host measurements; co-tenant load affects timing. Thread settings were not recorded in the cited results.

**Model and backend.** Prahari uses the ExecuTorch 1.6.0 XNNPACK CPU backend with Llama 3.2 1B Instruct QLoRA: INT4 group-32 weights and 8-bit dynamic activations. This export was retained after a SpinQuant export measured about 58–63 prefill and 12–13.5 decode tokens/s on the same box under mixed co-tenant load; the QLoRA confirmation measured 82.5 and 20.8 tokens/s. The workloads and host load were not a controlled comparison, so the observations support the selection on this host, not a general speedup claim [S2, S3].

**Keep detection fast.** Llama is invoked for explanation, not classification. The small detector produces a verdict and selected evidence first; the advisory model receives a compact prompt and generates at most 40 new tokens with greedy decoding in the Linux reference runner; the draft Android port uses callback-count stopping, not a guaranteed token cap. This makes the cost of the language model visible and keeps it out of the detector path [S2].

**Compact the prompt.** The team moved to an evidence-first prompt and then shortened it further. The recorded median fell from 199 prompt and 34 generated tokens to 137 and 29 in the earlier comparison; its reported times were 4.72 and 4.42 s/item. The final confirmation used 130 and 28 tokens at the median and reported 3.67 s/item. Runs were affected by changing shared-host load, so these timings do not isolate the causal gain from compaction. The token reduction is directly recorded; a controlled latency comparison remains future work [S3, S4].

**KleidiAI.** KleidiAI micro-kernels are linked into the installed ExecuTorch 1.6.0 XNNPACK backend; dispatch on Neoverse-N1 was not profiled; no speedup claimed. The 17 November symbol inspection found 517 `kai_` symbols in the XNNPACK backend library; its command, additional library counts and limitations are recorded in the evidence ledger [S5]. Symbol presence alone does not establish that a particular inference used those kernels.

## Android deployment (in progress)

A draft Android APK reportedly builds in CI at PR #18 head `e74c950`; [CI build and limited parity](https://github.com/rabesss/arm-bharat-ai-soc/actions/runs/44122552734) do not establish on-device model generation. Real-phone execution, exact runtime/model compatibility and measurements remain unverified. Device identity, permissions, latency, throughput and peak memory will be recorded after a real-phone run [S7].

\newpage

## Evaluation and data

Prahari evaluates detection independently from generated explanations. Historical detection F1, precision, recall, FPR and language accuracy from `eval/run_eval.py` are half-credit proxy metrics: an uncertain verdict contributes ½ to each side of the confusion counts, or ½ credit to language accuracy ([lines 143–163](https://github.com/rabesss/arm-bharat-ai-soc/blob/main/eval/run_eval.py#L143-L163), [419–426](https://github.com/rabesss/arm-bharat-ai-soc/blob/main/eval/run_eval.py#L419-L426)). Published aggregates do not include abstention counts. Conventional metrics with abstention counts: pending (see [EVIDENCE.md](https://github.com/rabesss/arm-bharat-ai-soc/blob/main/docs/phase1/EVIDENCE.md)). Each `n` includes both classes. A zero observed FPR describes this sample; it is not a guarantee. The proxy is an internal engineering measure rather than an official judging score [S3].

| Task | n | F1 | Precision | Recall | FPR |
|:--|--:|--:|--:|--:|--:|
| SMS | 1,162 | 0.9015 | 0.9570 | 0.8520 | 0.0078 |
| URL | 7,997 | 0.9948 | 1.0000 | 0.9896 | 0.0000 |
| Indic synthetic | 320 | 0.9665 | 0.9870 | 0.9469 | 0.0125 |
| NSL-KDD flow replay | 22,544 | 0.8505 | 0.9706 | 0.7568 | 0.0303 |

**Indic breakdown.** On the synthetic set, half-credit accuracy was 0.977 for English (n=192), 0.975 for Hinglish (n=80), 1.000 for mixed language (n=16), and 0.875 for Hindi (n=32) [S3]. These small language groups help identify a weakness in Hindi, but cannot establish performance across India's languages or real-world message distributions.

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

Candidate selection repeatedly used feedback from the same private evaluation set, so it is not a pristine untouched holdout. The detection and language results use the half-credit rule above. The separate LOCO stress test is described below. Explanation checks used 28 items and heuristic checks for validity, verdict, consistency, evidence mention, forbidden content, fabrication patterns, action and length; they are not a factuality or safety audit. The recorded work did not test a real phone, live traffic, or messages collected from Prahari users in a field trial.

**Category holdout.** Leaving each of 32 visible categories out of text-model training yielded pooled binary F1 1.0 on project-generated synthetic categories; fixed rules active; uncertain mapped to benign; not a category average or real-world estimate [S4]. The script prints a misleading macro label.

\newpage

## Explanation, safety and user experience

Prahari separates a detector's verdict from the explanation so that users can inspect the evidence alongside the language model's advice. For a message, the mechanism layer can identify a request for a secret or a fee, a threat, or a benign transaction notice. The UI presents the verdict, score, evidence, Llama explanation, fixed actions and timing. For suspicious communications, the advice directs the user to avoid acting on the message and to use a trusted channel [S2].

The prompt identifies incoming content as data rather than instructions, neutralises live URLs, and requests a verdict-first explanation grounded in selected evidence. Injection patterns are recognised; refusal retries and a heuristic contradiction filter address some failure modes. These are practical guards, not a proof that untrusted content cannot influence generation or that advice is correct. The model can still make a wrong assertion or give unsafe advice [S2].

The 28-item automated explanation evaluation reported 28 valid outputs; verdict 0.975, consistency 1.0, evidence mention 0.714, forbidden-content check 1.0, fabrication check 1.0, action check 0.964 and length check 1.0. Under the scorer's rules this means 27 correct verdicts and one `uncertain` verdict (scored 0.3, none wrong), and one action list that failed the action check, which fails when an action is unsafe or when a malicious item lacks a protective action [S2, S3]. The fabrication and forbidden-content checks are limited checks, not a guarantee of truth or safety. Understanding by non-experts has not yet been independently measured.

### Worked example for the recorded demo

Recorded on 17 November 2026 with `bin/app --demo` on the Oracle A1 Neoverse-N1 VM (visible preset input; full output in the demo recording). Input (SMS): *"Dear customer, your electricity connection will be disconnected tonight. Pay Rs 499 now at http://bses-bill-update.top or the meter will be cut."*

| Field | Output |
|:--|:--|
| Detector verdict | malicious, score 1.0, category "a payment fraud" |
| Evidence | asks for a payment to a personal number, account or unverified link; threatens to block, cut or freeze an account, SIM or connection; the domain bses-bill-update.top uses .top, common for throwaway scam sites |
| Llama 3.2 1B explanation (ExecuTorch, on the Oracle Arm cloud VM) | "This message is DANGEROUS: asks for a payment to an unverified account or link. Do not click on any suspicious links or send money." |
| Actions | Do not click the link or reply to the message. Never share OTP, UPI PIN, CVV or passwords with anyone. Report it at cybercrime.gov.in or call the national helpline 1930, and use Sanchar Saathi Chakshu to report the sender. |
| Llama run | 133 prompt tokens, 31 generated; prefill 75.0 tok/s, decode 21.5 tok/s; 5.6 s generation |

This first item of the run includes the one-time model load (13.2 s end to end); the remaining five demo items took 2.9–6.9 s each, at 2.30 GB RSS. A Hinglish example will be added once recorded.

### Offline use

Inference runs locally; inputs reach the local app over loopback. Downloading the model requires network access, and the app itself does not block outbound traffic. The controller evaluation used an import-time guard that blocks non-loopback connections; offline claims cover only what was tested. An independently verified egress restriction remains needed for the demo. Inspect the installed Android APK permissions before making claims about it [S2, S7].

\newpage

## Limitations and Phase 2

Prahari is a triage prototype. It misses some attacks and raises false alarms; in the recorded evaluation half-credit proxy SMS recall was 0.852 and flow replay recall was 0.7568 [S3]. An unfamiliar scam can bypass the rules, the legacy NSL-KDD distribution differs from modern traffic, and a benign verdict cannot prove safety. The flow model has no live packet-to-feature pipeline, and generated explanations need stronger validation. The cloud VM does not establish phone performance, physical edge deployment or organizer acceptance [S2, S4].

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

[S7] `docs/BRAINSTORM.md` and `candidates/BEST/REPORT.md`, baseline `2fdc142`; Android build status supplied by the controller, 17 November 2026.

The [evidence ledger](https://github.com/rabesss/arm-bharat-ai-soc/blob/main/docs/phase1/EVIDENCE.md) records commands, measurements and their limits. The rendered PDF is built locally from this source and attached at submission.
