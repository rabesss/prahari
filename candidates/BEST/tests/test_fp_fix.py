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
    "DigiLocker sign-in code 385721. Keep this code private; support will not ask you to forward it.",
    "For security never share your OTP with anyone or install AnyDesk on request.",
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
    # PR #48 review (gpt-6.1-terra): affirmative orders next to warning words
    "Share your bank OTP only with our executive.",
    "RBI never asks for OTP, and share your OTP with our officer.",
    "If not you, transfer money to the safe account now.",
    "Never share your PIN with anyone. Share it with our officer to verify.",
    # PR #48 review (CodeRabbit): a negated tail must not cover the order before it
    "Share your OTP with our officer, not your family.",
])
def test_scams_with_warning_words_are_still_flagged(text):
    assert verdict(text) == 1, text


# PR #48 review (GLM 5.4): orders hidden next to warning words, self-check lead-ins that are really
# threats, and contactless threats. Main flags each of these at model scores 0.5 and 0.99; so must this.
GLM_RULE_LAYER = [
    "Reply with the OTP now, don't delay.",
    "Share the OTP with our executive now, not anyone else.",
    "SBI refund ke liye OTP humein bhejein, sabko nahi.",
    "अपना ओटीपी हमारे एजेंट को दें, दूसरों को ना।",
    "Never share your OTP with anyone and send the PIN to our executive for verification.",
    "Agar aapne nahi kiya to apna OTP humein bhej dein taaki transaction reverse ho jaye.",
    "If anyone calls you share the OTP with them to verify your account",
    "Your refund of Rs 3,499 is pending. Share the OTP only with our executive to complete it.",
    "आपके केवाईसी अपडेट के लिए कोई भी ओटीपी हमें तुरंत भेजें।",
    "To prevent unauthorised access to your SBI account share the OTP received on your phone with our security team.",
    "Dear SBI customer, if you have not updated your KYC, your account will be blocked today.",
    "UPCL: If you have not paid the bill, your electricity connection will be cut tonight. Pay now.",
]
# PR #48 review round 2 (gpt-6.1-terra)
GLM_RULE_LAYER += [
    "Your parcel is at your door install AnyDesk immediately to verify your identity",
    "At delivery transfer money to our safe account to release your parcel",
    "कूरियर मिलने पर अपना बैंक ओटीपी हमारे एजेंट को दें।",
    "RBI never asks for your OTP please share your PIN with our executive",
    "Never give your OTP to strangers then share your PIN with our officer.",
]
# PR #48 review round 2 (GLM 5.4)
GLM_RULE_LAYER += [
    "Share the OTP with the courier at your door or your account will be blocked permanently.",
    "Share your UPI PIN with the delivery agent at your door.",
    "Your parcel is held at customs. Pay the clearance duty of Rs 2,350 to the courier in person when the parcel arrives.",
    "SBI: आपका KYC बंद हो रहा है। घर पर आने वाले एजेंट को OTP दें और ऑर्डर पाएं।",
    "Share the OTP with the courier boy at your door when he rings.",
    "Aapne kabhi SBI ka KYC nahi karvaya isliye OTP turant bhejein.",
    "जिन ग्राहकों ने कभी KYC अपडेट नहीं करवाया वे अपना OTP तुरंत हमारे अधिकारी को भेजें।",
    "Never share your OTP with strangers simply share it with our executive.",
    "Never share your OTP with anyone and accept the collect request sent to you.",
    "Never share your OTP with anyone and dictate it to our verification officer.",
    "कोई भी OTP मांगे, तुरंत हमें भेजिए।",
    "Agar koi OTP maange to use de dijiye, warna account band ho jayega.",
    "SBI: If this was not you, move your funds to the safe account.",
    "HDFC: If not done by you, authorise the debit and we will refund it.",
    "SBI: If you did not make this payment, a penalty of Rs 10,000 will be debited from your account.",
]
# PR #48 review round 3 (gpt-6.1-terra, GLM 5.4)
GLM_RULE_LAYER += [
    "Share your login OTP with the courier at your door to confirm your identity",
    "SBI: If this was not you, kindly confirm your debit card number to reverse the charge.",
    "HDFC: If you did not make this transaction, our fraud team will connect via AnyDesk to secure your account.",
    "SBI: अगर यह लेनदेन आपने नहीं किया तो OTP देकर वेरिफाई करें।",
    "Agar yeh transaction aapne nahi kiya to OTP de kar confirm karein.",
    "Your loan is approved. Share the OTP with the courier at your doorstep to receive the cheque.",
]
# Main flags these only on a high model score; the contact gate must let that score through.
GLM_MODEL_LAYER = [
    "Share your OTP only with the courier boy when he calls.",
    "SBI: Your internet banking is locked. Unlock here: sbi-netbanking.pw/verify",
    "HDFC: Account on hold. KYC form: forms.gle/abcXYZ12",
    "Agar koi bank wala call kare aur OTP mange to turant bata dein.",
    "Agar aapne SBI account ka KYC update nahi kiya to account band ho jayega.",
    "Your internet banking is locked. Unlock here: secureportal.pw",
    "SBI account suspended. Visit sbihelp.pw now",
    # PR #48 review round 2 (GLM 5.4)
    "SBI KYC pending hai. Apna OTP humein bata dena.",
    "Papa main nayi SIM se bol raha hoon. Jaldi Rs 7,000 bhej dena.",
    "UPCL: आपकी बिजली काट दी जाएगी। आज ही बिल भरें।",
    "SBI: Your internet banking is locked. Unlock here: sbisecure.pw",
    "Never share your OTP with anyone except our verified executive.",
    "Don't hesitate to share the OTP with our executive.",
    "SBI: Apna OTP dijiye.",
]


@pytest.mark.parametrize("text", GLM_RULE_LAYER)
def test_review_scams_flagged_at_mid_and_high_model_score(text):
    a = mech.analyze(text)
    for p in (0.5, 0.99):
        assert mech.decide(p, a)[0] == 1, (p, text)


@pytest.mark.parametrize("text", GLM_MODEL_LAYER)
def test_review_scams_keep_the_model_backstop(text):
    assert mech.decide(0.9, mech.analyze(text))[0] == 1, text


# Known residual false alarms: hypothetical-caller warnings, doorstep handover codes and self-check
# alerts are not cleared by warning context. Clearing them was tried and dropped in PR #48 review
# because each rule opened ways to hide a demand. They are recorded here, not asserted either way.
KNOWN_RESIDUAL = [
    "If anyone calls you asking for an OTP to stop a parcel, hang up and report it on 1930.",
    "Your order is out for delivery. Share OTP 4821 only with the delivery agent at your door.",
    "SBI: Rs 2,450 debited via UPI. If unauthorised, block card in YONO app.",
]


def test_genuine_advisory_with_negated_list_of_actions_is_not_flagged():
    text = ("CyberDost: paise receive karne ke liye kabhi UPI PIN daalne ya QR code scan karne ki zaroorat "
            "nahi hoti. Shikayat 1930 par karein.")
    assert mech.decide(0.99, mech.analyze(text))[0] != 1


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
