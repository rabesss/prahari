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


# 1. Hypothetical-caller warnings ("if anyone calls asking for an OTP, hang up") are NOT cleared: a
#    narrow rule was tried and dropped after review kept finding demands it cleared. These scams
#    around the same wording must stay flagged.
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
    "If anyone asks for your OTP, do not share it, give it to me.",
    "If anyone calls asking for OTP, hang up and never share it, send your PIN.",
    "Agar koi OTP maange to kuch mat batana, mujhe bhej do.",
    "If anyone calls asking for OTP, sharing it is fine, hang up after.",
])
def test_demands_behind_a_hypothetical_caller_stay_flagged(text):
    assert verdict(text) == 1


# 2. Negated warnings: a request cue that sits only inside "do not share" is not a request, and a
#    Hindi completed credit ("जमा किए गए हैं") is a record, not an order to deposit.
@pytest.mark.parametrize("text", [
    "आपके खाते में ₹1,500 जमा हो गए हैं। कृपया ओटीपी किसी को न बताएं।",
    "आपके पंजाब नेशनल बैंक खाते XX4410 में ₹8,000.00 एनईएफटी द्वारा जमा किए गए हैं। उपलब्ध शेष ₹21,300 है।",
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


def test_past_exposure_is_not_a_sextortion_threat():
    a = mech.analyze("Your private photos viral ho gaya. Contact me now.")
    assert "sextortion" not in {n for n, _ in a["harm"]}


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


# Review round 1 (GLM 5.4): demands next to a warning stay flagged.
@pytest.mark.parametrize("text", [
    "If anyone calls asking for the OTP, do not share it, SBI: Apna OTP dijiye.",
    "If someone from SBI asks for your PIN, never say it out loud, type it in the AnyDesk chat.",
    "If anyone asks for the OTP, disconnect and try installing AnyDesk from the Play Store.",
    "अगर कोई कॉल पर ओटीपी मांगे तो फोन काट देना और कलेक्ट अनुरोध स्वीकार करें",
    "agar koi OTP maange to phone kaat dena aur OTP ka screenshot lo aur humein dikhao",
    "SBI KYC: our officer will call you for the OTP, if anyone else calls asking for OTP, hang up.",
    "SBI सपोर्ट: कृपया स्क्रीन शेयर करें, हम ओटीपी नहीं मांगते।",
    "SBI: AnyDesk app open karo, bank OTP nahi maangta.",
    "SBI सपोर्ट: कृपया AnyDesk ऐप खोलें, हम ओटीपी नहीं मांगते।",
    "क्यूआर कोड स्कैन करें और ₹2000 का भुगतान स्वीकार करें, बैंक ओटीपी नहीं मांगता",
    "Never share your OTP with anyone except our verified executive. If anyone calls asking for the OTP, do not share it with anyone.",
    "SBI: humein OTP chahiye. If anyone calls asking for the OTP, hang up.",
    "SBI: अगर कोई ओटीपी मांगे तो फोन काट देना, our officer is asking for it.",
    "Agar koi OTP maange to phone kaat dena, hamare agent ko chahiye.",
])
def test_demands_next_to_warning_spans_stay_flagged(text):
    assert verdict(text) == 1


def test_extortion_and_exposure_have_their_own_phrases():
    text = "We have your son. Pay Rs 5 lakh to get him back safely. Final notice."
    lab, _, ev = detect.predict_text([text])[0]
    assert lab == 1
    assert llm.compact_evidence("sms", text, ev, lab)[0].startswith("threatens you or your family")
    text = "Abhi ₹15,000 bhejo warna tumhare family ko message kar dunga."
    lab, _, ev = detect.predict_text([text])[0]
    assert lab == 1 and llm.scam_type("sms", text, lab) == "an extortion threat"
    assert not any("block" in p for p in llm.compact_evidence("injection", text, ev, lab))


def test_reserved_tld_outside_the_risky_list_keeps_its_decision():
    assert mech.host_risk("portal.localhost") == ""
    assert mech.host_risk("rewards.test") == ""


def test_long_reserved_host_phrase_fits_the_budget():
    host = "a-very-long-parcel-redelivery-confirmation-portal-for-customers.example"
    assert len(llm._risky_short(mech.host_risk(host))) <= 78


# Review rounds 2-3 (gpt-6.1-terra, GLM 5.4): leftovers that hand over, demand or make an exception.
@pytest.mark.parametrize("text", [
    "SBI सपोर्ट: स्क्रीन शेयर कर लेना, बैंक ओटीपी नहीं मांगता।",
    "SBI: AnyDesk open kar, bank OTP nahi maangta.",
    "SBI सपोर्ट: पासवर्ड भर, बैंक ओटीपी नहीं मांगता।",
    "If anyone calls asking for the OTP, hang up, do not delay, share it with our officer.",
    "When someone calls asking for the OTP, hang up and pass it to me.",
    "If anyone calls asking for the OTP, hang up. Message me the same.",
    "Agar koi OTP maange to phone kaat dena, der mat karo, humein bata do.",
    "SBI: If anyone calls asking for your OTP, do not share it. Only our verified officer will ask for it.",
    "If anyone calls asking for the OTP, do not share it with anybody but our executive.",
    "Agar koi OTP maange to phone kaat dena. Sirf humara hi officer maangega.",
    "SBI: If anyone calls asking for your OTP, hang up. You must disclose it to our officer.",
    "If anyone calls asking for the OTP, hang up, then reveal the same to our desk.",
    "Agar koi OTP maange to phone kaat dena. Ise hamare officer ko batana hai.",
    "If anyone calls asking for your PIN, hang up. Our officer needs the same, type it in the app he sends.",
])
def test_leftover_handover_demand_or_exception_stays_flagged(text):
    assert verdict(text) == 1


def test_lead_in_words_do_not_backtrack():
    import time
    t = time.time()
    mech.analyze("now " * 40 + "pay")
    assert time.time() - t < 1.0


def test_feedback_invitation_is_not_called_an_exposure_threat():
    a = mech.analyze("HDFC Bank: Your family savings account is credited with Rs 5000. "
                     "Share feedback with friends and family on 18002663360.")
    assert all(d != mech.EXPOSE_DESC for _, d in a["harm"])


def test_spaced_hinglish_sextortion_is_recognised():
    a = mech.analyze("Tumhari private video sab contacts ko bhej dunga. Abhi 20,000 bhejo.")
    assert "sextortion" in {n for n, _ in a["harm"]}


def test_first_person_leak_threat_uses_the_exposure_line():
    a = mech.analyze("Pay Rs 20000 now. I'll leak your photos to your family.")
    assert ("block_threat", mech.EXPOSE_DESC) in a["harm"]


# Review round 3 (GLM 5.4) strings: with the span rules removed these stay flagged as at base.
@pytest.mark.parametrize("text", [
    "Agar koi OTP maange to mujhe de, phone kaat dena.",
    "अगर कोई ओटीपी मांगे तो हमें दे, फोन काट देना।",
    "Agar koi OTP maange to AnyDesk laga lo, phone kaat dena.",
    "If anyone calls asking for the OTP, hang up, repeat it to me.",
    "SBI: verification ke liye AnyDesk app chahiye, bank OTP nahi maangta.",
    "HDFC: KYC update ke liye OTP chahiye, bank kabhi OTP nahi maangta.",
    "SBI सपोर्ट: AnyDesk लगाओ, बैंक ओटीपी नहीं मांगता।",
    "If anyone calls asking for the OTP and asks you to open the link sent by SMS, hang up.",
])
def test_round3_strings_stay_flagged(text):
    assert verdict(text) == 1
