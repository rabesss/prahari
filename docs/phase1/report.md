---
title: "Prahari: Offline On-Device Threat, Phishing and Scam Triage on Arm"
subtitle: "Arm Bharat AI-SoC Challenge 2026–27 (PS3) — Phase 1 Technical Report"
author: "Prahari contributors"
date: "25 November 2026"
---

## Abstract {.unnumbered}

Prahari is an offline cybersecurity triage assistant for Indian smartphone and Arm Linux users, built for Problem Statement 3 of the Arm Bharat AI-SoC Challenge 2026–27 [S1]. Compact classical models and transparent Indian-context mechanism rules classify suspicious SMS and WhatsApp-style messages, phishing URLs, prompt-injection attempts and network events on the device. Llama 3.2 1B Instruct, quantized to 4-bit integers (INT4) with quantization-aware LoRA training (QLoRA) and running through ExecuTorch XNNPACK on the Arm CPU, then explains the structured evidence in plain language next to vetted safety steps [S2, S9, S10]. On a Samsung Galaxy S23 phone, a warm KYC check takes a median 1.857 s at 32.5 tok/s decode, and the app declares no network permission. On Arm Neoverse-V2, 54.17% of sampled CPU time runs inside Arm KleidiAI kernels. We report every holdout, including a sealed final set (n = 184) where the false-positive rate (FPR) remains 0.300. Prahari is strictly advisory: inference and storage stay on the device, and content leaves the app only when the user chooses to share a warning or copy a report. Built with Llama.

**Keywords:** on-device AI, scam detection, phishing, Arm, KleidiAI, ExecuTorch, Llama 3.2, India, privacy

## Introduction

Indian smartphone users routinely receive fraudulent messages built around familiar domestic rails: UPI collect requests disguised as refunds, fake KYC or PAN/Aadhaar suspension warnings, electricity-disconnection threats, courier and customs fees, task-recharge scams, and "digital arrest" impersonation of police or regulators. The Ministry of Home Affairs has publicly warned about fake digital arrests and courier impersonation [P1]. NCRB recorded 101,928 registered cybercrime cases in 2024, and I4C separately reported more than 6,589,201 financial-fraud complaints totalling over Rs 55,050 crore on the national portal across 2021–2025 [P2]. Registered cases and portal complaints are distinct measures and do not quantify Prahari's target user base.

The detection problem is hard because genuine bank debit alerts, OTP notifications, bill reminders and telecom advisories share the same vocabulary ("OTP", "Rs", "UPI", "account", "KYC", "blocked") across English, Devanagari Hindi and Romanised Hinglish. A keyword filter flags legitimate alerts until users ignore it, and a cloud-LLM wrapper sends private banking texts off the device. Following the PS3 brief and mentor guidance, Prahari keeps all inference local on Arm hardware and asks *what the sender wants the recipient to do*, which separates scams from benign informational notices [S1, S2].

This report makes four contributions:

1. **A hybrid detect-then-explain pipeline.** Deterministic classifiers and Indian-context mechanism rules decide the verdict; Llama 3.2 1B only explains the structured evidence.
2. **An on-device Arm deployment.** The full pipeline runs on a Samsung Galaxy S23 phone and on Arm Linux through ExecuTorch XNNPACK, with profiled execution inside Arm KleidiAI `kai_*` kernels [S9, S10].
3. **Verified offline operation.** The Android app declares no `INTERNET` permission and was tested in Airplane Mode; on Linux, inference passes with the network namespace cut [S9, S10].
4. **An honest evaluation.** We report development sets and every holdout, including an independently authored sealed set that was scored repeatedly during development, together with its remaining false alarms [S8, S11, S12, S15].

Table 1 summarises the headline results and Figure 1 shows them at a glance; Sections 5 and 6 give the full measurements and caveats. Throughout, recall is the share of scams flagged, the false-positive rate (FPR) is the share of genuine messages flagged, and F1 is the harmonic mean of precision and recall.

\needspace{9\baselineskip}

| Metric | Result | Setting |
|:------------------------|:------------------------|:------------------------|
| Warm KYC check, phone | 1.857 s median, 32.5 tok/s | Galaxy S23, small sample |
| Linux throughput | 0.98 s/item, 104.6 tok/s | Neoverse-V2, 8 threads |
| KleidiAI share of CPU time | 54.17% | Neoverse-V2, `perf` |
| India v3 held-back set | F1 0.970, FPR 0.000 | n = 81 |
| Sealed final holdout | F1 0.812, FPR 0.300 | n = 184, scored repeatedly |

Table: Key Phase 1 results. Phone timings come from two warm KYC checks per pass; the sealed-set false alarms are discussed in Section 6.1.

![Results at a glance. Detection F1 and FPR on the held-back and sealed sets, warm latency on the Galaxy S23, Llama 3.2 1B decode throughput on Neoverse-V2, and Galaxy S23 memory. All values appear in Tables 1, 4, 5 and 6 and Section 5.4; the memory panel's "everything else" bar (175 MiB) is derived as total PSS minus native heap.](img/fig-overview.png){#fig:overview width=88%}


## Related Work

India already has strong anti-scam tools, but none of them explains a suspicious message in plain Hindi or English on a mid-range phone with no network. Table 2 compares the closest products on four properties; product facts come from the cited vendor and government pages, checked on 24 Nov 2026.

\needspace{11\baselineskip}

| Product | Offline | India rails | Explains | Link/QR |
|:------------------------------------------------|:--------|:--------|:--------|:--------|
| Google Messages Scam Detection [G1, G2, G3] | Partial | No | No | Yes |
| Pixel / Samsung call and message guards [G2, SM1, SM2] | Yes | Partial | No | No |
| Truecaller Fraud Protection [T1, T2, T3] | Partial | Yes | No | Partial |
| Airtel network spam and link protection [A1] | No | Yes | No | Yes |
| Bitdefender Scamio; McAfee; Norton Genie [B1, M1, N1] | No | No | Partial | Yes |
| Sanchar Saathi Chakshu, 1930, TRAI DLT rules [D1, D2] | No | Yes | No | No |
| **Prahari (this work)** | **Yes** | **Yes** | **Yes** | **Partial** |

Table: Feature comparison with related products. Offline: inference without a network (Partial: some modes send data to the cloud). India rails: Hindi/India support or routing to Indian reporting channels. Explains: plain-language reason for a verdict. Link/QR: link or QR-code checking.

The closest products split along the same line. Google Messages runs standard scam detection on-device, but its Enhanced mode sends conversations with unknown senders to cloud Gemini, and Hindi is not among its listed languages. Truecaller filters SMS on-device at scale for India, while its caller ID and spam database are cloud and crowdsourced. Scamio, McAfee and Norton answer questions about texts, links and QR codes, but only in the cloud and in English.

Research points the same way. Saavalainen [R1] ran Gemma 3n-E2B-it zero-shot on an Android phone on Finnish SMS: it missed 15 of 41 dangerous messages (63.4% recall) against 2 of 41 for a cloud model (95.1%), and produced more unsupported details. The thesis concludes that small models "appear more suitable as part of a broader detection and explanation pipeline than as standalone phishing detectors". ElZemity et al. [R2] distil LLM teachers into Qwen2.5-0.5B and SmolLM2-135M SMS classifiers, reaching 94.31% accuracy and 96.25% recall, but give the user no explanation.

Prahari fills the gap between these lines of work: detectors decide, as in [R2], and Llama 3.2 1B only explains, as [R1] recommends. Its distinct combination is Indian scam mechanisms in English, Hindi and Hinglish; vetted next steps (Chakshu, 1930, cybercrime.gov.in) for every verdict with an attempted plain-language explanation for every risky one (falling back to labelled fixed text when no generated reply passes the checks); and no network at inference on a phone that is not a current flagship. Its main gaps are equally clear. Prahari does not sit in the message or call path, has no link-reputation feed (only rules, including a typosquat list of 56 Indian official domains), and its false-alarm rate on hard benign notices is still high (Section 6.1).


## System Design and Methodology

### Architecture

Prahari splits each decision into two stages (Figure 2). Stage 1 is a set of compact detectors and transparent rules that decide the verdict and extract typed evidence. Stage 2 is Llama 3.2 1B, run on the device through ExecuTorch, which turns that evidence into a short plain-language explanation.

The language model never decides the verdict and never chooses critical helpline actions. It only explains the detector's evidence, so a hallucination or a prompt injection hidden in an untrusted message cannot flip a \vlabel{DANGEROUS} item to \vlabel{NO RISK} [S2, S8]. Stage 1 is also fast: 0.42 ms per item on Arm Linux, and 5–17 ms warm for text checks on the Galaxy S23 phone (183 ms for a URL; 16–80 ms in a later build).

![Prahari architecture. Stage 1 detectors and rules decide the verdict and extract evidence; Stage 2 (Llama 3.2 1B on ExecuTorch) explains it on the device, and fixed vetted steps are shown above the AI text.](img/fig-architecture.png){#fig:arch width=100%}

### Stage 1 detectors and Indian-context rules

Stage 1 combines four small scikit-learn models with a rule layer. The SMS model uses word and character TF-IDF (term frequency–inverse document frequency) features with logistic regression, trained on English SMS corpora. The URL model adds character n-gram TF-IDF to lexical indicators: punycode and homoglyph digit swaps, brand lookalikes on disposable TLDs such as `.top` and `.xyz`, missing HTTPS, IP hosts and excessive subdomains. URLs are never fetched.

The Indian-context model joins character and word n-grams with a 19-dimension mechanism feature vector, so unseen Hindi and Hinglish spellings still activate shared cues. The flow model is a histogram gradient-boosted tree over NSL-KDD's 41 named features, plus three high-precision intrusion signatures (failed-login bursts, malformed fragments, same-source/destination loops) that fire on 0.10% (75/74,112) of normal train and dev records [S2, S4].

The mechanism layer first normalises zero-width characters, full-width Unicode and spaced capitals. It then separates harmful mechanics from benign ones. Harmful mechanics include requests for OTP, PIN, CVV or card details; payment to a personal number, UPI ID, "safe" account or lookalike domain; UPI collect requests; installing a screen-sharing or remote-access APK; digital-arrest coercion; upfront job, loan, customs or prize fees; and sending ID papers to a chat or link. Benign mechanics include completed receipts, OTP notifications, routine bills, official app pointers and protective disclaimers.

Precedence is deliberately asymmetric. A decisive harmful mechanic overrides a protective disclaimer, because scammers routinely write *"no OTP needed, pay Rs 499 fee"*. In the other direction, a contact counts only when an action names it, toll-free numbers are distinguished from personal mobiles, and advisories without a spoofed contact are cleared [S11].

Genuine-looking bank debit alerts that advise blocking the card in the bank app get a cautious \vlabel{uncertain} verdict rather than a scam label. The app shows it as an amber \vlabel{CHECK THIS ALERT} banner (or \vlabel{SUSPICIOUS} when the alert names an unofficial link or private number) with the step *"Didn't make this payment? Call 1930 and block the card or UPI in your bank app"* [S7, S8]. Untrusted text is also scanned by a dedicated prompt-injection route and is always framed as quoted data inside the Llama prompt [S2].

### Stage 2 grounded explanation and safety checks

Stage 2 runs Meta's INT4 QLoRA release of Llama 3.2 1B Instruct through ExecuTorch's `TextLLMRunner` on Linux and `LlmModule` on Android [S2, S7]. The prompt supplies the authoritative verdict, a short scam category and a compressed evidence phrase, neutralises live URLs, and asks for a verdict-first sentence followed by one protective step.

Fixed India-specific steps always appear above the AI text. Sanchar Saathi Chakshu is primary for scam messages and links before any loss, 1930 is primary once money has been debited, and cybercrime.gov.in is shown for extortion and sextortion [S7].

The second sentence is grounded. The prompt carries one vetted, advice-led key fact per scam type or benign reading, and Llama writes its own sentence from it instead of filling an empty slot with stock lines [S12].

Deterministic checks then validate the output [S8, S11, S12]:

- A generated sentence is dropped if it claims a link, number, device or domain the item lacks, makes an unsupported OTP, payment, app or KYC claim, hedges against a \vlabel{NO RISK} verdict, or is vague, first-person, overclaiming or mixed-script. The vetted fact replaces it.
- \vlabel{NO RISK} openings assert only the absence of elements that are actually absent, and never cite an overruled risk signal.
- Repeated sentences are removed, and generated questions (such as *"Can I help you with something else?"*) are stripped or replaced by the scam type's vetted step.
- If no model text survives, the explanation is reported as failed rather than passed off as model output.

Hindi mode shows a fixed-text Hindi summary built from the detector result and labelled as not AI-written. The 1B model cannot write usable Hindi, so the Llama explanation stays in English.

### Applications

The Android app is fully offline. It uses a Kotlin UI, Chaquopy 17.2.0 (Python 3.10, NumPy 1.26.2) and the ExecuTorch Android 1.5.1 AAR. It declares no `INTERNET` permission, checked automatically on every build, and disables backup. Messages arrive through the Android share sheet or text selection; the app offers an EN/Hindi toggle, offline text-to-speech over the vetted verdict and steps, quoted evidence with defanged URLs and masked OTPs, opt-in redacted local history (off by default), and an on-device QR photo decoder that needs no camera or storage permission [S7, S11].

Later additions extend coverage to Indian payment and device scams. A UPI QR checker parses `upi://` links offline and flags collect requests, payee mismatches and "scan to receive" lures. A typosquat check flags near copies of 56 Indian official domains and direct `.apk` downloads. *Copy report* drafts a masked, defanged Chakshu report and *Send to family* shares a short warning with no message details. An amber banner appears when AnyDesk, TeamViewer, AirDroid or RustDesk is installed during a bank, UPI or OTP scam. A sender check raises a bank-style SMS from a personal mobile number to at least \vlabel{SUSPICIOUS} [S16]. A Call Guard preview, behind a flag, transcribes a shared voice note with Arm's INT8 Whisper Tiny on the CPU and applies digital-arrest call rules. The newest Android features (report card and family share, screen-sharing banner, sender check, and the app side of the typosquat check) were checked on an Android 14 emulator with the same APK, not yet on the phone [S18].

On Linux, a CLI runs an 8-item demo benchmark and a loopback-only web UI serves the same pipeline. A rootless live monitor samples `/proc/net/tcp`, `/proc/net/tcp6` and `/proc/net/snmp` every 0.5 s, without root or packet capture, to flag port scans, repeated login-port connects, half-open floods, periodic beacons and failed-connect bursts; it feeds these descriptions to the flow rules and an optional Llama explanation. The monitor is Linux-only (Android 10+ restricts `/proc/net`) and is separate from the NSL-KDD replay path [S11].

### Datasets and evaluation protocol

Table 3 summarises the data. Public sets are split with grouping to prevent leakage: SMS by normalised text, URLs by domain.

\needspace{11\baselineskip}

| Dataset | Licence | Split (n) | Use |
|:----------------------------------|:--------------|:---------------------------|:--------------|
| UCI SMS Spam [DS1] + Mendeley SMS Phishing [DS2] | CC BY 4.0 | 4,127 / 607 / 1,162 | SMS model |
| PhiUSIIL URLs [DS3] | CC BY 4.0 | 40,000 / 4,000 / 7,997 | URL model |
| NSL-KDD [DS4] | UNB, with citation | 113,273 / 12,700 / 22,544 | Flow model (shifted test) |
| Indian and Hinglish seeds [DS5] | Apache-2.0, CC BY 4.0 | 136 train rows | Indian-context model |
| Project India sets (visible, v2, v3, v4) | Original | 256 / 64 / 320; v2 400; v3 159 tune + 81 held-back; v4 161 tune + 79 held-back | Tuning and validation |
| Sealed holdout; `fp_val_v1` | Original; CC0 | 184 (155 SMS + 29 injection); 240 | Final test; false alarms |

Table: Datasets, licences and splits (train / dev / eval unless noted). The v3 and v4 sets were each split into a tuning part and a held-back test part; Table 6 reports the held-back parts.

All headline detection numbers use conservative metrics: an \vlabel{uncertain} verdict counts as an error on both classes, so a scam left \vlabel{uncertain} is a miss and a genuine message left \vlabel{uncertain} is a false alarm. Coverage (the share of decided verdicts) is not reported separately; the conservative rule folds every \vlabel{uncertain} verdict into recall and FPR instead. An earlier evaluation gave half credit to \vlabel{uncertain} and is superseded [S3]. Project eval sets were reused during development, and India v2 was aggregate-only adaptive validation. We therefore report both the v3 held-back split (n = 81) and the independently authored sealed holdout (n = 184) in full in Section 6.1; `fp_val_v1` was written blind by an author with no access to the code [S6, S8, S11].


## Optimization on Arm

Prahari targets an interactive response of about 1–2 s and a bounded memory footprint on CPU-only Arm SoCs. Measured against that target, a warm KYC check on the Galaxy S23 took 1.20 s on the first build and 1.857 s on the final build, but 2.611 s in the hotter gated pass, and the six-item p90 reached 3.977–5.252 s (Section 5.1). On Neoverse-V2 at 8 threads, warm items took 0.534 s and the all-item mean, which includes the cold first item, 0.980 s (Section 5.2). Five engineering choices shape these numbers; each is listed with its measured effect.

**Detector-first cascade.** Classical classifiers and mechanism rules make the decision, and Llama 3.2 1B only explains the evidence the detectors produced. The detectors run in 0.42 ms/item on Arm Linux and in 5–17 ms warm for text checks on the Galaxy S23 (183 ms for the lookalike-URL check, 255 ms for the cold first check) [S2, S9]. The verdict stays the detector's even if generation is skipped or fails, so the language model never sits on the classification path.

**Low-bit weight quantization.** Prahari deploys the official ExecuTorch Llama 3.2 1B Instruct QLoRA INT4 export: group-32 symmetric INT4 weights with 8-bit dynamic per-channel activations, in a ~1.18 GB `.pte` file. On the Neoverse-N1 baseline it reached ~83.1 tok/s prefill (processing the prompt) and 19.9 tok/s decode (generating output tokens), against ~58–63 tok/s and 12–13.5 tok/s for the SpinQuant export under mixed host load, so QLoRA INT4 was kept [S2, S4].

**KleidiAI micro-kernels through ExecuTorch XNNPACK.** On CPUs with `asimddp` and `i8mm` (both the Snapdragon 8 Gen 2 and Neoverse-V2 report them), XNNPACK can route quantized matrix multiplications to Arm KleidiAI kernels. On Neoverse-V2, `perf` attributes 54.17% of whole-process CPU samples to `kai_*` kernels (Section 5.3) [S10].

**Compact prompt and bounded greedy decoding.** The prompt carries the verdict directive, a compressed evidence phrase and at most 320 characters of the input with links defanged. Decoding is greedy (temperature = 0) with a 40-token cap; the six demo items used 109–128 prompt tokens (median 123) and generated 25–39 tokens (median 28). Short prompts and outputs cut both prefill compute and KV-cache traffic without touching the weights [S7].

**Portable detector export for Android.** The Android Python runtime only offers scikit-learn 1.3.2, while training uses 1.9.1. Instead of shipping incompatible pickles, the build exports all four trained models as plain JSON/NumPy parameters and checks them against reference probabilities and labels on every build. This removes cross-version unpickling and keeps warm on-phone detector latency at 5–17 ms [S7, S9].

## Hardware Utilization and Performance

We measured Prahari on three Arm targets with separate workloads and measurement boundaries: a Samsung Galaxy S23 phone, an Armv9 Neoverse-V2 Linux server (8 vCPUs) and a 2-vCPU Neoverse-N1 evaluation VM [S8, S9, S10]. Figure 3 summarises all three.

### Galaxy S23 phone

The phone is a Samsung Galaxy S23 (SM-S911B, Snapdragon 8 Gen 2 / SM8550, Android 14, `arm64-v8a`; CPU flags include `asimddp`, `i8mm` and `bf16`). The APK used ExecuTorch Android with XNNPACK, declared no `INTERNET` permission, and the model and tokenizer matched their pinned hashes on the device. Table 4 gives the final measured build, run in two passes over six built-in samples: first with Llama on every item, then with flagged-only gating [S17].

\needspace{11\baselineskip}

| Check (final build) | TTFT | Decode | Total |
|:----------------------------------------------|----------:|----------:|---------------:|
| Warm KYC scam SMS, all-items pass (median, n = 2) | 879 ms | 32.5 tok/s | 1.857 s |
| Warm KYC scam SMS, gated pass (median, n = 2) | 1,275 ms | 23.9 tok/s | 2.611 s |
| Six-item median / p90, all-items pass | — | — | 1.984 / 3.977 s |
| Six-item median / p90, gated pass | — | — | 2.611 / 5.252 s |
| Bill / official link, gated (Llama skipped) | — | — | 0.186 / 0.312 s |
| Lookalike link (detector-text fallback) | — | — | 5.001 / 6.399 s |

Table: Galaxy S23 app telemetry, final build, warm checks. TTFT is time to first token; prefill was 165.0 tok/s (all-items) and 113.8 tok/s (gated). "—": not reported for these rows. The detector stage is not shown: warm text detectors took 5–17 ms on the earlier build.

The first on-phone run (23 November) was faster: 6 ms detector, 510 ms TTFT, 43.4 tok/s decode and 1.20 s per warm KYC check, and 1.42 s for the same check in Airplane Mode; an intermediate build measured 2.90 s and ~22 tok/s. The latest run warmed from 41.7 °C to 45.1 °C. The gated pass always ran second and hotter, so its slower KYC times may be thermal, but the cause was not tested; they do not measure the effect of gating, and throttling itself was not measured. Two warm checks per pass and a p90 over six items are small samples. For the lookalike link, Llama ran but no reply passed validation, so the app showed the detector's fixed text, labelled as not AI-written [S9, S14, S16, S17].

### Neoverse-V2 and Neoverse-N1

Table 5 shows thread scaling on Neoverse-V2 (Debian 12, 8 vCPUs, 15 GiB RAM, ExecuTorch 1.6.0). Each setting ran three processes × six items; values are means of the three run means [S10]. The 2-vCPU Neoverse-N1 evaluation baseline, on a 28-item suite, reached 83.1 tok/s prefill, 19.9 tok/s decode and 3.84 s per item [S2, S8].

\needspace{9\baselineskip}

| Neoverse-V2 threads | TTFT | Prefill | Decode | Item wall |
|:------------------------|-----------:|-------------:|-------------:|----------:|
| 1 | 1,465.5 ms | 109.26 tok/s | 25.69 tok/s | 2.792 s |
| 2 | 922.0 ms | 210.58 tok/s | 46.69 tok/s | 1.728 s |
| 4 | 907.7 ms | 378.79 tok/s | 75.89 tok/s | 1.470 s |
| 8 | 526.8 ms | 676.80 tok/s | 104.58 tok/s | 0.980 s |
| 8, warm items only | 159.3 ms | 751.17 tok/s | 104.31 tok/s | 0.534 s |

Table: Llama 3.2 1B INT4 on Neoverse-V2 (means over 3 runs × 6 items; the first item of each run is cold). The 4-thread TTFT varied widely (± 373.0 ms).

Going from 1 to 8 threads raised decode 4.07× and prefill 6.19× on Neoverse-V2, bringing mean per-item turnaround below 1 s. At 2 threads, V2 delivered 2.57× the prefill and 2.33× the decode of the 2-vCPU N1 VM. The two machines ran under different conditions, so this ratio is descriptive and does not separate `i8mm`/KleidiAI from core design or memory bandwidth [S10].

![Arm performance. (A) Neoverse-V2 ExecuTorch thread scaling (1–8 threads, mean ± SD over 3 runs × 6 items). (B) Llama 3.2 1B INT4 decode throughput and item wall latency on the three Arm targets, including the first, intermediate and final Galaxy S23 builds measured on separate workloads, so the bars are descriptive rather than a controlled comparison.](img/fig-arm-perf.png){#fig:arm-perf width=82%}

### Arm kernel evidence

The KleidiAI kernels are present in the ExecuTorch XNNPACK build (517 `kai_` symbols) [S5], and Prahari's INT4 matrix multiplications are observed executing in them on Neoverse-V2. A whole-process `perf` profile of one 2-thread run, covering startup, model load and six inferences (~2,222 samples, 0 lost), put 54.17% of sampled CPU time in `kai_*` kernels: 23.27% in the `i8mm` prefill matmul, 20.57% in the `dotprod` decode matmul and 10.33% in packing and helper kernels [S10]. This is a CPU-time share, not a fraction of inference wall time. No supported runtime switch was found to disable KleidiAI, so an on/off speedup was not measured. Dispatch to these kernels on the phone has not been shown directly.

### Memory

On the Galaxy S23, `dumpsys meminfo` after a KYC check reported 1,704 MiB total PSS (proportional set size, which splits shared pages among processes) and 1,824 MiB RSS (resident set size), of which native heap (model weights, XNNPACK workspace and KV cache) was 1,529 MiB, 89.8% of PSS. Peak sampled memory in the latest run was 1,795.3 MiB PSS / 1,907.9 MiB RSS. On disk, the APK plus model and tokenizer take 1.147 GiB. Runner RSS on Neoverse-V2 was 2,392.1 MiB after generation, and the N1 VM peaked at 2.05 GB of cgroup memory. This footprint leaves little headroom on 4–6 GB phones, and the eight checks of the first phone session are too few to show long-run stability [S2, S9, S10, S13, S17]. Figure 4 breaks down the phone's PSS by component.

![Galaxy S23 memory. `dumpsys meminfo` PSS breakdown after a KYC check; the native heap (Llama 3.2 1B weights, ExecuTorch XNNPACK workspace and KV cache) is 89.8% of 1.66 GiB total PSS.](img/fig-memory.png){#fig:memory width=72%}


## Results

### Detection performance

Table 6 reports the detector on every benchmark we hold. Conservative metrics count an \vlabel{uncertain} verdict as an error on both classes (Section 3.5), and both independent holdouts are reported, including the weaker one [S8, S11]. The project sets have been used repeatedly during development and are optimistic; the last four rows were kept out of tuning to different degrees.

\needspace{12\baselineskip}

| Set | n | Recall | FPR | F1 |
|:----------------------------------------|------:|-------:|-------:|-------:|
| Project SMS (dev) | 1,162 | — | — | 0.925 |
| Project URL (dev) | 7,997 | 0.988 | 0.000 | 0.994 |
| Project Indic (dev) | 320 | — | 0.031 | 0.969 |
| NSL-KDD flow replay (`KDDTest+`) | 22,544 | 0.757 | 0.030 | 0.850 |
| India v3 held-back split | 81 | 0.941 | 0.000 | 0.970 |
| Blind validation set (150 genuine, 90 scam) | 240 | 1.000 | 0.107 | 0.918 |
| India v4 held-back split | 79 | 0.969 | 0.298 | 0.805 |
| Sealed final holdout | 184 | 0.929 | 0.300 | 0.812 |

Table: Detection results with conservative scoring. Dashes mark values not recorded for that set.

The holdouts differ mainly in how often genuine messages raise false alarms. A contact gate, which lets a text-model score flag a message only when the reader is given something to act on (a non-official link, number or chat handle, a request, a payment order or a threat), removed every false alarm on the v3 split (FPR 0.128 → 0.000) and cut the blind validation set from 0.207 to 0.107 with recall unchanged. On the v4 split, which the fixing work never saw, false alarms remain on advisories, bank and OTP alerts, delivery notices and links to small-business sites. The sealed holdout is harder still: every link in it uses a `.example` placeholder, which the gate treats as a contact and the domain rules call risky, so 28 of 87 genuine SMS (FPR 0.322) are still flagged, mostly advisories carrying such a link, family chats warning about scams, and doorstep or self-check messages [S8, S12]. The sealed set has been scored at several checkpoints and is no longer a single-shot test.

Table 7 shows how the sealed-holdout numbers moved as components were added. The set holds 84 malicious and 100 benign messages across an SMS route and a prompt-injection route; injection-route FPR stayed at 0.154 (2 of 13) after the rules-and-text-model freeze [S8, S11, S15].

\needspace{8\baselineskip}

| Configuration | Recall | FPR | F1 |
|:------------------------------------------------|-------:|-------:|-------:|
| Initial baseline | 0.738 | 0.290 | 0.709 |
| Rules + text model freeze | 0.917 | 0.310 | 0.802 |
| After further recall tuning | 0.929 | 0.370 | 0.784 |
| Current detector (contact gate, negation handling) | 0.929 | 0.300 | 0.812 |

Table: Sealed final holdout (n = 184) at successive detector configurations.

Figure 5 plots conservative F1 and FPR for every benchmark in Table 6, so the gap between the development sets and the independent holdouts is visible at once.

![Detection performance. Conservative F1 and FPR for each benchmark in Table 6; the independent holdouts on the right carry most of the remaining false alarms.](img/fig-eval-summary.png){#fig:eval width=80%}

### Explanation quality

We audited generated explanations blind, rating each as correct, weak or wrong (Table 8). The initial audit of 20 sealed-holdout explanations found 7 wrong, including 4 false claims about the input; it used a different judge and item set from the later rows, so it is not directly comparable. Fixes for false "no link/payment" claims, repeated openings and stray generated questions followed. Three later audits of 20 fresh, never-tuned items each were scored by one AI model judge with A/B shuffling and a fixed rubric. They did not reduce wrong explanations: most remaining errors repeat a wrong detector evidence phrase [S8, S11, S12].

\needspace{10\baselineskip}

| Audit (20 items each) | Correct | Weak | Wrong |
|:------------------------------------------------|--------:|--------:|--------:|
| Initial blind audit (different judge and items) | 5 | 8 | 7 |
| Fresh-item audit 1, model judge | 8 | 7 | 5 |
| Fresh-item audit 2, model judge | 11 | 4 | 5 |
| Fresh-item audit 3, model judge | 10 | 5 | 5 |
| Audit 3 items, later build, before wording fix | 8 | 2 | 10 |
| Audit 3 items, later build, after wording fix | 9 | 4 | 7 |

Table: Blind explanation audits of English explanations. The last two rows regenerate the audit 3 items on a later detector build and re-judge them with the same model judge. No human audit was done on the fresh items.

The last two rows need care. Regenerated on the later build, the audit 3 items scored 8/2/10, worse than the 10/5/5 of audit 3 itself; the explanations were regenerated on that build and judged again, so the two results are not directly comparable. A wording fix then moved them to 9/4/7 (false input claims 9 → 6), but that gain came from `.example`-domain wording that real SMS never contain, so it overstates real-world improvement [S15]. Hindi accessibility scores, from the same model judge, rose from 3.5–4.5 to 5.45–6.4 out of 10 once the fixed-text Hindi summary was added. The latest explanation behaviour has no fresh independent human audit.

### Verification

A regression suite of 1,355 detector and LLM-safety tests passes on the current detector, including 39 tests for the live monitor and about 120 Call Guard call-script cases, with Android parity and manifest-permission checks in CI [S11, S12]. The rootless Linux connection monitor classified a 150-port loopback scan as \vlabel{DANGEROUS}, a quiet window as benign, and a closed-port scan as \vlabel{SUSPICIOUS} from kernel counter jumps [S11]. The Call Guard prototype is covered by those call-script cases. The newer Android features (OTP masking, official-channel verdicts, offline-only voice, opt-in history, font scale 2.0) were checked on an Android 14 x86_64 emulator, not a physical phone, so they carry no Arm timings [S12].


## Responsible AI, Limitations and Future Work

### Responsible AI and privacy

Prahari is private by construction. The Android APK requests no `INTERNET` permission, sets `allowBackup="false"`, sends no telemetry and runs every model on the phone, so messages, OTPs and bank alerts are not sent anywhere unless the user chooses to share a warning or copy a report; history is off by default and redacted when enabled. The design is advisory: vetted English and Hindi steps and the official reporting channels (Sanchar Saathi Chakshu, the 1930 helpline and cybercrime.gov.in) always appear above the AI card, which warns that it "can be wrong", and a benign result reads "\vlabel{NO RISK FOUND} — still verify", never "safe". The entrant used AI-assisted tools for mockups, Hindi copy review, coding and code review, and checked every architecture choice, measurement and safety text personally [S7].

### Limitations

- **False alarms on genuine notices.** The sealed-holdout false-positive rate on genuine SMS remains high (0.300 overall, Table 6), mostly on advisories and family warnings, so automatic background SMS scanning stays disabled until it falls well below that level on unseen data.
- **Phone performance is not yet stable.** Latency and throughput on the Galaxy S23 differed between builds and runs (Table 4); no run started from a cool phone, samples are small, and the cause of the differences is not established. KleidiAI kernels were observed executing, but no on/off speedup was measured.
- **Memory headroom.** Peak memory of about 1.7–1.9 GiB (Section 5.4) leaves little room on 4–6 GB phones; a mid-range phone has not been tested.
- **Hybrid scams and explanation quality.** A few adversarial scams that mix an official app with an unofficial link still pass the rules, the blind audits still rate some English explanations wrong, the AI prose is English only (the Hindi summary is fixed text), and several app features (report card, remote-app banner, sender check, APK-link warning) were checked only on the emulator. TalkBack is untested.
- **Network scope.** The live connection monitor is Linux-only, samples sockets rather than capturing packets, and is separate from the NSL-KDD replay classifier; Call Guard has no Android entry point yet.

### Future work

- **Wider, safer coverage:** a pause-and-explain link interstitial (opt-in default link handler), screenshot OCR, opt-in notification-listener scanning once false alarms are low enough, Call Guard on the phone with a Hindi-capable speech model, and a voice-clone check for shared voice notes.
- **Fresher threat knowledge offline:** a periodically refreshed local snapshot of a phishing feed such as OpenPhish or PhishTank (within licence terms), signed offline rule-pack updates, and an inspector that checks a downloaded `.apk` for remote-access and SMS-reading permissions before install.
- **Faster, leaner Arm execution:** SME2 on newer Arm CPUs, phone NPUs and Hailo accelerators on Arm Linux boards; a smaller KV cache (2048 → 512 context) targeting under 1.35 GB PSS; and a cool-start S23 re-measurement with longer samples to separate thermal throttling from build differences.
- **More languages and real users:** Marathi, Tamil, Telugu and Bengali with consented, licensed data and a fresh single-shot holdout, bank "freeze card/UPI" deep links where banks expose them, and comprehension tests with non-technical and elderly users (200% font, TalkBack).

## Conclusion

Prahari shows that useful scam triage can run entirely on an Arm phone. Its three main contributions are a hybrid pipeline in which deterministic detectors and Indian-context rules decide and Llama 3.2 1B only explains; an offline deployment on a Samsung Galaxy S23 phone and Arm Linux through ExecuTorch XNNPACK, with execution observed inside Arm KleidiAI kernels; and an evaluation that reports every holdout, including the weak ones.

On the phone, a warm KYC check takes a median 1.857 s with no network permission, and on Neoverse-V2 the 8-thread runner averages 0.980 s per item with 54.17% of sampled CPU time in KleidiAI kernels. The detector reaches F1 0.970 with no false alarms on the v3 held-back split. The open limits are equally concrete: an FPR of 0.300 on the sealed holdout, small and thermally uncontrolled phone samples, no measured KleidiAI on/off speedup, about 1.7–1.9 GiB of memory, and English explanations of which the blind audits still rate 5 to 7 in 20 wrong. Section 7 lists the planned next steps for each.

## References {.unnumbered}

External sources are listed by the key used in the text. Keys [S1]–[S18] refer to project evidence and are listed in Appendix A.

\RefsBegin

**[A1]** GSMA. *Airtel spam detection solution* (GSMA scams study). <https://www.gsma.com/solutions-and-impact/technologies/security/scams/gsma_study/airtel-spam-detection-solution/>

**[B1]** Bitdefender. *Scam Protection / Scamio* (India). <https://www.bitdefender.com/en-in/consumer/scam-protection>

**[D1]** Department of Telecommunications. *Sanchar Saathi — Chakshu (report suspected fraud communication)*. <https://sancharsaathi.gov.in/sfc/>

**[D2]** Telecom Regulatory Authority of India. *Direction of 19 November 2025* (DLT headers and 1600-series numbers for BFSI calls). <https://www.trai.gov.in/sites/default/files/2025-11/Direction_19112025.pdf>

**[DS1]** Almeida, T. A., et al. (2011). *SMS Spam Collection*. UCI Machine Learning Repository, CC BY 4.0. <https://archive.ics.uci.edu/dataset/228/sms+spam+collection>

**[DS2]** Mishra, S., and Soni, D. (2022). *SMS Phishing Dataset*. Mendeley Data, CC BY 4.0. <https://data.mendeley.com/datasets/f45bkkt8pr>

**[DS3]** Prasad, A., and Chandra, S. (2024). *PhiUSIIL Phishing URL Dataset*. UCI Machine Learning Repository, CC BY 4.0. <https://archive.ics.uci.edu/dataset/967>

**[DS4]** Tavallaee, M., et al. (2009). *NSL-KDD dataset*. Canadian Institute for Cybersecurity, University of New Brunswick; redistribution permitted with citation. <https://www.unb.ca/cic/datasets/nsl.html>

**[DS5]** Indian seed datasets: karanverma19, *Indian Multilingual Scam Message Dataset* (Apache-2.0), <https://huggingface.co/datasets/karanverma19/Indian_Multilingual_Scam_Message_Dataset>; bolewara, *Hinglish scam text dataset* (CC BY 4.0), <https://huggingface.co/datasets/bolewara/hinglish-scam-text-dataset>

**[G1]** Google. *New Android scam protections* (Google blog). <https://blog.google/security/new-android-scam-protections/>

**[G2]** Google. *Staying one step ahead: strengthening Android's lead in scam protection* (Google blog). <https://blog.google/security/staying-one-step-ahead-strengthening-androids-lead-in-scam-protection/>

**[G3]** Techzei. *Google Messages enhanced scam detection and India availability*. <https://techzei.com/google-messages-enhanced-scam-detection-india/>

**[L1]** Meta. *Llama 3.2 Community License* <https://www.llama.com/llama3_2/license/> and *Acceptable Use Policy* <https://www.llama.com/llama3_2/use-policy/>. Weights are obtained separately by users; Prahari's own code is MIT-licensed, and framework licences (ExecuTorch/PyTorch/scikit-learn BSD-3-Clause, Arm KleidiAI Apache-2.0, Chaquopy MIT) apply to their components.

**[M1]** McAfee. *Scam Detector*. <https://www.mcafee.com/en-us/scam-detector/>

**[N1]** Norton. *AI scam protection (Norton Genie)*. <https://in.norton.com/feature/ai-scam-protection>

**[P1]** Press Information Bureau, Government of India (2024). Ministry of Home Affairs advisory on fake "digital arrest" and courier impersonation. <https://www.pib.gov.in/PressReleasePage.aspx?PRID=2077948>

**[P2]** Press Information Bureau, Government of India (2026). I4C financial-fraud complaint figures, 2021–2025. <https://www.pib.gov.in/PressReleasePage.aspx?PRID=2287039>

**[R1]** Saavalainen (2026). *On-Device Phishing Explanation Generation Using Small Language Models*. Thesis, University of Helsinki. <http://hdl.handle.net/10138/638168>

**[R2]** ElZemity, et al. (2026). *Agentic Knowledge Distillation: Autonomous Training of Small Language Models for SMS Threat Detection*. arXiv:2602.10869. <https://arxiv.org/abs/2602.10869>

**[SM1]** Neoteo. *Samsung names Japan, Canada and India for Scam Detection*. <https://www.neoteo.com/en/samsung-names-japan-canada-and-india-for-scam-detection>

**[SM2]** C&K Lab. *Galaxy spam/smishing block settings*. <https://candklab.com/en/blog/galaxy-spam-smishing-block-settings/>

**[T1]** Truecaller. *Fraud Protection* press release. <https://corporate.truecaller.com/newsroom/press-release/28923657E2813595>

**[T2]** Truecaller. *Protect yourself from SMS scams with Truecaller's fraud protection* (blog). <https://www.truecaller.com/blog/features/protect-yourself-from-sms-scams-with-truecallers-fraud>

**[T3]** Truecaller. *Premium Terms of Service*. <https://www.truecaller.com/premium-terms-of-service>

\RefsEnd

## Appendix A: Artifact and Provenance Index {.unnumbered}

Each key names the project evidence behind a claim in the text. All paths are relative to the repository root.

\RefsBegin

**[S1]** Official Bharat AI-SoC Challenge 2026–27 brief, PS3 (\path{docs/challenge-brief.md}), and IIT Delhi PS3 mentoring guidance.

**[S2]** Detector, rules and app server: \path{candidates/BEST/} (\path{REPORT.md}, \path{DATA.md}, \path{app/server.py}, \path{triage/*.py}).

**[S3]** Historical baseline evaluation with half credit for uncertain verdicts, superseded by conservative scoring: \path{research/evals/20261111-075405-best-confirm/}.

**[S4]** Research log, leave-one-category-out check and data preparation: \path{research/LOG.md}, \path{research/REPORT.md}, \path{research/stress/loco.py}, \path{eval/prep_data.py}.

**[S5]** ExecuTorch 1.6.0 XNNPACK `kai_` symbol inspection on Arm Linux (517 symbols): \path{docs/phase1/EVIDENCE.md}.

**[S6]** Dataset sources, attributions and licences: \path{candidates/BEST/DATA.md}.

**[S7]** Android app (\path{android/}), CI manifest and permission audits (\path{.github/workflows/android.yml}), emulator screenshots (\path{docs/phase1/EVIDENCE.md}).

**[S8]** Neoverse-N1 evaluations, sealed-holdout scores (\path{docs/phase1/evidence/sealed-holdout/scores.json}) and the 20-item blind explanation audit (\path{docs/phase1/EVIDENCE.md}).

**[S9]** Galaxy S23 first device run (23 Nov 2026): device properties, hash checks, timed checks in Airplane Mode, `dumpsys meminfo` (\path{docs/phase1/evidence/galaxy-s23/}, \path{docs/phase1/img/s23-*.png}).

**[S10]** Neoverse-V2 benchmark (23 Nov 2026): `perf` KleidiAI profile, thread scaling and `unshare -n` offline proof (\path{docs/phase1/evidence/neoverse-v2/}).

**[S11]** Live Linux connection monitor, explanation honesty fixes, India v3 held-back set and Android UX update (merged 23 Nov 2026).

**[S12]** SMS false-alarm fix, Call Guard preview, grounded explanations and Hindi summary, v4 held-back set, UPI QR checker, Android app update and emulator captures (merged 24 Nov 2026; \path{research/fpfix/}, \path{docs/call-guard.md}, \path{research/explain-audit.md}, \path{research/v4-heldout/RESULTS.md}, \path{research/app-r3-verify/}).

**[S13]** Performance methodology, optimisations and harness: \path{docs/perf/}, \path{docs/perf/evidence/}, \path{bench/perf/} (16 harness tests).

**[S14]** Galaxy S23 final run (24 Nov 2026): \path{docs/perf/s23-final-20261124.md}, \path{evidence/galaxy-s23-20261124/} (per-check results, memory, battery, hashes, demo clips).

**[S15]** Validation gate (\path{bin/validate}, \path{docs/validation-gate.md}), including the explanation re-judgement; report card (\path{android/python/report_card.py}), remote-access app banner (\path{RemoteApps.kt}) and APK-link check (\path{docs/typosquat.md}).

**[S16]** Sender check (\path{docs/sender-check.md}, \path{candidates/BEST/triage/sender.py}) and lookalike-link stats (\path{evidence/galaxy-s23-20261124/}).

**[S17]** Galaxy S23 gating run on the release APK: \path{docs/perf/s23-gating-20261124.md}, \path{docs/perf/evidence/galaxy-s23-gating-20261124/retry/}.

**[S18]** Emulator feature check (\path{evidence/android-emulator-20261125/summary.md}) and two failed S23 sessions on 25 Nov (\path{evidence/galaxy-s23-20261125/}); same APK as [S17].

\RefsEnd

\needspace{12\baselineskip}

| Item | Value |
|:----------------------|:--------------------------------------------------------------|
| Repository | <https://github.com/rabesss/prahari> |
| Android APK | GitHub release `phase1-apk-5b59ee2`, SHA-256 `88f6a532…` |
| Model files (SHA-256) | Llama 3.2 1B QLoRA INT4 `.pte` `ab7b7ebf…`; `tokenizer.model` `82e9d319…` |
| CLI demo | `candidates/BEST/bin/app --demo --out .venv/demo.json` (8 items: SMS, URL, UPI, flow, injection) |
| Validation gate | `bin/validate`; add `--baseline BEFORE.json` to fail on any recall drop or FPR rise; sealed set only with `--sealed` |
| Model licence | Llama 3.2 weights fetched separately under Meta's Community License [L1] |

Table: Reproducibility card.
