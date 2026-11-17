---
title: "Prahari: offline threat triage on Arm"
subtitle: "Bharat AI-SoC Challenge 2026–27, PS3 | Phase 1 technical report"
date: "17 November 2026"
geometry: margin=0.75in
fontsize: 10pt
---

## Problem and Indian context

Prahari helps a person assess a pasted message or URL and gives plain-language advice without requiring a cloud inference service. Indian scam patterns include OTP and UPI credential requests, payment pressure and false authority claims; genuine bank, delivery and utility notices can look similar. The aim is triage, not proof that an item is safe. PS3 requires Llama-family advisory reasoning deployed on-device with ExecuTorch and calls for source, application, demonstration video and technical report [S1]. The current prototype does not yet demonstrate live network monitoring or an Android phone.

## Architecture

```text
Pasted SMS / URL ---> rules + trained text/URL detector ---> fusion/verdict
                                                               |
Network description ---> text rules --------------------------+--> Llama 3.2 1B
                                                               |    via ExecuTorch
                                                               +--> explanation + fixed actions
NSL-KDD feature record ---> trained flow model + signatures ---> separate verdict + evidence
                            (dataset replay only)
```

The SMS detector combines TF-IDF and a logistic classifier with Indian-context mechanism rules; URL detection combines character n-grams and indicators. The trained flow model uses NSL-KDD features and signatures. In the UI and `--demo`, the network input is a text description scored by `predict_flow_text`, not the trained flow model. `bin/explain` independently calls `classify_any("flow", text)` and explains the text-rule result; it does not receive the feature-model result. Their verdicts may disagree. Live capture is **not implemented**. See code and design record [S2].

## Arm deployment and performance

The measured target was an aarch64 Oracle A1 cloud VM with two Neoverse-N1 vCPUs, approximately 11 GB RAM, Ubuntu 24.04 and no GPU. The Llama 3.2 1B Instruct QLoRA export uses INT4 group-32 weights, dynamic 8-bit activations, ExecuTorch 1.6 and XNNPACK. Greedy generation was limited to 40 new tokens. The controller ran `bin/eval candidates/BEST --repeats 2`; 28 explanation items took 99.797 and 102.636 seconds across the two runs. Reported aggregate latency was 3.67 s/item, peak RSS 2.256 GB, median prefill 82.5 tokens/s and decode 20.8 tokens/s, with 130 prompt and 28 generated tokens at the median. Detector processing was 0.407 ms/item. This is a shared host; load affects timings. These are VM measurements, not phone measurements or an edge-device eligibility determination [S3].

KleidiAI kernels are linked into the installed ExecuTorch XNNPACK backend (`kai_` symbols present); dispatch on this CPU not verified. The symbol inspection record and command are **TODO** for the owner [S4]. No speedup is claimed. Android device, OS, latency, prefill/decode throughput and peak RSS: **TODO**, pending measurement on a real phone [S4].

## Evaluation

Data provenance and stated licences: UCI SMS Spam and Mendeley SMS Phishing (CC BY 4.0), PhiUSIIL URL (CC BY 4.0), NSL-KDD (UNB research use), Indian seed datasets from karanverma19 (Apache-2.0) and bolewara (CC BY 4.0), and project-generated Indian synthetic messages [S5]. Review source terms before redistribution. Training uses 4,127 SMS, 40,000 URL, 113,273 flow, 256 categorised Indian rows and 136 seed rows; development has 607 SMS, 4,000 URL, 12,700 flow and 64 Indian rows [S2]. Flow development is drawn from KDDTrain+, while the separate evaluation uses KDDTest+; the distributions differ [S6]. Indian dev was used for tuning and is optimistic. Datasets and Llama weights are not committed [S5].

The following are aggregate controller results from the separate evaluation, not a judging score. FPR is false positives divided by actual negatives; sample counts include both classes. The internal proxy score is an engineering measure, not the challenge's judging score. [S3]

| Task | n | F1 | Precision | Recall | FPR |
|:--|--:|--:|--:|--:|--:|
| SMS | 1,162 | 0.9015 | 0.9570 | 0.8520 | 0.0078 |
| URL | 7,997 | 0.9948 | 1.0000 | 0.9896 | 0.0000 |
| Indic synthetic | 320 | 0.9665 | 0.9870 | 0.9469 | 0.0125 |
| NSL-KDD flow replay | 22,544 | 0.8505 | 0.9706 | 0.7568 | 0.0303 |

Indic accuracy: English 0.977 (n=192), Hinglish 0.975 (n=80), mixed 1.000 (n=16), Hindi 0.875 (n=32) [S3]. Small groups and synthetic data limit inference about real users and languages. Other Indic scripts are not established as supported.

The LOCO record reports F1 1.0 over 32 held-out categories of the visible synthetic Indian set [S6]. However, `research/stress/loco.py` pools predictions and calls scikit-learn's default binary `f1_score`, despite printing “macro F1”; the result is **pooled binary F1**, not a verified mean of category F1s. The script trains on other categories and seed/SMS data, while mechanism rules remain in use. This is a narrow synthetic check and does not prove real-world generalisation. The historical 16-category note is superseded by the expanded 32-category run [S6].

## Explanation safety

The detector supplies the verdict and evidence; the prompt identifies user content as data, neutralises URLs, requests a verdict-first answer, and retries refusals with an evidence-only prompt. A heuristic removes some contradictory sentences; fixed actions accompany the explanation. Pattern matching detects some injection attempts, but these measures do not guarantee resistance or accurate advice [S2].

The 28-item checks reported 28 valid outputs, verdict 0.975, consistency 1.0, evidence mention 0.714, forbidden-content 1.0, fabrication 1.0, actions 0.964 and length 1.0. The BEST report records one wrong verdict and one unsafe action under the scorer's rules. These are limited automated checks, not proof of safety or comprehension [S2, S3]. A failed or misleading explanation should not be treated as authority; verify through a known official channel.

## User experience and offline operation

The loopback web interface accepts pasted text, shows a verdict, score, evidence, explanation, actions and Llama timing. `--demo` exercises preset inputs. It does not automatically block traffic or take action on behalf of the user [S2]. The evaluation ran with a guard that blocks non-loopback networking; normal app startup does not itself install that guard. A recording must demonstrate an independently enforced egress block, with local access retained, before claiming an offline proof. A remote phone variant requires a working APK and an inspection of its permissions; neither is established here [S7].

## Limitations and Phase 2

False alarms and misses occur, including SMS recall 0.852 and flow replay recall 0.7568 in the separate evaluation [S3]. Unseen scams, short messages and new attack families can evade detection. A safe verdict is not a guarantee; generated advice can be wrong. The synthetic and legacy network datasets do not establish real-world performance, and the prototype has no live packet capture, malware execution analysis, power measurement or validated physical-phone benchmark. The cloud VM is not evidence of phone latency, local physical edge operation, or organizer acceptance [S2, S3, S7].

Phase 2 is planned: build an Android app and test on a real phone offline; implement permission-aware live flow capture with a documented feature pipeline; collect consented, licensed and representative data; broaden Indic-language coverage and independently test false alarms, calibration, advice and usability. None is claimed complete [S7].

## Sources

[S1] `docs/challenge-brief.md`, PS3 snapshot; official page reviewed 2026-11-11 in `/var/tmp/adl-review/REPORT.md` and [challenge page](https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html).

[S2] `candidates/BEST/REPORT.md`, `DATA.md`, `app/server.py`, `triage/detect.py`, `triage/cli.py`, `triage/llm.py`, repository baseline `2fdc142` (2026-11-17).

[S3] `research/evals/20261111-075405-best-confirm/{details.json,summary.json,run.log}`, stamp `20261111-075405`; environment and measurement method in `candidates/BEST/REPORT.md`, baseline `2fdc142`.

[S4] KleidiAI linkage supplied for this report; reproducible symbol record **TODO**. Android measurements **TODO**.

[S5] `candidates/BEST/DATA.md`, baseline `2fdc142`; source links and licence statements there.

[S6] `research/REPORT.md` Generalisation, `research/LOG.md` 2026-11-11 gen7 verification, and `research/stress/loco.py` and `eval/prep_data.py`, baseline `2fdc142`.

[S7] `docs/BRAINSTORM.md` 2026-10-23 and `candidates/BEST/REPORT.md` Demo plan, baseline `2fdc142`; Phase 2 is planned, offline proof pending.

The claim-by-claim commands and evidence are in [EVIDENCE.md](EVIDENCE.md).
