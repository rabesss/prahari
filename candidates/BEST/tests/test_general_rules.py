"""Hand-written messages that are in no evaluation split, several per general rule. A later change
that breaks a rule fails here instead of on the next tuning split."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from triage import detect  # noqa: E402


def verdict(text):
    return detect.predict_text([text])[0][0]


GENUINE = [
    "HDFC Bank: Rs 2,350.00 debited from A/c XX4412 to AMAZON. Avl bal Rs 58,210. Never share your OTP. "
    "Call 18002662261 if not you.",
    "ICICI: Your bill of Rs 1,240 for the credit card ending 9012 is due on 05 Dec. Pay via iMobile app "
    "or icicibank.com.",
    "Dear customer, your broadband plan renews on 28 Nov for Rs 599. Auto-debit from your registered account.",
    "Airtel: Your postpaid bill of Rs 843 is ready. Pay by 25 Dec in the Airtel Thanks app to avoid "
    "service disruption.",
    "SBI: If you did not request a password reset, call 1800-425-3800 or ignore this message.",
    "Flipkart: Order OD123456789 delivered. Rate your experience in the app.",
    "Apollo Diagnostics: Report for Rajesh is ready. Collect at the desk or view it in the Apollo 24|7 app.",
    "LIC premium of Rs 23,489 is due on 12 Dec. Pay at any LIC branch or licindia.in.",
    "BSES Rajdhani: Power shutdown in your area has been rescheduled. We regret the inconvenience.",
    "Canara Bank: New beneficiary 'R MEHTA' added to your account XX3308. Not you? Disable net banking in "
    "the Canara DiYA app or visit canarabank.com.",
    "Hi Ma, I paid the electricity bill online just now, Rs 612. No hurry, give it to me whenever.",
    "UPITX: Rs 1,000.00 credited to your A/c XX9912 by NEFT from RAMESH KUMAR on 23-11-2026.",
    "DMRC: Smart card 1234567890 recharged with Rs 200. Balance Rs 450. Check on the Delhi Metro Rail app.",
    "IndianOil: LPG booking 7788990011 delivered on 23 Nov. Give the delivery code 4502 to the delivery "
    "boy at the door.",
    "Cybercrime police warn of a new WhatsApp scam where callers pose as bank staff and ask for OTP. "
    "Banks never ask for OTP. Report at 1930 or cybercrime.gov.in.",
]

SCAM = [
    "HDFC Alert: Your account will be suspended today. Verify at hdfc-secureverify.xyz or call 9811098110.",
    "SBI Customer Care: Your KYC is expired. Update PAN and Aadhaar through this link sbi-kycnow.in "
    "within 24 hours to avoid blocking.",
    "Your SBI debit card is blocked for suspicious activity. Share card number, expiry and OTP with our "
    "verification officer on WhatsApp 9876543210.",
    "TRAI Advisory: Fake calls are being made to deactivate mobile numbers. To protect your number, "
    "register on sanchar-verify.in-verify today or call the nodal desk 87XXXXXX33.",
    "Dear customer, your electricity will be disconnected tonight. Pay pending bill of Rs 1,530 to the "
    "assistant engineer on 9876543210 and share the receipt photo on WhatsApp.",
    "Kotak: Your card ending 5521 was declined 3 times. To unlock, install the Kotak Secure app from "
    "kotak-secureapp.in and complete verification.",
    "Congrats! You won Rs 5,00,000 in the KBC lottery. Pay Rs 8,500 processing fee to claim. Call the "
    "manager on 9876543210.",
    "Axis: A beneficiary was added to your account. If not done by you, call 9876500035 immediately to "
    "freeze your account.",
    "RBI Advisory: UPI apps will be discontinued tonight. Re-register your UPI on upi-rbi-verify.net "
    "within 2 hours.",
    "Customs Mumbai: Your parcel is on hold. Pay Rs 1,850 duty by UPI to the inspector's number 9876500077 "
    "to release it.",
    "Your SIM will be deactivated in 30 minutes. Press *401*98XXXXXX21# to whitelist your Aadhaar.",
    "PNB: EMI of Rs 12,400 is overdue. Avoid penalty: settle now at pnb-emi-pay.top.",
    "Our agent asks customers for the OTP to renew their SIM today.",
    "SBI alert: fraudsters are active in your area. To keep your account safe, share your OTP with our "
    "officer on 9876543210.",
]


@pytest.mark.parametrize("text", GENUINE, ids=lambda text: text[:48])
def test_genuine_message_is_cleared(text):
    assert verdict(text) == 0


@pytest.mark.parametrize("text", SCAM, ids=lambda text: text[:48])
def test_scam_message_is_flagged(text):
    assert verdict(text) == 1
