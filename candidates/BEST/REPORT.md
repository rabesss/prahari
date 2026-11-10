# Kavach Lite — on-device scam triage for Indian users

## Problem

Indian phone users receive SMS, WhatsApp-style messages, links and calls crafted to steal OTPs, UPI
credentials and money. Genuine bank, delivery and utility alerts look similar, so a useful assistant
must separate scams from hard negatives without sending private content to a cloud. The Bharat
AI-SoC PS3 brief asks for an on-device cybersecurity assistant that runs on Arm hardware, explains
its decision, and stays useful offline. Kavach Lite answers that: local detectors plus a small
Llama explanation model, no network at inference time.

## Architecture

Two stages run entirely on the device. Stage one combines transparent Indian-context rules with
small scikit-learn models: TF-IDF plus logistic regression for SMS, character n-grams for URLs, and
feature-engineered trees for NSL-KDD flows. Rules look for request mechanics (OTP/PIN demand, UPI
collect pressure, KYC or authority threats, prize and job bait) and protective mechanics genuine
alerts use ("never ask for OTP", "no fee is needed", official app pointers). Stage two feeds the
verdict, a short scam type and compressed evidence to Llama 3.2 1B running through ExecuTorch.
The CLI writes JSONL, and a small local web UI exposes the same pipeline for a live demo.

## Models

The detectors are local joblib artifacts: SMS TF-IDF + logistic regression, URL character n-gram
logistic regression, and a flow classifier over NSL-KDD's 41 features. The explanation model is the
`llama32-1b-qlora` entry in `models/registry.json`, executed by ExecuTorch's `TextLLMRunner` with
its matching tokenizer. Generation is greedy, capped at 40 new tokens, and the prompt is compact to
fit two Arm vCPUs. A rule layer handles prompt-injection inputs for the explain task. No new model
was trained for this round; the contribution is the rules, the decision policy, and the prompt and
evidence design.

## Datasets

Development used only `data/train` and `data/dev`: 4,127 SMS rows, 40,000 URL rows, 113,273 NSL-KDD
flow rows, 136 Indian-context seed messages, 607 dev SMS, 4,000 dev URLs, 12,700 dev flow rows and
40 dev indic rows. Hidden test data and private evaluation files were never read. `DATA.md` records
provenance and licences, including NSL-KDD, the public SMS/URL corpora, and the Llama 3.2 licence
and tokenizer. Evaluation used the controller's `bin/eval` proxy only.

## Results

The authoritative two-repeat proxy run scored **85.84** (D 0.9144, E 0.8129, P 0.6541, C 1.0);
the same tree scored 86.23 in a single-repeat run, the difference being the slower of the two
latency repeats (5.06 s vs 4.75 s). Detection: SMS F1 0.9613 (FPR 0.0057), URL F1 0.9949 (FPR 0),
indic F1 0.967 (FPR 0.0071, no penalty), flow F1 0.8265 (FPR 0.0299, penalised score 0.7444).
Explanation checks on 28 items: 28 valid, verdict 0.829, mention 0.357, forbidden 1.0, fabrication
1.0, actions 0.929, length 1.0. The starting baseline scored 69.33. The Indian-context rule layer lifted indic F1 from 0.7406 to 0.967 without
regressing English SMS. Two decision-policy changes mattered: a routine utility-bill gate that
treats plain-host reminders with no threat or secret request as genuine (cutting indic FPR from
3.57% to 0.71%), and a flow threshold of 0.10 that catches more KDDTest+ attacks while keeping FPR
near 3%.

## Performance on Arm

Measured by `bin/eval --repeats 2` on the Oracle A1 host (2× Neoverse-N1, about 11 GB RAM):
explanation latency 5.06 s per item over two repeats (4.75 s in the single-repeat run), peak RSS
2.210 GB, decode 20.2 tokens/s, prefill about 84.9 tokens/s, median prompt 177 tokens and 39
generated tokens. Detector latency is 0.376 ms per item, and the candidate bundle (code plus model
artifacts) is 1.184 GB including the shared 1.1 GB Llama PTE. The UI and CLI run offline; no
network calls are made after import.

## Limitations

The 1B model sometimes paraphrases instead of naming a required concept, so mention coverage is
35.7%; a larger model or a grounded template would help. Indic FPR is now 0.71%, but Hindi recall
remains weak (0.679 accuracy on the 28 Hindi rows) and bank-security, KYC and refund scams still
miss about two rows each. The utility gate deliberately treats a plain-host reminder with no threat
or secret request as routine; a scam that avoids threat words and uses a plain domain can still
pass. Flow detection uses KDDTrain+ only, so the KDDTest+ shift leaves F1 at 0.8265. Rules cover
English, Hindi and Hinglish patterns, not every Indic script. The explanation model can still
produce a wrong detail; deterministic guards catch fabricated domains and long numbers.

## Responsible AI, privacy and safety

All processing is local: no message, URL or flow leaves the device, and the import-time guard blocks
network access. Outputs are advisory, evidence is shown instead of hidden scores, and the UI tells
users to verify with the official app. Advice avoids requesting secrets or clicking message links,
and scam advice points to cybercrime.gov.in and helpline 1930. The system has no access to OTPs,
credentials or payment APIs. Known failure modes are documented here and in `LIMITATIONS` notes;
a human can always ignore the verdict, and the tool does not block communication by itself.
