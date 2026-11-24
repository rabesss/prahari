"""Validation-gate PR: false alarms on genuine advisories and wrong evidence phrases.

Each fixed pattern has a genuine case that must not be flagged and scam look-alikes that must stay
flagged. All messages are hand-written for this test; none comes from a dev, validation, audit or
holdout set.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from triage import detect, llm, mech  # noqa: E402


def verdict(text):
    return detect.predict_text([text])[0][0]


# 1. Family or friend warnings about a hypothetical caller, with a protective instruction.
@pytest.mark.parametrize("text", [
    "Bhai, agar koi bank se bolke OTP maange to phone kaat dena, kuch mat batana.",
    "दादी, अगर कोई केवाईसी के नाम पर ओटीपी या पिन मांगे तो कुछ मत बताना, फोन काट देना।",
    "Nani, if someone calls from SBI asking for your OTP or sending a KYC link, hang up right away.",
    "Beta, if anyone calls saying your pension will stop and asks for the UPI PIN, just disconnect. "
    "We will go to the branch on Monday.",
])
def test_hypothetical_caller_warnings_are_not_flagged(text):
    assert verdict(text) != 1
    a = mech.analyze(text)
    for p in (0.5, 0.9, 0.99):
        assert mech.decide(p, a)[0] != 1, (p, text)


@pytest.mark.parametrize("text", [
    "Mom, if anyone calls asking for the OTP, just share it, it is our bank agent.",
    "Papa, agar koi OTP maange to de dena, bank wale hain.",
    "पापा, अगर कोई ओटीपी मांगे तो बता देना, बैंक वाले हैं।",
    "If anyone calls asking for OTP, hang up and call me on 9876543210 instead.",
    "If anyone asks for your OTP, hang up. Then share the OTP with our officer when he calls back.",
    "If anyone calls asking for the OTP, hang up and forward the SMS to me.",
    "If someone asks for OTP, disconnect, and install AnyDesk so our team can secure your account.",
    "If anyone calls asking for OTP, hang up and visit sbi-secure-help.top to block your card.",
    "If anyone asks for the OTP, don't disconnect, give them the code.",
    "Agar koi OTP maange to phone kaat dena, warna account band ho jayega, abhi 500 rupaye bhejo.",
    "अगर कोई ओटीपी मांगे तो फोन काट देना। लेकिन मुझे अभी ओटीपी भेजो, जरूरी है।",
    "If anyone calls asking for the OTP, hang up. Your account will be blocked today, share your PIN to keep it.",
    "If anyone calls asking for OTP hang up and message us on WhatsApp to report.",
    "If anyone calls, share the OTP, then hang up.",
    "If anyone calls asking for OTP, sharing it is fine, hang up after.",
])
def test_demands_behind_a_hypothetical_caller_stay_flagged(text):
    assert verdict(text) == 1


def test_hypothetical_warning_needs_an_unknown_caller_and_protection():
    assert mech._hypothetical_warning("agar koi OTP maange to phone kaat dena")
    assert not mech._hypothetical_warning("agar koi OTP maange to de dena")       # order, not protection
    assert not mech._hypothetical_warning("if the officer asks for the OTP, hang up")  # not an unknown caller
    assert not mech._hypothetical_warning("if anyone asks for the OTP, don't hang up")  # protection negated


# 2. Negated warnings: a request cue that sits only inside "do not share" is not a request, and a
#    Hindi completed credit ("जमा किए गए हैं") is a record, not an order to deposit.
@pytest.mark.parametrize("text", [
    "आपके खाते में ₹1,500 जमा हो गए हैं। कृपया ओटीपी किसी को न बताएं।",
    "आपके पंजाब नेशनल बैंक खाते XX4410 में ₹8,000.00 एनईएफटी द्वारा जमा किए गए हैं। उपलब्ध शेष ₹21,300 है।",
    "बैंक कभी भी फोन पर ओटीपी, पिन या सीवीवी नहीं मांगता। किसी को भी ये जानकारी न दें।",
    "Bank kabhi bhi call par OTP, PIN ya CVV nahi maangta. Kisi ko mat batana.",
    "बैंक जनहित सूचना: बैंक कभी भी कॉल, एसएमएस या लिंक के जरिए केवाईसी, ओटीपी, सीवीवी या यूपीआई पिन नहीं "
    "मांगता। शिकायत 1930 या cybercrime.gov.in पर करें।",
])
def test_negated_warnings_and_credit_records_are_not_flagged(text):
    assert verdict(text) != 1


@pytest.mark.parametrize("text", [
    "आपके खाते में गलती से ₹25,000 जमा हो गए हैं। कृपया 9876543210 पर वापस भेजें।",
    "आपके खाते में ₹5,000 जमा किए गए हैं। ओटीपी बताएं ताकि पुष्टि हो सके।",
    "आपके बैंक खाते में ₹10,000 जमा किए गए हैं। रिफंड के लिए ₹500 शुल्क जमा करें।",
    "बैंक कभी ओटीपी नहीं मांगता, लेकिन केवाईसी के लिए अभी 9876543210 पर ओटीपी भेजें।",
])
def test_scams_around_credits_and_negations_stay_flagged(text):
    assert verdict(text) == 1


def test_perfective_deposit_is_not_a_payment_order_but_imperative_is():
    assert not mech._ordered("₹2,000 आपके खाते में जमा किए गए हैं", threat=False)
    assert mech._ordered("₹2,000 अभी जमा करें", threat=False)


# 3. Evidence phrases the explanation repeats.
def test_reserved_domain_is_not_called_common_for_scams():
    assert mech.host_risk("parcel-help.example") == "the domain parcel-help.example is not an official site"
    assert "throwaway" in mech.host_risk("parcel-help.top")
    text = "Your parcel is held. Pay the Rs 49 fee at parcel-help.example to release it."
    lab, _, ev = detect.predict_text([text])[0]
    assert lab == 1
    phrases = llm.compact_evidence("sms", text, ev, lab)
    assert not any("throwaway" in p for p in phrases), phrases
    assert all(len(p) <= 78 for p in phrases)


def test_blackmail_is_not_described_as_account_blocking():
    text = "Tumhari private photos sab contacts ko bhej dunga. Abhi ₹15,000 bhejo warna sabko bhejunga."
    lab, _, ev = detect.predict_text([text])[0]
    assert lab == 1
    phrases = llm.compact_evidence("sms", text, ev, lab)
    assert not any("block" in p for p in phrases), phrases
    assert llm.scam_type("sms", text, lab) == "sextortion or blackmail"
    # Without private material the line names the threat it is, still not account blocking.
    a = mech.analyze("Abhi ₹15,000 bhejo warna tumhare family ko message kar dunga.")
    assert ("block_threat", mech.EXPOSE_DESC) in a["harm"]


def test_trading_deposit_is_not_described_as_refund_fee():
    text = "Assured 4% profit daily in our trading group. Deposit Rs 20,000 today to unlock the VIP plan: vip-trade.top"
    lab, _, ev = detect.predict_text([text])[0]
    assert lab == 1
    phrases = llm.compact_evidence("sms", text, ev, lab)
    assert not any("refund, prize or parcel" in p for p in phrases), phrases
    assert llm.scam_type("sms", text, lab) == "an investment or trading scam"


def test_account_block_threat_keeps_its_phrase():
    text = "Your SBI account will be blocked today. Update KYC at sbi-kyc-help.top now."
    a = mech.analyze(text)
    assert ("block_threat", "threatens to block, cut or freeze an account, SIM or connection") in a["harm"]
