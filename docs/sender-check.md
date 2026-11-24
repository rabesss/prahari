# Sender check (optional, warn-only)

Prahari can take the SMS sender as an optional second input. A personal mobile number can only raise a result. A registered-looking sender ID never makes a message look safer.

## Rule
- **Input.** On Android, the check screen has an optional **Sender** field in message mode, empty by default. Shared text arrives without a sender. In Python, the item contract has an optional `sender` field (`bin/predict --task sms`, `bin/explain`, `/api/triage`). The default is `None`, and every existing eval set has no sender.
- **Parsing** (`candidates/BEST/triage/sender.py`):
  - A 10-digit Indian mobile number (`9876543210`, `+91 98765 43210`, `09876543210`) is a **personal mobile number**.
  - `AX-HDFCBK-S` style headers are **registered-looking sender IDs**. The format is an optional 2-letter prefix, 6 characters, and an optional `-S`/`-T`/`-P`/`-G` category suffix. A bare 6-letter ID like `HDFCBK` counts too.
  - `1600xxxxxx` is the **1600 series**. Anything else is **other**.
- **Raise.** A text message from a personal mobile number is raised to at least **SUSPICIOUS** when it does one of these:
  - it reads like a debit or OTP alert;
  - it asks for an OTP, PIN or KYC details;
  - it claims a bank, government, courier or telecom identity to the reader (a "Dear customer" greeting, or "your account / card / parcel / SIM / connection ...").

  The first evidence line is then the vetted sentence *"Banks and government send SMS from registered sender IDs like XX-ABCDEF, not personal mobile numbers"* (Hindi: *"बैंक और सरकारी विभाग SMS रजिस्टर्ड सेंडर ID (जैसे XX-ABCDEF) से भेजते हैं, निजी मोबाइल नंबर से नहीं"*). A DANGEROUS verdict stays DANGEROUS.
- **No raise.** These are left as they are:
  - chats that only mention a bank ("I paid the bank EMI");
  - forwarded warnings with no ask ("SBI never asks for your OTP");
  - ordinary payment requests between people ("send 500 for dinner").
- **Never lowers risk.** A sender ID, a 1600 number or any other sender returns the detector's result unchanged and adds no wording. Headers can be spoofed in a forwarded message or a screenshot, and the reader types the sender by hand. The check screen says so: *"A sender ID never proves a message is real."*
- **Calls.** Call Guard results for a transcript that mentions a bank get an `advisory` line (EN and HI). It says banks are moving service calls to 1600-series numbers in phases, so whatever the number, hang up and call the number on the card or in the bank app. The verdict is unchanged. The Android Call Guard preview is still behind its off-by-default flag, so the advisory exists only in the bridge JSON there.
- **Llama.** When the sender raised an item, the required opening carries a vetted sender phrase, and the model's one sentence is grounded in the vetted fact *"Banks and government send SMS from registered sender IDs, not personal mobile numbers."* The validator drops any generated sentence that vouches for the sender (for example "sent from a verified number") and puts the vetted fact in its place. The Hindi summary adds the fixed Hindi sentence above; it is not model text.

## Evidence
- **Invariant tests:** `candidates/BEST/tests/test_sender.py`.
  - Parser cases.
  - A seeded property test over the visible fixtures and stress suites (never a holdout) with header, mobile and junk senders. Adding a sender never lowers the label or the score. Only a personal mobile number changes anything. No added line carries safe or verified wording.
  - Raise and no-raise cases in English, Hindi and Hinglish.
  - CLI, web API and prompt paths.
  - Validator cases for sentences that vouch for the sender.
  - The Android bridge checks are in `android/tools/test_bridge.py`.
- **Holdout gate.** These sets have no sender, so the sender-less path must be byte-identical. The full detector output hash and the metrics at `origin/main` 89d4e97 and at this branch are identical on v3_test (81), v3_tune (159), fp_val_v1 (240), v4_tune (161) and the held-back v4_test (79). The sealed final holdout was not re-scored.
- **Device:** pending a Galaxy S23 re-test of the Sender field (layout at font scale 2.0, TalkBack, Hindi mode).

## Sources
- TRAI, Direction of 19 Nov 2025 on phase-wise mandatory adoption of 1600-series numbers by RBI, SEBI and PFRDA regulated entities. It also quotes TCCCPR 2018 regulation 3: commercial communication only through registered headers or the special number series. https://www.trai.gov.in/sites/default/files/2025-11/Direction_19112025.pdf
- TRAI SMS header lookup (to check who a header is registered to): https://smsheader.trai.gov.in
- Header category suffixes (-P/-S/-T/-G) rolled out by operators in July 2025 under TRAI's amended TCCCPR. Reported by Business Standard, 15 Jul 2025: https://www.business-standard.com/industry/news/telcos-roll-out-sms-headers-to-identify-messages-and-reduce-spam-125071501393_1.html
