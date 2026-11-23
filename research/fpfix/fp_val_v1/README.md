# Independent Indian message validation set v1

Authored by an OpenAI Codex research sub-agent on 23 November 2026 for this project. All messages are original synthetic text, independently written using public format and safety guidance; no real person's message or personal information was copied. No repository datasets or detector code were consulted. The author releases this original synthetic dataset as CC0 1.0 for this project (https://creativecommons.org/publicdomain/zero/1.0/).

The 150 legitimate items cover transactional alerts, authentication and doorstep delivery codes, UPI activity, reminders, public advisories, offers and ordinary chats. The 90 scams contain an explicit harmful request; a warning describing an unsafe request is not itself a scam. `hard` is a subjective annotation for messages that resemble the opposite class or contain competing safety cues, rather than a measured detector outcome. `why` records the class rationale. The identifiers, codes, names, references and masked account endings are invented. Numeric mobile examples and lookalike domains are fabricated, not checked against live allocations; do not call or visit them. Sender headers are illustrative and do not establish provenance or a real sender's template. The delivery handover code is distinct from a banking or login OTP and should be shared only with the delivery agent at physical handover. The corpus is a synthetic stress test, not a representative sample of Indian traffic or a measure of real-world prevalence.

## Counts

| Label | Category | en | hi | hinglish | Total |
|---:|---|---:|---:|---:|---:|
| 0 | bank_alert | 7 | 4 | 4 | 15 |
| 0 | delivery_otp | 6 | 3 | 3 | 12 |
| 0 | fraud_advisory | 6 | 3 | 3 | 12 |
| 0 | govt_notice | 6 | 3 | 3 | 12 |
| 0 | kyc_reminder | 6 | 3 | 3 | 12 |
| 0 | loan_emi | 6 | 3 | 3 | 12 |
| 0 | otp | 6 | 3 | 3 | 12 |
| 0 | personal_chat | 7 | 4 | 4 | 15 |
| 0 | promo | 6 | 3 | 3 | 12 |
| 0 | telecom | 6 | 3 | 3 | 12 |
| 0 | upi_txn | 6 | 3 | 3 | 12 |
| 0 | utility_bill | 6 | 3 | 3 | 12 |
| 1 | digital_arrest | 3 | 2 | 1 | 6 |
| 1 | electricity_disconnect | 3 | 2 | 1 | 6 |
| 1 | fake_kyc | 6 | 3 | 3 | 12 |
| 1 | fake_refund | 3 | 1 | 2 | 6 |
| 1 | family_impersonation | 3 | 1 | 2 | 6 |
| 1 | investment | 3 | 1 | 2 | 6 |
| 1 | job_task | 3 | 2 | 1 | 6 |
| 1 | loan_app | 3 | 2 | 1 | 6 |
| 1 | lottery_prize | 3 | 1 | 2 | 6 |
| 1 | otp_share_request | 3 | 1 | 2 | 6 |
| 1 | parcel_customs | 3 | 2 | 1 | 6 |
| 1 | reward_points | 3 | 1 | 2 | 6 |
| 1 | spoofed_advisory | 3 | 1 | 2 | 6 |
| 1 | upi_collect | 3 | 2 | 1 | 6 |

## Public sources consulted

- RBI, Consumer Awareness – Cyber Threats and Frauds: https://rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=53185 (OTP, KYC, remote access, collect requests).
- NPCI, Fraud Awareness: https://www.npci.org.in/fraud-awareness (payment PIN, fake cashback, remote access).
- UIDAI, Aadhaar usage dos and don'ts: https://uidai.gov.in/images/Aadhaar_Usage-Dos_and_Donts_180324.pdf (Aadhaar OTP handling; search excerpt consulted).
- SMS Alert, TRAI header suffix overview: https://kb.smsalert.co.in/knowledgebase/trai-mandates-header-suffixes-for-sms-new-rules-effective-from-may-6-2025/ (illustrative -S, -T, -P and -G suffixes; search excerpt consulted).

Sources inform formats and safety distinctions, not the fictional transactions or endorsement of these exact texts. Labels describe only the content in each example, not the authenticity of a sender or live destination. `check.py` validates structural counts and computes token Jaccard similarity; the similarity test is a heuristic and cannot establish semantic independence. SHA-256 is recorded in `fp_val_v1.sha256`.
