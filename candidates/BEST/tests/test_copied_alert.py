"""A copied debit alert that sends the reader to a lookalike domain is never NO RISK (seen on the app)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from triage import detect  # noqa: E402


def label(text):
    return detect.predict_text([text])[0][0]


def test_copied_alert_with_lookalike_link_is_suspicious():
    assert label("Rs.2,450.00 debited from A/c XX4821. Not you? Visit sbi-refund-help.dev to cancel.") != 0
    assert label("Rs 5,000 debited from your HDFC account. If not done by you, cancel at hdfc-reversal.top") != 0


def test_genuine_alerts_naming_the_bank_stay_clear():
    assert label("Rs.2,450.00 debited from A/c XX4821 on 23-Nov to UPI SWIGGY. Not you? Call 1800-1234 or "
                 "block in the SBI app. -SBI") == 0
    assert label("Your HDFC Bank A/c XX1234 debited Rs 500. Not you? Visit hdfcbank.com or call 1800-202-6161") == 0


def test_protective_wording_does_not_clear_a_lookalike_link():
    # CodeRabbit on #54: "Never share OTP" made the protective branch clear it first.
    assert label("Rs 500 debited. Never share OTP. Pay Rs 10 in the SBI app. Not you? Visit "
                 "sbi-refund-help.dev to cancel.") != 0
