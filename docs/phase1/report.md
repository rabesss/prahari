---
title: "Prahari: Offline On-Device Threat, Phishing and Scam Triage on Arm"
subtitle: "Phase 1 Technical Report · Arm Bharat AI-SoC Student Challenge 2026–27"
author: "Team Prahari · Problem Statement 3"
date: "25 November 2026"
---

\AbstractHeading{Abstract}

Prahari is an offline cybersecurity triage assistant for Indian smartphone and Arm Linux users. Compact classical models and transparent Indian-context mechanism rules classify suspicious SMS and WhatsApp-style messages, phishing URLs and prompt-injection attempts on the device, and network events on Arm Linux. Meta's INT4 QLoRA release of Llama 3.2 1B Instruct (described by Meta as quantisation-aware training with LoRA adaptors), run through ExecuTorch XNNPACK on the Arm CPU, then explains that evidence in plain language beside vetted safety steps. The app labels which of three outcomes the user sees: checked AI text, the detector's fixed text when no reply passes deterministic checks, or "explanation unavailable" when the model is missing or raises an error. On a Samsung Galaxy S23 phone, whose app declares no network permission, a warm KYC check in the all-items pass takes a median 1.857\ s at 32.5\ tok/s decode (2.611\ s in the later, hotter gated pass). On Arm Neoverse-V2, a whole-process profile places 54.17% of sampled CPU time inside Arm KleidiAI kernels. We report every holdout, including an independently authored but repeatedly scored sealed set (n\ =\ 184), where the false-positive rate (FPR) is still 0.300 (30 of 100 benign items: 87 genuine SMS-route and 13 benign prompt-injection-route items) and 0.322 (28 of 87) on genuine SMS alone. Prahari is strictly advisory: inference and storage stay on the device, and content leaves the app only when the user chooses to share a warning or copy a report. Built with Llama.[^llama]

[^llama]: Llama 3.2 is licensed under the Llama 3.2 Community License [1].

\begingroup\raggedright

**Keywords:** on-device AI, scam detection, phishing, Arm, KleidiAI, ExecuTorch, Llama 3.2, India, privacy

\endgroup

## Introduction

Indian smartphone users routinely receive fraudulent messages built around familiar domestic rails: UPI collect requests disguised as refunds, fake KYC or PAN/Aadhaar suspension warnings, electricity-disconnection threats, courier and customs fees, task-recharge scams, and "digital arrest" impersonation of police or regulators. The Ministry of Home Affairs has publicly warned about fake digital arrests and courier impersonation [2]. The National Crime Records Bureau (NCRB) recorded 101,928 registered cybercrime cases in 2024, and the Indian Cyber Crime Coordination Centre (I4C) separately reported more than 6,589,201 financial-fraud complaints totalling over Rs\ 55,050 crore on the national portal across 2021–2025 [3]. Registered cases and portal complaints are distinct measures and do not quantify Prahari's target user base.

The detection problem is hard because genuine bank debit alerts, OTP notifications, bill reminders and telecom advisories share the same vocabulary ("OTP", "Rs", "UPI", "account", "KYC", "blocked") across English, Devanagari Hindi and Romanised Hinglish. A keyword filter would flag legitimate alerts, and a cloud-LLM wrapper would send private banking texts off the device. Following the PS3 brief and mentor guidance [A1], Prahari keeps all inference local on Arm hardware and asks *what the sender wants the recipient to do*, which separates scams from benign informational notices.

\needspace{5\baselineskip}
This report makes four contributions:

1. **A hybrid detect-then-explain pipeline.** Deterministic classifiers and Indian-context mechanism rules decide the verdict; Llama 3.2 1B only explains the structured evidence.
2. **An on-device Arm deployment.** The message and link detect-and-explain pipeline runs on a Samsung Galaxy S23 phone and on Arm Linux through ExecuTorch XNNPACK, with profiled execution inside Arm KleidiAI `kai_*` kernels. Call Guard (voice notes) is a Linux preview not yet in the Android app; the live network monitor is Linux-only.
3. **Verified offline operation.** The Android app declares no `INTERNET` permission and was tested in Airplane Mode; on Linux, inference passes with the network namespace cut [A9,\ A10].
4. **An honest evaluation.** We report the development sets and every holdout, with false alarms as counts and 95% Wilson intervals, including an independently authored sealed set that was scored repeatedly during development.

Table 1 and Figure 1 summarise the headline results; Sections 5 and 6 give the measurements and caveats. Recall is the share of scams given a `scam` verdict (an `uncertain` verdict counts as a miss), the false-positive rate (FPR) the share of genuine (benign) items flagged, including `uncertain` verdicts, and F1 the harmonic mean of precision and recall. The phone and detection rows come from different builds (Appendix B), and the sealed holdout, though independently authored, was scored repeatedly (Section 6.1).


| **Metric** | **Result** | **Setting** |
|:-----------------------------------|:-----------------------------------|:------------------------------|
| Warm KYC check, all-items pass | 1.857\ s median, 32.5\ tok/s | Galaxy S23, n\ =\ 2 |
| Warm KYC check, gated pass | 2.611\ s median, 23.9\ tok/s | Galaxy S23, n\ =\ 2, run second |
| Linux throughput | 0.980\ s/item, 104.6\ tok/s | Neoverse-V2, 8 threads |
| KleidiAI share of CPU time | 54.17% | Neoverse-V2, 2 threads, `perf` |
| India v3 held-back split | F1 0.970, FPR 0.000 (0/47) | n\ =\ 81 |
| Sealed holdout | F1 0.812, FPR 0.300 (30/100) | n\ =\ 184, repeatedly scored |

Table: Key Phase 1 results. Phone rows: medians of two warm KYC checks, model preloaded (APK from commit 5b59ee2). Detection rows: detector checkpoint 75993f1, conservative scoring.


![Results at a glance: held-back detection (Table 8), Galaxy S23 warm KYC check time by build (Table 6, Section 5.1) and Neoverse-V2 decode speed (Table 7). Light teal marks the intermediate S23 build; the hatched gated pass ran second and hotter. The S23 bars come from different builds and sessions, not a controlled comparison.](img/fig-overview.pdf){#fig:overview width=100%}

## Related Work

India already has strong anti-scam tools, but none of the products in Table 2 documents, as of 24 November 2026, a mode that explains a suspicious message in plain Hindi or English on a phone with no network. The table compares them on four properties as stated on the cited vendor and government pages on that date, not from hands-on testing.

| **Product** | **Offline** | **India** | **Explains** | **Link/QR** |
|:------------------------------------------------|:--------|:--------|:--------|:--------|
| Google Messages Scam Detection [4–6] | Partial | No | No | Yes |
| Pixel / Samsung call and message guards [5,\ 7,\ 8] | Yes | Partial | No | No |
| Truecaller Fraud Protection [9–11] | Partial | Yes | No | Partial |
| Airtel network spam and link protection [12] | No | Yes | No | Yes |
| Bitdefender Scamio; McAfee; Norton Genie [13–15] | No | No | Partial | Yes |
| Sanchar Saathi Chakshu, 1930, TRAI DLT rules [16,\ 17] | No | Yes | No | No |
| **Prahari (this work)** | **Yes** | **Yes** | **Yes** | **Partial** |

Table: Documented features of related products. Offline: inference without a network. India: Hindi/India support or Indian reporting channels. Explains: plain-language reason. Link/QR: link or QR checking. "Partial", in every column, means the property holds for only some of the listed products, modes or features (for example, Offline: some modes use the cloud; Explains: answers on request in a cloud chat; Link/QR for Prahari: offline rules and QR decoding, no reputation feed). "No": not documented in the cited sources.


The closest products split along the same line. Google Messages runs standard scam detection on-device, but its Enhanced mode sends conversations with unknown senders to cloud Gemini, and Hindi is not among its listed languages. Truecaller filters SMS on-device at scale for India, while its caller ID and spam database are cloud and crowdsourced. In their documented modes, Scamio, McAfee and Norton answer questions about texts, links and QR codes in the cloud and in English; on-device or Hindi support is not established by their pages.

Research points the same way. Saavalainen [18] ran Gemma 3n-E2B-it zero-shot on an Android phone on Finnish SMS: it missed 15 of 41 dangerous messages (63.4% recall) against 2 of 41 for a cloud model (95.1%), and produced more unsupported details. The thesis concludes that small models "appear more suitable as part of a broader detection and explanation pipeline than as standalone phishing detectors". ElZemity et al. [19] distil LLM teachers into Qwen2.5-0.5B and SmolLM2-135M SMS classifiers, reaching 94.31% accuracy and 96.25% recall, but give the user no explanation.

Prahari sits between these lines of work: detectors decide, as in [19], and Llama 3.2 1B only explains, as [18] recommends. Its distinct combination is Indian scam mechanisms in English, Hindi and Hinglish; vetted next steps (Chakshu, 1930, cybercrime.gov.in) for every verdict, plus an on-device explanation that is checked AI text, labelled fixed text or an "explanation unavailable" notice (Section 3.3); and no network at inference. Its gaps are equally clear. Prahari does not sit in the message or call path, has no link-reputation feed (only rules, including a typosquat list of 56 Indian official domains), and its false-alarm rate on hard benign notices is still high (Section 6.1).


## System Design and Methodology

### Architecture

Prahari splits each decision into two stages (Figure 2): in Stage 1, compact detectors and transparent rules decide the verdict and extract typed evidence; in Stage 2, Llama 3.2 1B, run on the device through ExecuTorch, turns that evidence into a short plain-language explanation.

The language model never decides the verdict or chooses critical helpline actions, so a hallucination or a prompt injection hidden in an untrusted message does not change a \vlabel{DANGEROUS} item to \vlabel{NO RISK FOUND}; detector and implementation errors remain possible [A2]. Stage 1 is also fast: 0.42\ ms/item on Neoverse-N1, and 5–17\ ms warm for text checks on the Galaxy S23 phone (183\ ms for a URL); in the intermediate build the warm KYC and bill-reminder checks took 16–80\ ms.

![Prahari architecture. Stage 1 detectors and rules decide the verdict, which the app shows with fixed vetted steps written without the LLM, and extract typed evidence; Stage 2 (Llama 3.2 1B on ExecuTorch) explains that evidence on the device, below the fixed steps. The live socket monitor runs on Linux only.](img/fig-architecture.pdf){#fig:arch width=100%}

### Stage 1 detectors and Indian-context rules

Stage 1 returns one of three detector labels (`scam`, `uncertain`, `benign`), which the app shows as four verdict tiers: \vlabel{DANGEROUS} for a scam, \vlabel{SUSPICIOUS} for uncertain and \vlabel{NO RISK FOUND} (still verify) for benign. A bank debit or OTP alert that is not \vlabel{DANGEROUS} and carries the vetted bank step is shown instead as the amber \vlabel{CHECK THIS ALERT} banner, or as \vlabel{SUSPICIOUS} if it names its own link or number. Each input is routed by kind: `upi://` payloads go to the UPI checker, links to the URL model and lexical rules, network descriptions to the flow rules, and prompt-injection items to the injection rules before the text path. Every text message passes the mechanism rules first: Indian-context messages are decided by the Indian-context model together with those rules, and the rest by the rules first (a decisive harmful mechanic flags, a benign notice with no harmful mechanic clears), otherwise by the English SMS model. An optional sender check can only raise the verdict [A2,\ A16].

Stage 1 combines four small scikit-learn models with a rule layer. The SMS model uses word and character TF-IDF (term frequency–inverse document frequency) features with logistic regression, trained on English SMS corpora. The URL model adds character n-gram TF-IDF to lexical indicators: punycode and homoglyph digit swaps, brand lookalikes on disposable TLDs such as `.top` and `.xyz`, missing HTTPS, IP hosts and excessive subdomains. URLs are never fetched.

The Indian-context model joins character and word n-grams with a 19-dimension mechanism feature vector, so unseen Hindi and Hinglish spellings still activate shared cues. The flow model is a histogram gradient-boosted tree over NSL-KDD's 41 named features, plus three high-precision intrusion signatures (failed-login bursts, malformed fragments, same-source/destination loops) that fire on 0.10% (75/74,112) of normal train and dev records [A4].

The mechanism layer first normalises zero-width characters, full-width Unicode and spaced capitals, then separates harmful mechanics from benign ones. Harmful mechanics include requests for OTP, PIN, CVV or card details; payment to a personal number, UPI ID, "safe" account or lookalike domain; UPI collect requests; installing a screen-sharing or remote-access APK; digital-arrest coercion; upfront job, loan, customs or prize fees; and sending ID papers to a chat or link. Benign mechanics include completed receipts, OTP notifications, routine bills, official app pointers and protective disclaimers.

Precedence is deliberately asymmetric. A decisive harmful mechanic overrides a protective disclaimer, because scammers routinely write *"no OTP needed, pay Rs\ 499 fee"*. In the other direction, a contact counts only when an action names it, toll-free numbers are distinguished from personal mobiles, and advisories without a spoofed contact are cleared.

Genuine-looking bank debit alerts that advise blocking the card in the bank app get a cautious `uncertain` verdict rather than a scam label, shown as \vlabel{CHECK THIS ALERT} with the step *"Didn't make this payment? Call 1930 and block the card or UPI in your bank app"*. Untrusted text is also scanned by a dedicated prompt-injection route and is always framed as quoted data inside the Llama prompt.

### Stage 2 grounded explanation and safety checks

Stage 2 runs Meta's INT4 QLoRA release of Llama 3.2 1B Instruct through ExecuTorch's `TextLLMRunner` on Linux and `LlmModule` on Android [A7]. The prompt supplies the authoritative verdict, a short scam category and a compressed evidence phrase, neutralises live URLs, and asks for a verdict-first sentence followed by one protective step.

Fixed India-specific steps always appear above the AI text. Sanchar Saathi Chakshu is primary for scam messages and links before any loss, 1930 is primary once money has been debited, and cybercrime.gov.in is shown for extortion and sextortion.

The second sentence is grounded. The prompt carries one vetted, advice-led key fact per scam type or benign reading, and Llama writes its own sentence from it instead of filling an empty slot with stock lines [A12]. Deterministic checks then validate the output:

- A generated sentence is dropped if it claims a link, number, device or domain the item lacks, makes an unsupported OTP, payment, app or KYC claim, hedges against a \vlabel{NO RISK FOUND} verdict, or is vague, first-person, overclaiming or mixed-script. The vetted fact replaces it.
- \vlabel{NO RISK FOUND} openings assert only the absence of elements that are actually absent, and never cite an overruled risk signal.
- Repeated sentences are removed, and generated questions (such as *"Can I help you with something else?"*) are stripped or replaced by the scam type's vetted step.

Each item therefore ends in one of three explanation outcomes (Table 3), and the app labels which one the user sees; the verdict and vetted steps are shown in all three.


| **Outcome** | **What the user sees** | **When** |
|:----------------------|:--------------------------------------|:--------------------------------------|
| Accepted AI text | Llama's explanation, marked "AI-written and can be wrong" | A reply passes every check (any dropped sentence replaced by its vetted fact) |
| Fixed detector text | The detector's own text, marked as not written by AI | Every reply fails the checks, Llama runs out of time, or gating skips Llama for a \vlabel{NO RISK FOUND} result |
| No explanation | A notice that no explanation is available | The model is missing, fails to load or raises an error |

Table: The three explanation outcomes. The Linux CLI prints "Explanation unavailable" whenever no reply passes the checks.


Hindi mode shows a fixed-text Hindi summary built from the detector result and labelled as not AI-written. The 1B model cannot write usable Hindi, so the Llama explanation stays in English. Box 1 traces the app's built-in KYC sample through both stages on the phone.

```{=latex}
\begin{prahariExample}{Box 1. Worked example: the built-in KYC sample on the Galaxy S23}
\textbf{Input (SMS sample).} ``Dear customer your SBI KYC is expiring, update at \path{http://sbi-kyc.in-verify.top} or the account will be blocked''

\textbf{Stage 1 verdict.} \vlabel{DANGEROUS}: ``Sends you to a lookalike page and asks you to act there.'' Type: an account-blocking scam. Evidence, three signals: ``Sends you to a lookalike page and asks you to act there''; ``Threatens to block, cut or freeze an account, SIM or connection''; ``The domain sbi-kyc.in-verify.top imitates `sbi' on .top'', quoted defanged as \path{hxxp://sbi-kyc[.]in-verify[.]top}.

\textbf{Vetted steps (above the AI card).} (1) Do not open the link or call the number in it. (2) Check your account in the bank app or call the number on your card. (3) Report the message or call on Sanchar Saathi Chakshu. Buttons: ``Report on Sanchar Saathi Chakshu'' and ``Lost money? Call 1930''.

\textbf{Displayed explanation.} ``This message is DANGEROUS: threatens to block the account or service. Ignore the threat; check your account in the bank app.'' The final build labels the card ``AI sentence replaced by a safety step'' and ``AI-written and can be wrong. Follow the steps above.'' Sentence 1 is the verdict opening the prompt requires Llama to write; sentence 2 is the vetted step the checks put in place of Llama's own text. Warm check: 15\ ms detector, 1.88\ s total (one of two warm checks; median 1.857\ s in Table~6). \textbf{Sources:} verdict, signals and steps from first-build captures; explanation, labels and timing from the final build; the explanation text is the same in both [A9,~A17].
\end{prahariExample}
```

### Applications

The fully offline Android app uses a Kotlin UI, Chaquopy 17.2.0 (Python 3.10, NumPy 1.26.2) and the ExecuTorch Android 1.5.1 AAR. It declares no `INTERNET` permission, checked automatically on every build, and disables backup. Messages arrive through the Android share sheet or text selection; the app offers an EN/Hindi toggle, offline text-to-speech over the vetted verdict and steps, quoted evidence with defanged URLs and masked OTPs, opt-in redacted local history (off by default), and an on-device QR photo decoder that needs no camera or storage permission [A7].

Later additions target Indian payment and device scams. A UPI QR checker parses `upi://` links offline and flags collect requests, payee mismatches and "scan to receive" lures. A typosquat check flags near copies of 56 Indian official domains and direct `.apk` downloads. *Copy report* drafts a masked, defanged Chakshu report and *Send to family* shares a short warning with no message details. An amber banner appears when AnyDesk, TeamViewer, AirDroid or RustDesk is installed during a bank, UPI or OTP scam. A sender check raises a bank-style SMS from a personal mobile number to at least \vlabel{SUSPICIOUS}. Call Guard, a Linux preview behind a flag, transcribes a shared voice note with Arm's INT8 Whisper Tiny on the CPU and applies digital-arrest call rules; its Android prototype compiles with the app but has no entry point in the UI and has not run on a phone. The newest features (report card and family share, screen-sharing banner, sender check, the app side of the typosquat check) and earlier interface additions (OTP masking, official-channel verdicts, opt-in history, font scale 2.0) were checked on an Android 14 emulator, not the phone, so they carry no Arm timings [A18].

On Linux, a CLI runs an 8-item demo benchmark and a loopback-only web UI serves the same pipeline. A rootless live monitor samples `/proc/net/tcp`, `/proc/net/tcp6` and `/proc/net/snmp` every 0.5\ s, without root or packet capture, to flag port scans, repeated login-port connects, half-open floods, periodic beacons and failed-connect bursts; it feeds these descriptions to the flow rules and an optional Llama explanation. The monitor is Linux-only (Android 10+ restricts `/proc/net`) and is separate from the NSL-KDD replay path [A11].

### Datasets and evaluation protocol

Table 4 summarises the data [A6]. Public sets are split with grouping to prevent leakage: SMS by normalised text, URLs by domain. Their eval splits, and the project's Indian eval set, were reused during development, so their scores are optimistic.


The Indian test sets are synthetic, with no real user messages, so they do not establish field performance. India v2 served only for validation; the other sets were written outside the detector work:

- **India v2** (400 messages) was aggregate-only adaptive validation: it shares an author with the visible development set and only its aggregate score was used, so it is not independent evidence and Table 8 does not report it.
- **India v3** is an independent development set recorded only as "authored blind", with no further authorship detail; its 81-message held-back split has 47 genuine messages and 34 scams [A11].
- **India v4** was written by an AI model (Gemini): 240 messages (140 genuine, 100 scam; 60% English, 25% Hinglish, 15% Hindi), split by label and category into 161 tuning and 79 held-back messages (47 genuine, 32 scam) [A12].
- **The blind validation set** was written by an AI coding agent with no access to the repository or any dataset, working from public RBI, NPCI, UIDAI and TRAI format guidance: 119 English, 60 Hindi and 61 Hinglish messages. Its scams barely test contactless fraud (84 of 90 carry a link or mobile number) [A12].
- **The sealed holdout** was authored independently of the detector developers by an AI model (Gemini). It holds 84 malicious and 100 benign items: 155 SMS-route (68 scam, 87 genuine) and 29 prompt-injection-route (16, 13) [A8].


| **Dataset** | **Licence** | **Split (n)** | **Use** |
|:------------------------------|:---------------|:----------------------------|:----------------------|
| UCI SMS Spam [20] + Mendeley SMS Phishing [21] | CC BY 4.0 | 4,127 / 607 / 1,162 | SMS model |
| PhiUSIIL URLs [22] | CC BY 4.0 | 40,000 / 4,000 / 7,997 | URL model |
| NSL-KDD [23] | UNB, with citation | 113,273 / 12,700 / 22,544 | Flow model (shifted test) |
| Indian and Hinglish seeds [24,\ 25] | \mbox{Apache-2.0}, CC BY 4.0 | 136 train rows | Indian-context model |
| Project Indian set (visible) | Original | 256 / 64 / 320 | Indian-context model |
| India v2, v3, v4 sets | Original | v2\ 400; v3\ 159\ +\ 81; v4\ 161\ +\ 79 | Tuning + held-back test |
| Blind validation set | CC0 | 240 (150 genuine, 90 scam) | False-alarm check |
| Sealed holdout | Original | 184 (155 SMS\ +\ 29 injection) | Repeatedly scored holdout |

Table: Datasets, licences and splits (train / dev / eval unless noted; "159\ +\ 81" is tuning\ +\ held-back). Table 8 reports the eval splits of the first three rows and of the visible Indian set, the held-back parts of v3 and v4, and the last two rows.


Author independence is not independence from model selection: the sealed set was scored at several detector checkpoints and its false alarms read, so it is an *independently authored, repeatedly scored holdout*, not an untouched estimate of generalisation. The v3 split was also used as a check during later fixes.

All headline detection numbers use conservative metrics: an `uncertain` verdict counts as an error on both classes (a miss for a scam, a false alarm for a genuine message), so coverage (the share of decided verdicts) is folded into recall and FPR. An earlier evaluation that gave half credit to `uncertain` is superseded [A3].

## Optimisation on Arm

Prahari targets an interactive response of about 1–2\ s and a bounded memory footprint on CPU-only Arm SoCs. The final build's warm KYC check met it in the all-items pass (1.857\ s) but not in the hotter gated pass (2.611\ s), and the six-item p90 on a small synthetic mix reached 3.977–5.252\ s (Section 5.1).

Table 5 lists the six engineering choices behind these numbers, separating the design rationale from what was measured and naming the ablation that was not run. None was isolated in a controlled on/off experiment on the phone.

On Neoverse-N1 the QLoRA INT4 export led SpinQuant INT4 on decode (Table 5) and on prefill (~83.1 against ~58–63\ tok/s), so it was kept [A4]. The prompt holds the verdict directive, a compressed evidence phrase and at most 320 input characters with links defanged; the six demo items used 109–128 prompt tokens (median 123) and generated 25–39 (median 28). Android's Python runtime offers only scikit-learn 1.3.2 (training uses 1.9.1), hence the JSON/NumPy export.


| **Technique** | **Rationale** | **Measured effect** | **Not measured** |
|:-------------------|:--------------------|:------------------------------------|:-------------------|
| Detector-first cascade | Keep the LLM off the verdict path | Detectors 0.42\ ms/item on Neoverse-N1; 5–17\ ms warm, 183\ ms URL (S23) | End-to-end gain over an LLM classifier |
| QLoRA INT4 weights (group-32, 8-bit activations) | Fit phone memory; faster decode | 19.9 vs 12–13.5\ tok/s decode over SpinQuant INT4 (N1, mixed host load); 1.100\ GiB (1.181\ GB) `.pte` | FP16 runtime baseline (size ≈2.47\ GB, computed only [A13]) |
| KleidiAI kernels via XNNPACK | Use `i8mm` and `dotprod` | 54.17% of CPU samples in `kai_*` (V2, 2 threads) | On/off speedup; dispatch on the phone |
| Compact prompt, greedy 40-token cap | Cut prefill and decode work | Median prompt 222 → 130 tokens, 5.39 → 3.67\ s/item (N1 28-item suite, mixed host load) | Controlled re-run on V2 or the phone |
| Model preload and reuse | Pay load and packing once | Descriptive only: cold first item 4.02–4.06\ s vs subsequent items 1.04–1.74\ s (V2, 2 threads; different inputs) | Controlled reload comparison |
| Portable detector export | No cross-version pickles | Parity with reference outputs on every build; 5–17\ ms warm (S23) | — |

Table: Optimisation techniques: rationale, measured effect and missing ablations. N1 comparisons ran under mixed host load and changed prompt content as well as length, so they are indicative only. "—": no missing measurement identified.



## Hardware Utilisation and Performance

We measured Prahari on three Arm targets with separate workloads and measurement boundaries: a Samsung Galaxy S23 phone, an Armv9 Neoverse-V2 Linux server (8 vCPUs) and a 2-vCPU Neoverse-N1 evaluation VM [A8,\ A9,\ A10].

### Galaxy S23 phone

The phone is a Samsung Galaxy S23 (SM-S911B, Snapdragon 8 Gen 2 / SM8550, Android 14, `arm64-v8a`; CPU flags include `asimddp`, `i8mm` and `bf16`). The APK used ExecuTorch Android with XNNPACK, declared no `INTERNET` permission, and the model and tokenizer matched their pinned hashes on the device. Table 6 gives the final measured build, run in two passes over six built-in samples (a cold-start first KYC check after preload, two warm KYC checks, a bill reminder, an official link and a lookalike link): first with Llama on every item, then with flagged-only gating. The model was preloaded before each pass, and warm checks and totals exclude that preload. The six-item p90 is over a synthetic mix that includes a cold check and a fallback, so it is not a production tail estimate. TTFT is time to first token; prefill ran at 165.0\ tok/s (all-items) and 113.8\ tok/s (gated). All phone timings are app-reported telemetry, and temperatures are battery readings [A17].


The first on-phone run (23 November) was faster: 6\ ms detector, 510\ ms TTFT, 43.4\ tok/s decode and 1.20\ s per warm KYC check (1.42\ s in Airplane Mode); an intermediate build measured medians of 2.90\ s and 21.5\ tok/s. In the latest run the battery warmed from 41.7\ °C to 45.1\ °C. The gated pass always ran second and hotter, so its slower KYC times may be thermal; neither the cause nor throttling was tested, and these times do not measure the effect of gating. For the lookalike link, Llama ran in both passes but no reply passed validation, so the app showed the detector's fixed text, labelled as not AI-written [A9,\ A14,\ A17].

| **Check (final build)** | **TTFT** | **Decode** | **Total** |
|:----------------------------------------------|----------:|----------:|---------------:|
| Warm KYC scam SMS, all-items pass (median, n\ =\ 2) | 879\ ms | 32.5\ tok/s | 1.857\ s |
| Warm KYC scam SMS, gated pass (median, n\ =\ 2) | 1,275\ ms | 23.9\ tok/s | 2.611\ s |
| Six-item median / p90, all-items pass | — | — | 1.984 / 3.977\ s |
| Six-item median / p90, gated pass | — | — | 2.611 / 5.252\ s |
| Bill / official link, gated (Llama skipped) | — | — | 0.186 / 0.312\ s |
| Lookalike link, all-items / gated (detector-text fallback) | — | — | 5.001 / 6.399\ s |

Table: Galaxy S23 app telemetry, final build (APK from commit 5b59ee2; Table 8 uses detector checkpoint 75993f1, Appendix B). Totals run from the Check tap, so the gated 0.186 / 0.312\ s include app, UI and Chaquopy overhead beyond detector time. "—": not reported.


### Neoverse-V2 and Neoverse-N1

Table 7 shows thread scaling on Neoverse-V2 (Debian 12, 8 vCPUs, 15\ GiB RAM, ExecuTorch 1.6.0). Each setting ran three processes × six items; values are means of the three run means [A10]. The 2-vCPU Neoverse-N1 evaluation baseline, on a 28-item suite, reached 83.1\ tok/s prefill, 19.9\ tok/s decode and 3.84\ s per item.

Going from 1 to 8 threads raised decode 4.07× and prefill 6.19× on Neoverse-V2, bringing mean per-item turnaround below 1\ s. At 2 threads, V2 delivered 2.53× the prefill (210.58 vs 83.1\ tok/s) and 2.35× the decode (46.69 vs 19.9\ tok/s) of the 2-vCPU N1 VM. The two machines ran under different conditions, so this ratio is descriptive and does not separate `i8mm`/KleidiAI from core design or memory bandwidth. Figure 3 plots the V2 thread scaling next to the per-target throughput.


| **Neoverse-V2 threads** | **TTFT** | **Prefill** | **Decode** | **Item wall** |
|:------------------------|-----------:|-------------:|-------------:|----------:|
| 1 | 1,465.5\ ms | 109.26\ tok/s | 25.69\ tok/s | 2.792\ s |
| 2 | 922.0\ ms | 210.58\ tok/s | 46.69\ tok/s | 1.728\ s |
| 4 | 907.7\ ms | 378.79\ tok/s | 75.89\ tok/s | 1.470\ s |
| 8 | 526.8\ ms | 676.80\ tok/s | 104.58\ tok/s | 0.980\ s |
| 8, warm items only | 159.3\ ms | 751.17\ tok/s | 104.31\ tok/s | 0.534\ s |

Table: Llama 3.2 1B INT4 on Neoverse-V2 (means over 3 runs × 6 items; the first item of each run is cold). The 4-thread TTFT varied widely (± 373.0\ ms).


![Arm performance. (A) Neoverse-V2 thread scaling (mean ± SD of 3 runs). (B) Per-target decode speed and item time; workloads differ (S23: warm in-app KYC check; V2: six-item mean with the cold first item; N1: 28-item suite), not a controlled comparison.](img/fig-arm-perf.pdf){#fig:arm-perf width=100%}

### Arm kernel evidence

The KleidiAI kernels are present in the ExecuTorch XNNPACK build (517 `kai_` symbols) [A5], and Prahari's INT4 matrix multiplications are observed executing in them on Neoverse-V2.

A whole-process `perf` profile of one 2-thread run, covering startup, model load and six inferences (~2,222 samples, 0 lost), put 54.17% of sampled CPU time in `kai_*` kernels: 23.27% in the `i8mm` prefill matmul, 20.57% in the `dotprod` decode matmul and 10.33% in packing and helper kernels [A10]. This is a CPU-time share, not a fraction of inference wall time. No supported runtime switch was found to disable KleidiAI, so an on/off speedup was not measured. Dispatch to these kernels on the phone has not been shown directly.

### Memory

On the Galaxy S23, `dumpsys meminfo` after a KYC check reported 1,744,842\ KiB (1,704\ MiB) total PSS and 1,867,396\ KiB (1,824\ MiB) RSS. PSS (proportional set size) splits shared pages among the processes that map them; RSS (resident set size) counts them in full. In the App Summary categories (Figure 4) the native heap was 1,566,056\ KiB (1,529\ MiB), 89.8% of PSS, followed by private other (58\ MiB, 3.4%), graphics (57\ MiB, 3.4%), code (37\ MiB, 2.1%) and Java heap, system and stack (22\ MiB, 1.3%). Model weights, the XNNPACK workspace and the KV cache are the expected contributors to that heap; `dumpsys` does not break it down, so their split was not measured.

![Galaxy S23 memory by `dumpsys meminfo` App Summary category (PSS) after a KYC check.](img/fig-memory.pdf){#fig:memory width=100%}

Peak sampled memory in the latest run was 1,795.3\ MiB PSS / 1,907.9\ MiB RSS; memory was polled every 500\ ms, so shorter spikes may be missed. On disk, the APK plus model and tokenizer take 1.147\ GiB (1.232\ GB). Runner RSS on Neoverse-V2 was 2,392.1\ MiB after generation, and the N1 VM peaked at 2.05\ GB (about 1.9\ GiB) of cgroup memory, which includes page cache. This footprint leaves little headroom on 4–6\ GB phones, and the eight checks of the first phone session are too few to show long-run stability [A9,\ A13].

\needspace{8\baselineskip}

## Results

### Detection performance

Table 8 reports the detector on the principal detection benchmarks, with conservative scoring (Section 3.5). The first four rows are eval splits reused during development and are optimistic; the last four had different degrees of development exposure [A8,\ A12].




\begingroup\renewcommand{\prahariTableFont}{\fontsize{10.3}{12.4}\selectfont}\KeepNoteWithTable

| **Set** | **n** | **Recall** | **F1** | **FPR (false alarms; 95% CI)** |
|:----------------------------------|------:|-------:|-------:|-----------------------------:|
| SMS eval split | 1,162 | — | 0.925 | — |
| URL eval split | 7,997 | 0.988 | 0.994 | 0.000 (0/4,000; 0.000–0.001) |
| Indian eval split (visible set) | 320 | — | 0.969 | 0.031 (5/160; 0.013–0.071) |
| NSL-KDD flow replay (`KDDTest+`) | 22,544 | 0.757 | 0.850 | 0.030 (294/9,711; 0.027–0.034) |
| India v3 held-back split^a^ | 81 | 0.941 | 0.970 | 0.000 (0/47; 0.000–0.076) |
| Blind validation set^b^ | 240 | 1.000 | 0.918 | 0.107 (16/150; 0.067–0.166) |
| India v4 held-back split^c^ | 79 | 0.969 | 0.805 | 0.298 (14/47; 0.187–0.440) |
| Sealed holdout^d^ | 184 | 0.929 | 0.812 | 0.300 (30/100; 0.219–0.396) |

Table: Detection results with conservative scoring and 95% Wilson intervals. Superscripts mark development exposure (notes below). "—": not logged by the run behind the row.

```{=latex}
\par\nobreak\vspace{-3pt}{\footnotesize\raggedright\setlength{\parskip}{0pt}\interlinepenalty=10000\noindent\textbf{Development exposure.} \textsuperscript{a}\,v3 split used as a check during later fixes. \textsuperscript{b}\,Blind set's false alarms read after the first scoring, never tuned on. \textsuperscript{c}\,v4 split never seen by the fixing work, scored once per candidate. \textsuperscript{d}\,Sealed holdout scored at several checkpoints (Table~9), false alarms read. The Indian eval count is FPR × 160 genuine items. Intervals reflect binomial count uncertainty only, not adaptive selection or field-population uncertainty.\par}
\endgroup
```



The holdouts differ mainly in how often genuine messages raise false alarms. A contact gate lets a text-model score flag a message only when the reader is given something to act on (a non-official link, number or chat handle, a request, a payment order or a threat). With it, the v3 split went from 6 to zero observed false alarms (0/47), and with later negation fixes the blind validation set fell from 31 to 16 of 150, both with recall unchanged. Zero observed false alarms on 47 genuine messages is still compatible with an FPR of up to 0.076.


On the v4 split, which the fixing work never saw, false alarms remain on advisories, bank and OTP alerts, delivery notices and links to small-business sites. The sealed holdout is harder still: every link in it uses a `.example` placeholder, which the gate treats as a contact and the domain rules call risky. As a result 28 of 87 genuine SMS (FPR 0.322; 95% CI 0.233–0.426) are still flagged, mostly advisories carrying such a link, family chats warning about scams, and doorstep or self-check messages [A12,\ A15].

Figure 5 plots the F1 and FPR of every benchmark in Table 8, showing the gap between development and held-back sets.

![Detection performance: conservative F1 and FPR for each benchmark in Table 8. "—": SMS eval FPR not recorded, as in Table 8. The sealed FPR bar covers all 100 benign items (30/100); its SMS route alone is 0.322 (28/87).](img/fig-eval-summary.pdf){#fig:eval width=100%}

Table 9 shows how the numbers on the sealed holdout moved as components were added; injection-route FPR stayed at 0.154 (2 of 13) after the rules and text model were frozen [A8,\ A15].


\begingroup\renewcommand{\prahariTableFont}{\fontsize{10.3}{12.4}\selectfont}

| **Configuration** | **Recall** | **FPR (FA / 100)** | **F1** |
|:------------------------------------------------|-------:|-----------------:|-------:|
| Initial baseline | 0.738 | 0.290 (29) | 0.709 |
| Rules + text model freeze | 0.917 | 0.310 (31) | 0.802 |
| After further recall tuning | 0.929 | 0.370 (37) | 0.784 |
| Current detector (contact gate, negation handling) | 0.929 | 0.300 (30) | 0.812 |

Table: Sealed holdout (n\ =\ 184; 100 benign items: 87 SMS, 13 injection-route) at successive checkpoints, each a reuse of the set. FA: false alarms.

\endgroup


### Explanation quality

We audited generated English and Hindi-mode explanations blind as correct, weak or wrong (Table 10). Each of the three fresh-item audits used 20 new items written by an AI agent that saw no project code or data; an LLM judge (OpenAI GPT-6.1 Terra) saw each item's before and after outputs as an unlabelled, shuffled A/B pair and applied a fixed rubric, and for Hindi rated correctness and accessibility (0–10) for a Hindi-only older reader. Both sides used the same detector. "Before" lacked grounded facts and, in Hindi mode, showed the Hindi steps, the English Llama text and a note that the AI text is in English; "after" added grounded facts and the fixed-text Hindi summary [A12]. The initial audit used a different judge (Google Gemini 4 Neon) and items and recorded only one side; no human audit was done on the fresh items.

Grounding did not reduce wrong English explanations (3, 5, 3 → 5, 5, 5); most remaining errors repeat a wrong detector evidence phrase. In Hindi the judge rated no "before" output and 5–9 of 20 "after" outputs correct, but 4–7 per audit were still wrong, mostly because the summary translates that same evidence. Hindi accessibility (0–10) rose 4.50 → 6.30, 3.50 → 5.45 and 4.05 → 6.40. In the last row, audit 3's items were regenerated and re-judged on both sides, and a later wording fix moved them from 8/2/10 to 9/4/7 (false input claims 9 → 6), but only via `.example`-domain wording that real SMS lack, so it overstates real gains [A15].

```{=latex}
\begingroup\def\prahariZebraStart{4}\renewcommand{\prahariTableFont}{\fontsize{10.3}{12.4}\selectfont}
\begin{longtable}[]{@{}>{\raggedright\arraybackslash}p{(\linewidth - 8\tabcolsep) * \real{0.44}}>{\raggedleft\arraybackslash}p{(\linewidth - 8\tabcolsep) * \real{0.14}}>{\raggedleft\arraybackslash}p{(\linewidth - 8\tabcolsep) * \real{0.14}}>{\raggedleft\arraybackslash}p{(\linewidth - 8\tabcolsep) * \real{0.14}}>{\raggedleft\arraybackslash}p{(\linewidth - 8\tabcolsep) * \real{0.14}}@{}}
\caption{Blind explanation audits (correct / weak / wrong), 20 items each, before and after grounding (judges in the text). In the bottom row, Before and After are the outputs before and after a wording fix, both grounded.}\label{tbl:audits}\tabularnewline
\toprule
 & \multicolumn{2}{c}{\textbf{English}} & \multicolumn{2}{c}{\textbf{Hindi}}\tabularnewline
\noalign{\vskip-1pt}\arrayrulecolor{prahariBorder}\cmidrule(lr){2-3}\cmidrule(l){4-5}
\textbf{Audit} & \textbf{Before} & \textbf{After} & \textbf{Before} & \textbf{After}\tabularnewline
\midrule
Initial audit (after only) & — & 5 / 8 / 7 & — & —\tabularnewline
Fresh-item audit 1 & 11 / 6 / 3 & 8 / 7 / 5 & 0 / 20 / 0 & 9 / 7 / 4\tabularnewline
Fresh-item audit 2 & 6 / 9 / 5 & 11 / 4 / 5 & 0 / 20 / 0 & 5 / 9 / 6\tabularnewline
Fresh-item audit 3 & 5 / 12 / 3 & 10 / 5 / 5 & 0 / 18 / 2 & 7 / 6 / 7\tabularnewline
\midrule
Audit 3 regenerated (pre / post wording fix) & 8 / 2 / 10 & 9 / 4 / 7 & — & —\tabularnewline
\bottomrule
\end{longtable}
\endgroup
```


### Verification

A regression suite of 1,355 detector and LLM-safety tests passes on the current detector, including 39 tests for the live monitor and about 120 Call Guard call-script cases, with Android parity and manifest-permission checks in CI [A11,\ A12]. The rootless connection monitor classified a 150-port loopback scan as `scam`, a quiet window as `benign`, and a closed-port scan as `uncertain` from kernel counter jumps.

## Responsible AI, Limitations and Future Work

### Responsible AI and privacy

Prahari is private by design: the APK requests no `INTERNET` permission, disables backup, sends no telemetry and runs every model on the phone, so messages, OTPs and bank alerts leave the device only if the user shares a warning or copies a report. The design is advisory: vetted English and Hindi steps and the official reporting channels (Chakshu, 1930, cybercrime.gov.in) always appear above the AI card, which warns it "can be wrong", and a benign result reads "\vlabel{NO RISK FOUND} — still verify", never "safe". AI tools helped with mockups, Hindi copy review, coding and code review; we checked every design choice, measurement and safety text [A7].

### Limitations

- **False alarms on genuine notices.** The sealed-holdout FPR is 0.300 overall (SMS + injection, 30/100) and 0.322 on SMS (28/87), mostly on advisories and family warnings; automatic background SMS scanning stays disabled until it falls well below that on unseen data.
- **Synthetic test data.** Every Indian test set is synthetic and AI- or blind-authored; none contains real user messages, so field performance is not established.
- **Phone performance is not yet stable.** Galaxy S23 latency and throughput differed between builds and runs (Table 6) for reasons not established; no run started from a cool phone and samples are small. KleidiAI kernels were observed executing, but no on/off speedup was measured.
- **Memory headroom.** Peak memory of about 1.7–1.9\ GiB (Section 5.4) leaves little room on 4–6\ GB phones; a mid-range phone has not been tested.
- **Hybrid scams.** A few adversarial scams that mix an official app with an unofficial link still pass the rules.
- **Explanations and emulator-only checks.** The blind audits still rate some English explanations wrong, and the AI prose is English only (the Hindi summary is fixed text). Several app features (report card, remote-app banner, sender check, APK-link warning) were checked only on the emulator, and TalkBack is untested.
- **Network scope.** The live connection monitor is Linux-only, samples sockets rather than capturing packets, and is separate from the NSL-KDD replay classifier; Call Guard has no Android entry point yet.

### Future work

<!-- The last two items are kept together so the final item is never stranded on a new page. -->

\begin{itemize}
\tightlist
\item \textbf{Wider, safer coverage.} A pause-and-explain link interstitial, screenshot OCR, opt-in notification scanning once false alarms are low enough, and Call Guard on the phone with a Hindi-capable speech model.
\item \textbf{Fresher threat knowledge offline.} A refreshed local snapshot of a phishing feed such as OpenPhish or PhishTank (within licence terms) and signed offline rule-pack updates.
\item \textbf{Faster, leaner Arm execution.} SME2 on newer Arm CPUs and phone NPUs; a smaller KV cache (2048 → 512 context) targeting under 1.35~GB (about 1.26~GiB) PSS; and a cool-start S23 re-measurement with longer samples.
\KeepWithPreviousItem
\item \textbf{More languages and real users.} Marathi, Tamil, Telugu and Bengali with consented, licensed real messages and a fresh single-shot holdout, and comprehension tests with elderly users (200\% font, TalkBack).
\end{itemize}

## Conclusion

Prahari shows that useful scam triage can run entirely on an Arm phone: deterministic detectors and Indian-context rules decide, Llama 3.2 1B only explains, and the message and link pipeline runs offline on a Galaxy S23 phone and on Arm Linux through ExecuTorch XNNPACK. On the phone, a warm KYC check takes a median 1.857\ s in the all-items pass (two checks) with no network permission. On Neoverse-V2 the 8-thread runner averages 0.980\ s per item, and a separate whole-process profile of a 2-thread run put 54.17% of sampled CPU time in KleidiAI kernels.

On the v3 held-back split the detector reaches F1 0.970 with zero observed false alarms (0/47; 95% CI 0.000–0.076), but on the independently authored, repeatedly scored sealed holdout its FPR is still 0.300 (30/100). The other open limits are equally concrete: synthetic test data; small and thermally uncontrolled phone samples; no measured KleidiAI on/off speedup; about 1.7–1.9\ GiB of memory; and English explanations that the LLM judge still rated wrong at the audited checkpoints: 5 of 20 in each fresh-item audit, and 7 of 20 in a later re-judgement of reused items. Section 7 lists next steps for each.

\needspace{8\baselineskip}

## References {.unnumbered}

External sources are numbered in order of first citation; project evidence [A1]–[A18] is listed in Appendix A. Web pages without publication dates were accessed 24 November 2026.

\RefsBegin

\refl{1} Meta. *Llama 3.2 Community License* and *Acceptable Use Policy*. \refurl{www.llama.com/llama3_2/license/}; \refurl{www.llama.com/llama3_2/use-policy/}. Weights are obtained separately by users; Prahari's own code is MIT-licensed, and framework licences (ExecuTorch/PyTorch/scikit-learn BSD-3-Clause, Arm KleidiAI Apache-2.0, Chaquopy MIT) apply to their components.

\refl{2} Press Information Bureau, Government of India (2024). *Ministry of Home Affairs advisory on fake "digital arrest" and courier impersonation*. \refurl{www.pib.gov.in/PressReleasePage.aspx?PRID=2077948}

\refl{3} Press Information Bureau, Government of India (2026). *I4C financial-fraud complaint figures, 2021–2025*. \refurl{www.pib.gov.in/PressReleasePage.aspx?PRID=2287039}

\refl{4} Google. *New Android scam protections*. Google blog. \refurl{blog.google/security/new-android-scam-protections/}

\refl{5} Google. *Staying one step ahead: strengthening Android's lead in scam protection*. Google blog. \refurl{blog.google/security/staying-one-step-ahead-strengthening-androids-lead-in-scam-protection/}

\refl{6} Techzei. *Google Messages enhanced scam detection and India availability*. \refurl{techzei.com/google-messages-enhanced-scam-detection-india/}

\refl{7} Neoteo. *Samsung names Japan, Canada and India for Scam Detection*. \refurl{www.neoteo.com/en/samsung-names-japan-canada-and-india-for-scam-detection}

\refl{8} C&K Lab. *Galaxy spam/smishing block settings*. \refurl{candklab.com/en/blog/galaxy-spam-smishing-block-settings/}

\refl{9} Truecaller. *Fraud Protection*. Press release. \refurl{corporate.truecaller.com/newsroom/press-release/28923657E2813595}

\refl{10} Truecaller. *Protect yourself from SMS scams with Truecaller's fraud protection*. Truecaller blog. \refurl{www.truecaller.com/blog/features/protect-yourself-from-sms-scams-with-truecallers-fraud}

\refl{11} Truecaller. *Premium Terms of Service*. \refurl{www.truecaller.com/premium-terms-of-service}

\refl{12} GSMA. *Airtel spam detection solution*. GSMA scams study. \refurl{www.gsma.com/solutions-and-impact/technologies/security/scams/gsma_study/airtel-spam-detection-solution/}

\refl{13} Bitdefender. *Scam Protection / Scamio (India)*. \refurl{www.bitdefender.com/en-in/consumer/scam-protection}

\refl{14} McAfee. *Scam Detector*. \refurl{www.mcafee.com/en-us/scam-detector/}

\refl{15} Norton. *AI scam protection (Norton Genie)*. \refurl{in.norton.com/feature/ai-scam-protection}

\refl{16} Department of Telecommunications. *Sanchar Saathi — Chakshu (report suspected fraud communication)*. \refurl{sancharsaathi.gov.in/sfc/}

\refl{17} Telecom Regulatory Authority of India (2025). *Direction of 19 November 2025* (DLT headers and 1600-series numbers for BFSI calls). \refurl{www.trai.gov.in/sites/default/files/2025-11/Direction_19112025.pdf}

\refl{18} Saavalainen (2026). *On-Device Phishing Explanation Generation Using Small Language Models*. Thesis, University of Helsinki. \refurl{hdl.handle.net/10138/638168}

\refl{19} ElZemity et al. (2026). *Agentic Knowledge Distillation: Autonomous Training of Small Language Models for SMS Threat Detection*. arXiv:2602.10869. \refurl{arxiv.org/abs/2602.10869}

\refl{20} Almeida, T. A., et al. (2011). *SMS Spam Collection*. UCI Machine Learning Repository, CC BY 4.0. \refurl{archive.ics.uci.edu/dataset/228/sms+spam+collection}

\refl{21} Mishra, S., and Soni, D. (2022). *SMS Phishing Dataset*. Mendeley Data, CC BY 4.0. \refurl{data.mendeley.com/datasets/f45bkkt8pr}

\refl{22} Prasad, A., and Chandra, S. (2024). *PhiUSIIL Phishing URL Dataset*. UCI Machine Learning Repository, CC BY 4.0. \refurl{archive.ics.uci.edu/dataset/967}

\refl{23} Tavallaee, M., et al. (2009). *NSL-KDD dataset*. Canadian Institute for Cybersecurity, University of New Brunswick; redistribution permitted with citation. \refurl{www.unb.ca/cic/datasets/nsl.html}

\refl{24} karanverma19. *Indian Multilingual Scam Message Dataset*. Hugging Face, Apache-2.0. \refurl{huggingface.co/datasets/karanverma19/Indian_Multilingual_Scam_Message_Dataset}

\refl{25} bolewara. *Hinglish scam text dataset*. Hugging Face, CC BY 4.0. \refurl{huggingface.co/datasets/bolewara/hinglish-scam-text-dataset}


\RefsEnd

\needspace{14\baselineskip}

\AppendixTables

## Appendix A: Artifact and Provenance Index {.unnumbered}

| **Label** | **Evidence** | **Repository path** |
|:------|:--------------------------------------|:----------------------------------------------|
| A1 | Official challenge brief (PS3) and IIT Delhi PS3 mentoring guidance | \fpath{docs/challenge-brief.md} |
| A2 | Detector, rules and app server | \fpath{candidates/BEST/} (\fpath{REPORT.md}, \fpath{DATA.md}, \fpath{app/server.py}, \fpath{triage/*.py}) |
| A3 | Historical evaluation with half credit for uncertain verdicts, superseded by conservative scoring | \fpath{research/evals/20261111-075405-best-confirm/} |
| A4 | Research log, leave-one-category-out check and data preparation | \fpath{research/LOG.md}, \fpath{research/REPORT.md}, \fpath{research/stress/loco.py}, \fpath{eval/prep_data.py} |
| A5 | ExecuTorch 1.6.0 XNNPACK `kai_` symbol inspection on Arm Linux (517 symbols) | \fpath{docs/phase1/EVIDENCE.md} |
| A6 | Dataset sources, attributions and licences | \fpath{candidates/BEST/DATA.md} |
| A7 | Android app, CI manifest and permission audits, emulator screenshots | \fpath{android/}, \fpath{.github/workflows/android.yml}, \fpath{docs/phase1/EVIDENCE.md} |
| A8 | Neoverse-N1 evaluations, sealed-holdout scores with counts, initial 20-item explanation audit | \fpath{docs/phase1/evidence/sealed-holdout/scores.json}, \fpath{docs/phase1/EVIDENCE.md} |
| A9 | Galaxy S23 first run (23 November 2026): device properties, hash checks, Airplane Mode checks, `dumpsys meminfo` | \fpath{docs/phase1/evidence/galaxy-s23/}, \fpath{docs/phase1/img/s23-*.png} |
| A10 | Neoverse-V2 benchmark (23 November 2026): `perf` KleidiAI profile, thread scaling, `unshare -n` offline proof | \fpath{docs/phase1/evidence/neoverse-v2/} |
| A11 | Live Linux connection monitor and its 39 tests; explanation honesty fixes, India v3 held-back results and Android UX update (23 November 2026) | \fpath{candidates/BEST/triage/live.py}, \fpath{candidates/BEST/bin/monitor}, \fpath{candidates/BEST/tests/test_live.py}, \fpath{docs/phase1/EVIDENCE.md} |
| A12 | SMS false-alarm fix and blind validation set; Call Guard preview; grounded explanations, Hindi summary and audits; v4 set; UPI QR checker and emulator captures (24 November 2026) | \fpath{research/fpfix/}, \fpath{docs/call-guard.md}, \fpath{research/explain-audit.md}, \fpath{research/v4-heldout/RESULTS.md}, \fpath{research/app-r3-verify/} |
| A13 | Performance methodology, optimisations and harness (16 harness tests) | \fpath{docs/perf/}, \fpath{docs/perf/evidence/}, \fpath{bench/perf/} |
| A14 | Galaxy S23 intermediate run (24 November 2026): per-check results, memory, battery, hashes, demo clips | \fpath{docs/perf/s23-final-20261124.md}, \fpath{evidence/galaxy-s23-20261124/} |
| A15 | Validation gate and explanation re-judgement; report card, remote-access app banner, APK-link check | \fpath{bin/validate}, \fpath{docs/validation-gate.md}, \fpath{android/python/report_card.py}, \fpath{android/app/src/main/java/in/prahari/app/RemoteApps.kt}, \fpath{docs/typosquat.md} |
| A16 | Sender check and lookalike-link statistics | \fpath{docs/sender-check.md}, \fpath{candidates/BEST/triage/sender.py}, \fpath{evidence/galaxy-s23-20261124/} |
| A17 | Galaxy S23 final measured build (24 November 2026): gating run on the release APK | \fpath{docs/perf/s23-gating-20261124.md}, \fpath{docs/perf/evidence/galaxy-s23-gating-20261124/retry/} |
| A18 | Emulator feature check and two failed S23 sessions on 25 November 2026 (same APK as A17) | \fpath{evidence/android-emulator-20261125/summary.md}, \fpath{evidence/galaxy-s23-20261125/} |

Table: Project evidence index (paths relative to the repository root).

## Appendix B: Reproducibility Card {.unnumbered}

The steps below rebuild the Linux detector, its explanations and the validation gate on an aarch64 machine from the public repository at the git tag `phase1-report`, the revision this report describes. They reproduce the pipeline, not every number: the held-back results in Table 8 (v3 and v4 held-back splits, sealed holdout) also need the detector at checkpoint \mbox{\hash{75993f1}} and datasets that are not in the repository.


\begingroup\raggedright\setlist{itemsep=6pt, topsep=5pt, parsep=1pt}

1. **Clone.** Clone the public repository and check out the report revision:

    ```
    git clone https://github.com/rabesss/prahari.git && \
      cd prahari && git checkout phase1-report
    ```

2. **Install.** With Python 3.12, create a virtual environment and install the detector requirements (pinning ExecuTorch 1.6.0) and the Hugging Face CLI:

    ```
    python3.12 -m venv .venv && . .venv/bin/activate
    pip install -r candidates/BEST/requirements.txt
    pip install 'huggingface_hub[cli]'
    ```

\endgroup

\KeepTables

| **Item** | **Value** |
|:----------------------|:--------------------------------------------------------------|
| Repository | \refurl{github.com/rabesss/prahari} |
| Report revision | Git tag `phase1-report` |
| Android APK release | \refurl{github.com/rabesss/prahari/releases/tag/phase1-apk-5b59ee2}, built from commit \hash{5b59ee2fcaaa2b6153f9a302abb76a1aac5dd317} |
| APK SHA-256 | \hash{88f6a53285c04ef8e0fb7766b05da716dbdc22a4b11112e731b70165e3d07862} |
| Model SHA-256 | \hash{ab7b7ebf97421c7770ad97d4abfdf8650a7d9f9dc1ce9a0c4663d49f7b7a08ac} (file \path{Llama-3.2-1B-Instruct-QLORA_INT4_EO8.pte}) |
| Tokenizer SHA-256 | \hash{82e9d31979e92ab929cd544440f129d9ecd797b69e327f80f17e1c50d5551b55} (file \path{tokenizer.model}) |
| Held-back detector checkpoint | Commit \hash{75993f19c590144d2369fcfb70d430429daa7990}: Table 8 held-back rows, last row of Table 9 (\path{docs/validation-gate.md}) |
| Table 9, rows 1–3 | Checkpoint entries 1, 2 and 4 (the last is commit \hash{7368067}) in \path{docs/phase1/evidence/sealed-holdout/scores.json} |
| Table 8, eval rows | SMS, Indian: false-alarm reduction entry; URL: typosquat gate run (both \path{docs/phase1/EVIDENCE.md}); flow: \path{candidates/BEST/REPORT.md} |
| Data not in the repository | v3 and v4 held-back splits, sealed holdout (hashes pinned in \path{eval/validate.py}); their rows cannot be re-run from the repository alone |

Table: Reproducibility card.

\begingroup\raggedright\setlist{itemsep=6pt, topsep=5pt, parsep=1pt}

3. **Fetch the model.** The Llama 3.2 model is gated on Hugging Face: request access on the model page, accept the Llama 3.2 licence [1] and authenticate with `hf auth login` (never commit the token). Download both files and check them against Table 12 with `sha256sum`.

    ```
    hf auth login
    M=executorch-community/Llama-3.2-1B-Instruct-QLORA_INT4_EO8-ET
    hf download "$M" --local-dir "$PWD/.venv/models/qlora"
    ```

4. \interlinepenalty=10000 **Point the model registry at it.** Run the short Python snippet in the README section "Run on aarch64 Linux", which copies `models/registry.json` to `.venv/prahari-registry.json` with the downloaded file paths (the tracked file stays untouched), then export the copy as `HC_MODEL_REGISTRY`, exactly as the README does:

    ```
    export HC_PY="$PWD/.venv/bin/python" \
      HC_MODEL_REGISTRY="$PWD/.venv/prahari-registry.json"
    ```

5. **Validate and run the demo.** `bin/validate` scores the committed sets and runs the test suites (`--baseline BEFORE.json` fails on any recall drop or FPR rise; sets not in the repository are reported as not scored; `--sealed` scores the sealed set, once per frozen candidate). The 8-item demo (SMS, URL, UPI, flow, injection) can exit with status 1 when the lookalike-link explanation fails validation; it still prints the verdict and "Explanation unavailable" (see README).

    ```
    bin/validate
    candidates/BEST/bin/app --selftest
    candidates/BEST/bin/app --demo --out .venv/demo.json
    ```

\endgroup
