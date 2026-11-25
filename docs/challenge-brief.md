# Bharat AI-SoC Challenge 2026–27: summary of the PS3 brief

This is our own short summary of the official challenge page, written for this project. It is not a copy
of the page, and the page's own terms apply to its text. Always read the official page for the current
wording and dates:
https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html (summary checked 23 Oct 2026; dates re-checked 25 Nov 2026).

## The challenge

- Second edition of the Bharat AI-SoC Challenge, themed "Applied AI on SoC". MeitY runs it through the Chips
  to Startup (C2S) Programme with Arm, and IIT Delhi is the mentor institute.
- Students and working professionals or developers compete on equal terms in teams of one to three. There
  are five problem statements, and one winner per statement is chosen after a final live demo and jury Q&A.
- Two phases: **Phase 1, Open Qualifying** (report, source code and demo), then **Phase 2, Proof-of-Concept
  Development** for shortlisted teams.
- Dates on the page (re-checked 25 Nov 2026): registration closed 19 Oct 2026; Phase 1 due 25 Nov 2026 (an
  earlier snapshot said 23 Nov; the page gives no time of day, and the owner's Phase 1 form notes say 11:59 PM
  IST); shortlist mid-December 2026; Phase 2 due 5 Feb 2027; finals 15–16 Feb 2027.
- The page says the Phase 1 form and detailed submission guidelines were sent to each team leader's
  registered e-mail; those guidelines, not this summary, define the video and report format.

## PS3: on-device threat, phishing and scam detection

- **Goal:** an AI system on Arm edge hardware, with no cloud dependency, that detects cybersecurity
  threats: network intrusions, malware behaviour, phishing URLs, and scam SMS or other fraudulent messages.
- **It should also** explain threats to non-experts in plain language and recommend what to do, processing
  everything locally.
- **Hardware options:** Arm-based Android phones, Raspberry Pi 5 (CPU-only or with an AI HAT+), or other
  Arm-based Linux devices. If a Hailo accelerator is used, its pipeline must be documented separately from
  Llama on the CPU.
- **Required:** a Llama-family model for the advisory or reasoning component, deployed on the device with
  ExecuTorch as the reference runtime.
- **Optional datasets and tools named on the page:** CICIDS, UNSW-NB15 and NSL-KDD; PhishTank and OpenPhish
  feeds; the UCI SMS Spam Collection; libpcap and Scapy; the Hailo SDK.
- **Deliverables:** source code, the application, a demonstration video and a technical report.

How this project maps onto these requirements is in [`README.md`](../README.md) and
[`docs/phase1/report.md`](phase1/report.md).
