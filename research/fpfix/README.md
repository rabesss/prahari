# SMS false-alarm fix (PR #48)

## Problem
PR #42 raised F1 on the 81-message v3 held-back split from 0.761 to 0.889, but on the sealed India
holdout the SMS false-alarm rate stayed near 0.38 to 0.40. The PS3 mentor asked that genuine bank and
OTP messages not be routinely flagged.

## Root cause
Breaking the false alarms down by category and by which rule fired showed two general failure modes:

1. **Model-only flags.** On Indian messages, when no harm rule fires, the Indic TF-IDF probability
   alone decides (gate 0.85). Genuine bank, OTP, UPI and notice SMS share vocabulary with scams. On
   independent dev data these flags were close to a coin flip (v4_tune: 12 true against 14 false).
   Nearly every true one carried a contact of its own (a mobile number, a chat handle or a lookalike
   link). The false ones carried none.
2. **Harm words inside warnings.** Advisories ("RBI never asks for your OTP, PIN or CVV"),
   hypotheticals ("if anyone calls asking for an OTP, hang up"), self-check alerts ("if not you, block
   the card in the app") and doorstep OTPs ("share only with the delivery agent at handover") tripped
   the credential, remote-access and block rules. The existing negation check only looks a few words
   back from the verb.

## Fix (candidates/BEST/triage/mech.py)
- **Contact gate (`_actionable`).** A text-model score alone flags a message only when the reader has
  something to act on. That means at least one of: a non-official contact anywhere (link, mobile
  number, chat handle, obfuscated or scheme-less link), a direct request, an un-negated order to
  share, send, pay or install, a payment order, or a threat in any word order.
- **Warning segments (`request_text`, `_warning_only`).** Clauses are split into segments. A segment
  counts as a warning when it is one of:
  - a negation over an OTP, PIN, payment, app or link;
  - a hypothetical caller;
  - a self-check about a transaction the reader did not make;
  - a doorstep handover (a delivery word plus an in-person marker).

  A segment that itself orders the reader (a verb with no negation within two words of it), or
  threatens them, or makes an exception ("except our executive") is never a warning. Harm is ignored
  only when all of these hold:
  - every harmful mechanism is a secret, app, QR, collect or block mechanism (never a payment,
    transfer, prize, job, investment or authority demand);
  - each of them sits in warning segments;
  - the message has no contact anywhere;
  - the remainder has no order, threat or request cue. Quoted fraudster demands stay flagged, as an
  earlier controller decision requires.

Tried and dropped: treating the reserved `.example` TLD as neutral. Real SMS never contain it, so the
change only moved synthetic benchmarks, and it broke pinned stress rows.

## Validation set (fp_val_v1/)
240 Indian SMS: 150 legitimate (bank, OTP, delivery OTP, UPI, KYC, EMI, utility, telecom,
government, advisory, promo, chat) and 90 scams, in English, Hindi and Hinglish. A Codex delegate
wrote them blind: it had no access to the repository or any dataset and worked from public RBI, NPCI,
UIDAI and TRAI format guidance. Released as CC0; see `fp_val_v1/README.md`.

Maximum token Jaccard against every other set:
- sealed holdout: 0.289
- dev sets v2, v3 and v4: 0.36 or less
- stress suites: one item at 0.56 (short generic wording)

An earlier draft set from the same thread was discarded because it near-duplicated sealed-holdout
items.

Limitation: 84 of the 90 scams carry a link or a mobile number, so this set barely exercises
contactless scams. Hand-written contactless cases from the reviewers live in
`candidates/BEST/tests/test_fp_fix.py` instead.

Use protocol: the set was scored once before any change was driven by it (FPR 0.093 at that
iteration). Later changes came from stress and safety tests and from review findings. After the
first scoring its false alarms were read but not tuned on.

## Results (uncertain counts as an error)
| Set | main FPR / recall / F1 | this PR FPR / recall / F1 |
|---|---|---|
| v3_test (tuning holdout, 81) | 0.128 / 0.941 / 0.889 | 0.000 / 0.941 / 0.970 |
| fp_val_v1 (new, 240) | 0.207 / 1.000 / 0.853 | 0.120 / 1.000 / 0.909 |
| v4_tune (161) | 0.215 / 0.926 / 0.834 | 0.151 / 0.926 / 0.869 |
| dev_v2 (96) | 0.000 / 1.000 / 1.000 | 0.000 / 1.000 / 1.000 |
| v3_tune (159) | 0.000 / 1.000 / 1.000 | 0.000 / 1.000 / 1.000 |

The sealed holdout result is in the PR description (scored once, after review).

Reproduce: `$HC_PY research/fpfix/score.py candidates/BEST NAME=PATH.jsonl ... [--errors]`.
