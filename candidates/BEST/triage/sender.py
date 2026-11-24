"""Optional sender check: a warn-only signal from who sent an SMS.

Indian A2P SMS from banks, government, couriers and telecom operators come from registered DLT
sender IDs ("headers") such as AX-HDFCBK-S, not from 10-digit personal mobile numbers (TRAI
TCCCPR 2018 and its directions; see docs/sender-check.md). So a message that claims such an
identity, reads like such an alert, or asks for an OTP or KYC details, and arrived from a personal
mobile number, is raised to at least SUSPICIOUS.

The signal only ever raises risk. A registered-looking header never lowers a verdict and never
produces "safe" or "verified" wording: headers can be spoofed in a forwarded message or a
screenshot, and the reader types the sender in by hand. With no sender, or any sender that is not
a personal mobile number, every result is returned unchanged.

For a call that claims to be a bank, calls get only an advisory note: banks are moving service
calls to the 1600 number series in phases, so the number alone proves nothing either way.
"""
import re

from . import mech

# Vetted text. The UI shows SENDER_LINE as evidence; Llama gets a short phrase for the required
# opening and SENDER_FACT for its one sentence, and only paraphrases them.
SENDER_LINE = ("Banks and government send SMS from registered sender IDs like XX-ABCDEF, "
               "not personal mobile numbers")
SENDER_LINE_HI = ("बैंक और सरकारी विभाग SMS रजिस्टर्ड सेंडर ID (जैसे XX-ABCDEF) से भेजते हैं, "
                  "निजी मोबाइल नंबर से नहीं")
SENDER_FACT = "Banks and government send SMS from registered sender IDs, not personal mobile numbers."
OPENING = {
    "identity": "it claims to be a bank or official sender but came from a personal mobile number",
    "alert": "it looks like an official alert but came from a personal mobile number",
    "request": "it asks for an OTP or KYC details but came from a personal mobile number",
}
NOTE_1600 = ("Banks are moving service calls to numbers that start with 1600, in phases. "
             "Whatever the number, hang up and call the number on your card or in the bank app; "
             "never share an OTP or PIN on a call.")
NOTE_1600_HI = ("बैंक अपनी सर्विस कॉल धीरे-धीरे 1600 से शुरू होने वाले नंबरों पर ला रहे हैं। "
                "नंबर कोई भी हो, फ़ोन काटें और कार्ड या बैंक ऐप पर दिए नंबर पर खुद कॉल करें; "
                "कॉल पर OTP या PIN कभी न बताएं।")

TEXT_KINDS = ("sms", "injection")

_SEP = r"[\s.\-()/]*"
_MOBILE = re.compile(r"^(?:\+?91|0)?" + _SEP + r"([6-9](?:" + _SEP + r"\d){9})$")
_SERIES_1600 = re.compile(r"^(?:\+?91" + _SEP + r")?0?(1600(?:" + _SEP + r"\d){6})$")
# Optional 2-letter operator/circle prefix, a 6-character entity, optional TRAI category suffix
# (-S service, -T transactional, -P promotional, -G government).
_DLT = re.compile(r"^(?:([A-Z]{2})[-\s])?([A-Z0-9]{6})(?:[-\s]([STPG]))?$")


def parse(sender):
    """Classify a sender string. None for an empty sender.

    kind is "mobile" (a 10-digit Indian mobile number, with or without +91/0), "1600" (the
    1600 service-call series), "dlt" (a registered-looking header) or "other".
    """
    if sender is None:
        return None
    s = str(sender).strip()
    if not s:
        return None
    m = _MOBILE.match(s)
    if m:
        return {"kind": "mobile", "number": re.sub(r"\D", "", m.group(1))}
    m = _SERIES_1600.match(s)
    if m:
        return {"kind": "1600", "number": re.sub(r"\D", "", m.group(1))}
    m = _DLT.match(s.upper())
    if m and (m.group(1) or not m.group(2).isdigit()):
        return {"kind": "dlt", "prefix": m.group(1), "entity": m.group(2), "suffix": m.group(3)}
    return {"kind": "other"}


_INSTITUTION = re.compile(
    r"\b(?:bank|banking|net ?banking|sbi|hdfc|icici|axis|kotak|pnb|canara|baroda|bob|idbi|indusind|"
    r"yes ?bank|union bank|bandhan|federal bank|rbi|reserve bank|paytm|phonepe|gpay|google pay|npci|bhim|"
    r"credit card|debit card|uidai|aadhaar|aadhar|income ?tax|epfo|government|govt|ministry|police|cbi|"
    r"customs|cyber ?cell|e-?challan|traffic challan|rto|electricity|bijli|discom|courier|india ?post|"
    r"speed ?post|parcel|shipment|fedex|dhl|blue ?dart|delhivery|dtdc|airtel|jio|vodafone|vi|bsnl|mtnl|"
    r"trai|telecom|sim card|kyc)\b|"
    r"बैंक|बिजली|आधार|आयकर|सरकार|पुलिस|कस्टम|कूरियर|पार्सल|डाक|सिम|केवाईसी|एयरटेल|जियो|बीएसएनएल|ट्राई",
    re.I)
_DEAR = re.compile(r"\b(?:dear|valued)\s+(?:customer|user|sir|madam|member|subscriber|consumer|"
                   r"card ?holder|account ?holder)\b|प्रिय (?:ग्राहक|उपभोक्ता)", re.I)
_YOUR_ACCOUNT = re.compile(
    r"\b(?:your|ur|aapk[aei]|apk[aei]|tumhar[aei])\b[^.;!?।\n]{0,25}?"
    r"\b(?:a/?c|account|acct|card|kyc|pan|aadhaa?r|parcel|shipment|package|consignment|sim|"
    r"mobile number|connection|wallet|upi|loan|emi|policy|pf|refund|challan|reward points?|"
    r"electricity|bijli|net ?banking|khata|khaata)\b|"
    r"(?:आपका|आपके|आपकी)[^.;!?।\n]{0,25}?(?:खाता|खाते|कार्ड|पार्सल|सिम|नंबर|कनेक्शन|केवाईसी|आधार|पैन|लोन|बिजली)",
    re.I)
_KYC_ASK = re.compile(
    r"\b(?:kyc|e-?kyc|pan|aadhaa?r)\b[^.;!?।\n]{0,30}\b(?:update|verify|complete|link|re-?submit|expire|"
    r"expired|pending|suspend\w*|block\w*|karein|karo|kare)\b|"
    r"\b(?:update|verify|complete|link)\b[^.;!?।\n]{0,20}\b(?:kyc|e-?kyc|pan|aadhaa?r)\b|"
    r"\b(?:kyc|e-?kyc|pan|aadhaa?r)\b[^.;!?।\n]{0,20}\b(?:not (?:updated|completed|verified|linked)|incomplete)\b|"
    r"(?:केवाईसी|आधार|पैन)[^.;!?।\n]{0,30}(?:अपडेट|सत्यापित|लिंक|पूरा|बंद)", re.I)
_REQUEST_HARM = {"secret_request", "id_request"}
# Bank-alert markers: a masked account or card number, a balance, a transaction reference.
_ALERT_MARK = re.compile(r"\b(?:a/?c|acct|account|card)\s*(?:no\.?\s*)?(?:ending\s*)?[x*]{2,}\s*\d{2,6}\b|"
                         r"\b[x*]{2,}\d{3,6}\b|\b(?:avl\.?|available)\s*bal|\b(?:txn|upi ref|ref no|utr)\b", re.I)
# A first-person or casual chat about the writer's own transaction is not an alert.
_CHATTY = re.compile(r"\b(?:my|mine|i|i'm|i've|mera|meri|mere|maine|bhai|bhaiya|yaar|yar|bro|dude|thanks|thx|lol)\b|"
                     r"मेरा|मेरी|मेरे|मैंने|भाई|यार", re.I)
_DEBIT = re.compile(r"\b(?:debited|credited|withdrawn)\b", re.I)
# An institution's notice to the reader: an action, deadline, hold or threat, not a chat.
_NOTICE_CUE = re.compile(
    r"\b(?:block\w*|suspend\w*|deactivat\w*|disconnect\w*|expir\w*|freez\w*|frozen|terminat\w*|"
    r"held|on hold|pending|due|overdue|update|verify|verification|re-?kyc|link|pay|click|call|"
    r"penalty|fine|seized|cancel\w*|kat (?:jayega|jaega|jayegi)|band (?:ho|kar)\w*|turant|today|tonight|"
    r"immediately|within \d+|now|accessed|new device|unusual|suspicious|logged in|shipped|dispatched|"
    r"out for delivery)\b|बंद|काट|रोक|तुरंत|आज|अपडेट|सत्यापित|भुगतान", re.I)
_CLAUSE = re.compile(r"[.!?।;\n]+")
_SUBCLAUSE = re.compile(r"[.!?।;,\n]+")
# Hinglish "na" negates only before the verb ("na karein"); "karo na" is a plea.
_KYC_NEG = re.compile(r"\b(?:never|not|don'?t|do not|doesn'?t|won'?t|kabhi|mat|nahi|nahin)\b|\bno\b(?!\s+doubt)|"
                      r"\bna\s+kar\w*|नहीं|मत|कभी|(?:^|\s)न(?:\s|$)", re.I)
# The writer's own KYC ("my KYC is pending", "KYC kar diya", "मेरा केवाईसी") is news, not an ask.
_KYC_OWN = re.compile(r"\b(?:my|mera|meri|mere|hamara|humara|our)\s+(?:\w+\s+)?(?:kyc|e-?kyc|pan|aadhaa?r)\b|"
                      r"(?:मेरा|मेरी|मेरे|हमारा)\s*(?:\S+\s+)?(?:केवाईसी|पैन|आधार)", re.I)
_CODE = re.compile(r"\b(?:code|password|passcode|pin)\b", re.I)


def _code_for_institution(t):
    """A code or password named for a bank or service in the same sub-clause ("code ... for SBI
    login"), not a door or wifi code next to an unrelated mention."""
    return any(_CODE.search(c) and _INSTITUTION.search(c) and not _CHATTY.search(c) for c in _SUBCLAUSE.split(t))


_KYC_DONE = re.compile(r"\b(?:kar (?:diya|di|li|liya)|ho gaya|ho gayi|is done|done|completed|updated)\b|कर दिया|हो गया", re.I)


def _kyc_ask(t):
    """A KYC/PAN/Aadhaar update ask aimed at the reader.

    Checked per sub-clause: a negation right before the ask ("never ask you to update KYC"), the
    writer's own KYC, or a done update ("KYC kar diya", but not "KYC not completed") is no ask.
    """
    for c in _SUBCLAUSE.split(t):
        m = _KYC_ASK.search(c)
        if not m or _KYC_OWN.search(c):
            continue
        if _KYC_NEG.search(c[max(0, m.start() - 25):m.start()]) or _KYC_NEG.search(m.group(0)):
            continue
        done = _KYC_DONE.search(c)
        if done and not _KYC_NEG.search(c[max(0, done.start() - 8):done.start()]):
            continue
        return True
    return False


_OTP_WORD = re.compile(r"\b(?:otp|one[- ]time (?:password|code|pin)|verification code|login code|security code)\b|ओटीपी", re.I)


def reason(kind, text, sender):
    """Why a personal-mobile sender raises this text message, or None.

    "alert": a debit or OTP alert, which always comes from a header. "request": an OTP, PIN or
    KYC ask. "identity": a bank, government, courier or telecom identity claimed to the reader
    (a "dear customer" greeting, or "your account/card/parcel/SIM ..."). A chat that only mentions
    a bank, and a forwarded warning with no ask, does not count.
    """
    if kind not in TEXT_KINDS or not text:
        return None
    p = parse(sender)
    if not p or p["kind"] != "mobile":
        return None
    a = mech.analyze(text)
    harm = {n for n, _ in a["harm"]}
    t = a["text"]
    # The OTP word itself is required: mech's OTP-note reading also covers "the door code is 1234".
    if (a["otp_note"] and (_OTP_WORD.search(t) or _code_for_institution(t))) or (
            (a["receipt"] or _DEBIT.search(t)) and not _CHATTY.search(t) and (
                _ALERT_MARK.search(t) or _DEAR.search(t) or
                (_DEBIT.search(t) and _YOUR_ACCOUNT.search(t) and _INSTITUTION.search(t)))):
        return "alert"
    if harm & _REQUEST_HARM or _kyc_ask(t):
        return "request"
    advisory = not harm and (a["protective"] or a.get("awareness") or a.get("report") or a.get("advice"))
    if advisory:
        return None
    if _INSTITUTION.search(t) and (_DEAR.search(t) or (_YOUR_ACCOUNT.search(t) and _NOTICE_CUE.search(t))):
        return "identity"
    return None


_RANK = {0: 0, "uncertain": 1, 1: 2}


def rank(label):
    return _RANK[label]


def apply(label, score, evidence, why):
    """Raise a result for a reason from reason(); with no reason the inputs come back unchanged."""
    if not why:
        return label, score, evidence
    ev = [SENDER_LINE] + [e for e in (evidence or []) if e != SENDER_LINE]
    if label == 1:
        return 1, score, ev
    return "uncertain", max(float(score), 0.5), ev


_CALL_BANK = re.compile(
    r"\b(?:bank|sbi|hdfc|icici|axis|kotak|pnb|canara|baroda|rbi|reserve bank|credit card|debit card|"
    r"net ?banking)\b|बैंक", re.I)


def call_note(transcript):
    """The 1600-series advisory for a call that mentions a bank, or None. Never changes a verdict."""
    if transcript and _CALL_BANK.search(transcript):
        return NOTE_1600
    return None
