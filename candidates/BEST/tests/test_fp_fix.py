"""fp-fix: fewer false alarms on genuine Indian messages without clearing scams.

Two general rules (mech.py):
  * contact gate: a text-model score alone flags a message only when the reader is given something
    to act on (a contact of the sender's own anywhere, a direct request or a payment order);
  * warning segments: harm words that sit only in negated, hypothetical, self-check or doorstep
    clauses do not count when the message has no contact anywhere.
All messages here are hand-written for this test; none comes from a dev, validation or holdout set.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from triage import detect, mech  # noqa: E402


def verdict(text):
    return detect.predict_text([text])[0][0]


@pytest.mark.parametrize("text", [
    "HDFC Bank never asks for your OTP, PIN, CVV or card number. Report fraud on 1930.",
    "If anyone calls you asking for an OTP to stop a parcel, hang up and report it on 1930.",
    "Your order is out for delivery. Share OTP 4821 only with the delivery agent at your door.",
    "Rs 500 debited from A/c XX12 at Croma. If not done by you, call 1800 1234 or block the card in the app.",
    "आरबीआई कभी भी ओटीपी या पिन नहीं मांगता। धोखाधड़ी की शिकायत 1930 पर करें।",
    "Bank kabhi bhi call karke UPI PIN nahi maangta. Shikayat 1930 par karein.",
])
def test_genuine_warnings_and_alerts_are_not_flagged(text):
    a = mech.analyze(text)
    for p in (0.5, 0.9, 0.99):
        assert mech.decide(p, a)[0] != 1, (p, text)
    assert verdict(text) != 1


@pytest.mark.parametrize("text", [
    "Don't panic, just share the OTP with our officer to cancel the charge.",
    "RBI never asks for OTP. Share the OTP on 9876501234 to verify your account.",
    "SBI never asks for your PIN. Update KYC now at sbi-kyc-update.top or your account is blocked.",
    "Do not tell your family. Transfer Rs 50,000 to the safe account now.",
    "If not done by you, share the OTP with our executive to reverse it.",
])
def test_scams_with_warning_words_are_still_flagged(text):
    assert verdict(text) == 1, text


def test_contact_gate_needs_something_to_act_on():
    notice = "Dear customer, your reward points statement for November is ready."
    a = mech.analyze(notice)
    assert not a["harm"]
    assert mech.decide(0.99, a)[0] == 0
    with_number = notice + " Call 9876501234 to redeem."
    assert mech.decide(0.99, mech.analyze(with_number))[0] == 1


def test_contact_gate_keeps_a_payment_order():
    text = "होटल रेटिंग का काम: पहले 500 रुपये रिचार्ज करें, पूरा पैसा कमीशन के साथ वापस मिलेगा।"
    assert mech.decide(0.9, mech.analyze(text))[0] == 1


def test_negated_isolation_order_does_not_hide_the_payment_order():
    assert "पैसे भेजें" in mech.request_text("वकील से संपर्क न करें और तुरंत पैसे भेजें।")
    assert "pay now" in mech.request_text("Don't panic, pay now.")


def test_warning_segments_keep_scam_isolation_and_conditional_threats():
    assert not mech._warning_segment("do not tell your family")
    assert not mech._warning_segment("agar payment nahi hua toh connection kat jayega")
    assert mech._warning_segment("RBI never asks for your OTP")
    assert mech._warning_segment("kabhi AnyDesk install na karein")


def test_list_after_a_negation_stays_with_it():
    text = "The department does not send links asking for bank details, card CVV, or OTP."
    assert mech.request_text(text) == "."


def test_cleared_alert_reports_no_harm_evidence():
    text = "HDFC Bank never asks for your OTP, PIN, CVV or card number. Report fraud on 1930."
    lab, _, ev = detect.predict_text([text])[0]
    assert lab == 0
    assert not any("asks you to share" in e for e in ev)
