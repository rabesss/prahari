"""A safe pattern that also fires on plain text clears messages it was never written for: a stray
'|' in an alternation once let the OTP pattern match the empty string, which cleared every
message that had no harmful mechanism, scams included."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from triage import mech  # noqa: E402

PLAIN = ["hello", "the quick brown fox jumps over the lazy dog", "ok thanks, see you then"]
CONTENT_SAFE = ("otp_notification", "transaction_receipt", "protective", "awareness", "consumer_advice",
                "collect_review", "opt_out", "bill_notice", "appointment_notice")


def test_safe_patterns_need_their_content():
    patterns = dict(mech.SAFE)
    for name in CONTENT_SAFE:
        for text in PLAIN:
            assert not mech._any(patterns[name], text), f"{name} matches plain text: {text!r}"
