"""Offline UPI QR and upi:// intent scam detector.

Parses NPCI UPI QR payloads and deep links (upi://pay, upi://collect, upi://mandate,
and major Indian PSP intent schemes) without any network access or third-party packages.
Produces structured, grounded evidence for the verdict banner and on-device Llama explainer.

Design priority: high recall on Indian UPI QR scams (PIN-to-receive / collect trick,
refund/cashback/KYC lures, brand impersonation & lookalike VPAs, AutoPay mandate traps,
amount tampering, merchant code anomalies, unknown/spoofed PSP handles) while keeping
false positives near zero on genuine Indian P2P and merchant QRs.
"""
from __future__ import annotations

import json
import math
import re
import sys
import unicodedata
from dataclasses import dataclass, replace
from urllib.parse import parse_qsl, unquote, unquote_plus, urlparse

from . import rules

MAX_UPI_LEN = 4096
_HIDDEN_RE = re.compile(r"[\u200b-\u200f\u2060\ufeff\u00ad]")
# ZWJ/ZWNJ are part of Malayalam chillu and Urdu/Indic names; they only hide something next to ASCII text.
_SUSPICIOUS_HIDDEN_RE = re.compile(
    r"[\u200b\u200e\u200f\u2060\ufeff\u00ad]|(?<=[\x21-\x7e])[\u200c\u200d]|[\u200c\u200d](?=[\x21-\x7e])")

# Recognized URI schemes for UPI QR codes and Indian PSP intent links.
_UPI_SCHEME_RE = re.compile(
    r"^(?:upi|upiglobal|tez|gpay|phonepe|paytmmp|bhim|credpay|amazonpay)://",
    re.I,
)
_INTENT_UPI_RE = re.compile(r"^intent://[^\s#]*#Intent;(?:[^;\s]*;)*?scheme=upi(?:;|$)", re.I)
_BARE_QUERY_RE = re.compile(
    r"^(?:[a-z][a-z0-9_]{0,15}=[^&\s]*&)+[a-z][a-z0-9_]{0,15}=[^&\s]*$",
    re.I,
)
_UPI_PARAM_KEYS = frozenset({
    "pa", "pn", "am", "mam", "cu", "tn", "mc", "tr", "tid", "url", "mode",
    "purpose", "orgid", "sign", "ver", "mid", "msid", "mtid", "amrule",
    "recur", "recurvalue", "recurtype", "validitystart", "validityend",
    "block", "rev", "share", "mn", "txntype", "fam", "refurl",
})

# Comprehensive set of legitimate NPCI-approved Indian bank, TPAP, and aggregator PSP handles.
KNOWN_PSP_HANDLES = frozenset({
    # Google Pay
    "okaxis", "okhdfcbank", "okicici", "oksbi",
    "okbizaxis", "okbizicici", "okbizhdfcbank", "okbizsbi",
    # PhonePe
    "ybl", "ibl", "axl",
    # Paytm (legacy + 2024+ TPAP handles)
    "paytm", "ptyes", "ptaxis", "pthdfc", "ptsbi", "ptybl", "paytmqr",
    # BHIM / NPCI
    "upi",
    # Amazon Pay
    "apl", "yapl", "rapl",
    # WhatsApp Pay
    "waaxis", "wahdfcbank", "waicici", "wasbi",
    # Major TPAPs & fintechs
    "axisb", "yescred", "icicicred", "superyes", "naviaxis", "fkaxis",
    "sliceaxis", "slice", "jupiteraxis", "fifederal", "fam", "yesfam",
    "tapicici", "yesg", "ikwik", "freecharge", "fbpe", "bharatpe", "yespay",
    "yescurie", "jio", "jiopay", "airtel", "mairtel", "airtelpaymentsbank",
    "abfspay", "bajaj", "bajajpay", "timecosmos", "zomato", "payzapp", "pz",
    "goaxb", "myicici", "kmbl", "kmb", "kotak", "pingpay", "postbank", "ippb",
    "indie", "yespop", "yespopclub", "bpunity", "niyoicici", "shriram",
    # Public, private, small finance & foreign banks
    "sbi", "sbiepay", "sbipay", "yono",
    "hdfcbank", "hdfcbankjd", "hdfc", "hdfcmerchant",
    "icici", "icicibank", "eazypay", "pockets", "imobile", "icicimerchant",
    "axisbank", "axb", "axisgo", "axismerchant",
    "barodampay", "barodapay", "bob", "bobpay",
    "boi", "boipay", "cnrb", "canara", "canarabank",
    "pnb", "pnbpay", "uboi", "ubi", "unionbank", "unionbankofindia",
    "uco", "ucopay", "indianbank", "indianbk", "iob", "iobpay",
    "cbin", "centralbank", "mahb", "bom", "psb", "psbpay",
    "idbi", "ibkl", "idfc", "idfcbank", "idfcfirst", "cmsidfc",
    "indus", "indusind", "yesbank", "yesbankltd",
    "federal", "fbl", "federalbank", "rbl", "rblbank",
    "bandhan", "bandhanbank", "aubank", "equitas", "esaf", "fino",
    "ujjivan", "jana", "suryoday", "utkarshbank", "shivalik", "unity",
    "nsdl", "nsdlpb", "kvb", "kvbl", "sib", "sibm", "cub", "kbl", "kbl052",
    "tmb", "dcb", "dlb", "csbpay", "jkb", "jsb", "tjsb", "srcb",
    "dbs", "hsbc", "sc", "scb", "scmobile", "citi", "citigold",
    "allbank", "allahabadbank", "andb", "corp", "denabank", "obc",
    "syndicate", "united", "utbi", "vijayabank", "kaypay", "lime", "paywiz",
    "mbs", "sbimerchant",
    # Payment gateways / POS merchant handles
    "payu", "razorpay", "rzp", "cashfree", "billdesk", "ccavenue", "juspay",
    "pinelabs", "mswipe", "ezetap", "setu", "paysharp", "plural",
    # SEBI verified base handle
    "valid",
})

# SEBI Oct 2025 "@valid<bank>" verified intermediary handles.
_SEBI_VALID_HANDLE_RE = re.compile(
    r"^valid(?:hdfc|hdfcbank|icici|axis|sbi|kotak|yes|yesbank|pnb|bob|"
    r"idfc|indus|federal|rbl|canara|boi|ubi|iob|uco|hsbc|dbs|scb|citi|aubank|bandhan)$"
)

# Handles that imitate brands, regulators, or scam lures instead of real NPCI bank PSPs.
SPOOFED_PSP_HANDLES = frozenset({
    "rbi", "npci", "gov", "govin", "india", "police", "cbi", "customs",
    "uidai", "aadhaar", "epfo", "incometax", "itd", "sebi", "trai", "irctc",
    "indiapost", "amazon", "amazonpay", "flipkart", "netflix", "google",
    "phonepe", "gpay", "whatsapp", "refund", "cashback", "kyc", "verify",
    "support", "helpdesk", "customercare", "official", "claim", "prize",
    "lottery", "winner", "bonus", "reward", "secure", "alert", "billing",
    "electricity", "bses", "bescom", "msedcl", "uppcl", "pay", "upiid",
    "bank", "card", "otp", "pin", "free", "olx", "army",
})

# Digit-swap lookalikes of major PSP handles (e.g., okax1s, 0kicici, yb1, pay7m).
_PSP_CORE = ("okaxis", "okhdfcbank", "okicici", "oksbi", "ybl", "ibl", "axl",
             "paytm", "ptyes", "ptaxis", "pthdfc", "ptsbi", "hdfcbank", "icici", "axisbank", "sbi")

# Known Indian merchant QR VPA prefixes (opaque IDs that legitimately don't spell the shop name).
_MERCHANT_VPA_PREFIX_RE = re.compile(
    r"^(?:q\d{5,}|paytmqr[a-z0-9]+|paytm\.s[a-z0-9]+|bharatpe\.[a-z0-9]+|"
    r"gpay-[a-z0-9]+|vyapar\.[a-z0-9]+|mab\.[a-z0-9]+|pos\.[a-z0-9]+|"
    r"ezetap\.[a-z0-9]+|mswipe\.[a-z0-9]+|pinelabs\.[a-z0-9]+|"
    r"razorpay\.[a-z0-9]+|cf\.[a-z0-9]+|mer\.[a-z0-9]+|epos\.[a-z0-9]+)$",
    re.I,
)
_MOBILE_VPA_RE = re.compile(r"^(?:(?:\+?91)?[6-9]\d{9})$")

# Major Indian brands/institutions commonly impersonated in UPI QR scams.
# Each entry: (canonical_label, category, regex_for_pn, accepted_vpa_tokens)
_IMPERSONATED_ENTITIES = [
    ("SBI", "bank", r"\b(?:sbi|state\s+bank(?:\s+of\s+india)?|yono)\b", ("sbi", "yono", "sbiepay")),
    ("HDFC Bank", "bank", r"\b(?:hdfc(?:\s+bank)?)\b", ("hdfc", "payzapp")),
    ("ICICI Bank", "bank", r"\b(?:icici(?:\s+bank)?|imobile)\b", ("icici", "imobile", "pockets")),
    ("Axis Bank", "bank", r"\b(?:axis\s+bank)\b", ("axis", "axb")),
    ("Kotak Bank", "bank", r"\b(?:kotak\s+(?:mahindra|bank|securities|life|general|811))\b|^\s*kotak\s*$", ("kotak", "kmbl", "kmb")),
    ("PNB", "bank", r"\b(?:pnb|punjab\s+national\s+bank)\b", ("pnb",)),
    ("RBI", "gov", r"\b(?:rbi|reserve\s+bank(?:\s+of\s+india)?)\b", ("rbi",)),
    ("NPCI", "gov", r"\b(?:npci|bhim\s+upi)\b", ("npci", "bhim")),
    ("SEBI", "gov", r"\b(?:sebi)\b", ("sebi",)),
    ("TRAI", "gov", r"\b(?:trai)\b", ("trai",)),
    ("UIDAI / Aadhaar", "gov", r"\b(?:uidai|aadhaar|aadhar)\b", ("uidai", "aadhaar")),
    ("Income Tax", "gov", r"\b(?:income\s+tax|itr\s+dept|e-?filing)\b", ("incometax", "nsdl", "tin", "cbdt")),
    ("EPFO", "gov", r"\b(?:epfo|pf\s+office)\b", ("epfo",)),
    ("India Post", "gov", r"\b(?:india\s+post|indiapost|speed\s+post)\b", ("indiapost", "ippb", "post")),
    ("Police / Cyber Cell", "gov", r"\b(?:police|cyber\s*(?:cell|crime|police)|cbi|ncb|customs\s+(?:department|dept|office|officer)|"
     r"(?:high|supreme|district|sessions|family)\s+court|court\s+(?:fine|summons|order|warrant)|customs)\b"
     r"|(?<!food\s)(?<!tennis\s)(?<!badminton\s)(?<!basketball\s)(?<!food-)\bcourt\b(?!\s*yard)", ()),
    ("Amazon", "ecom", r"\b(?:amazon(?:\s+pay|\s+india)?)\b", ("amazon", "amzn", "apl")),
    ("Flipkart", "ecom", r"\b(?:flipkart)\b", ("flipkart", "fkrt", "fk")),
    ("IRCTC", "travel", r"\b(?:irctc)\b", ("irctc",)),
    ("Paytm", "tpap", r"\b(?:paytm)\b", ("paytm",)),
    ("PhonePe", "tpap", r"\b(?:phonepe)\b", ("phonepe", "pe")),
    ("Google Pay", "tpap", r"\b(?:google\s*pay|gpay)\b", ("gpay", "google", "tez")),
    ("BSES", "utility", r"\b(?:bses(?:\s+rajdhani|\s+yamuna)?)\b", ("bses", "bbps")),
    ("BESCOM", "utility", r"\b(?:bescom)\b", ("bescom", "bbps")),
    ("MSEDCL", "utility", r"\b(?:msedcl|mahadiscom)\b", ("msedcl", "mahadiscom", "bbps")),
    ("UPPCL", "utility", r"\b(?:uppcl)\b", ("uppcl", "bbps")),
    ("Tata Power", "utility", r"\b(?:tata\s+power)\b", ("tatapower", "tpddl", "bbps")),
    ("Airtel", "telecom", r"\b(?:airtel)\b", ("airtel",)),
    ("Jio", "telecom", r"\b(?:jio(?:\s+mart|\s+fiber|\s+pay)?)\b", ("jio", "reliance")),
    ("Swiggy", "ecom", r"\b(?:swiggy)\b", ("swiggy",)),
    ("Zomato", "ecom", r"\b(?:zomato)\b", ("zomato",)),
    ("Netflix", "ecom", r"\b(?:netflix)\b", ("netflix",)),
    ("LIC", "bank", r"\b(?:lic(?:\s+of\s+india)?)\b", ("lic",)),
]

# Official/support/scam-desk words in payee name (`pn`) that make a personal VPA or P2P MCC suspicious.
_OFFICIAL_DESK_RE = re.compile(
    r"\b(?:customer\s*(?:care|support|service)|support\s*(?:desk|team)|claims?\s*(?:department|dept|desk)|"
    r"customs\s*(?:clearance|department|dept|office)|help\s*desk|helpline|refund|cashback|"
    r"kyc|verif(?:y|ication)|official|disconnection|prize|lottery|winner|"
    r"billing\s*desk|care\s*team|fraud\s*team|security\s*team)\b",
    re.I,
)
# Generic words ("SG Tech Support", "XYZ Travel Desk", "Cell City Mobiles", "Quick Claim Assist") are
# ordinary small-business names; they read as an official desk only next to a claimed organisation.
_OFFICIAL_DESK_WEAK_RE = re.compile(
    r"\b(?:support|desk|department|dept|officer|cell|recovery|claim|clearance)\b",
    re.I,
)
# Plain cashback / money-back promo wording that real merchant QRs carry ("5% cashback on purchase").
_MERCHANT_PROMO_RE = re.compile(r"\b(?:get\s+)?(?:\d+\s*%\s*)?(?:cash\s*back|cashback|money\s*back)\b|कैशबैक", re.I)
_HARD_FEE_RE = re.compile(
    r"\b(?:job|task|prize|lottery|parcel|kyc|withdrawal|payout|bonus|refund|work\s*from\s*home|registration)\b", re.I)
_URL_SCAM_WORD_RE = re.compile(r"refund|kyc|cashback|claim|prize|reward|help|support|care|verif|secure|login|update|offer")
# A promo stops being plain promo when it asks for a payment or action to receive the money.
# Routine on a merchant QR ("Courier charge"), the classic parcel/customs scam on a personal one.
_PERSONAL_PARCEL_FEE_RE = re.compile(
    r"\b(?:customs|parcel|courier|package|shipment)\b[^.;!?।\n]{0,30}\b(?:fee|charge|duty|clearance|release)\b", re.I)
# Group companies carry the bank's name legitimately (ICICI Lombard, PNB MetLife, SBI Life, HDFC Ergo).
_GROUP_COMPANY_RE = re.compile(
    r"\b(?:lombard|prudential|metlife|ergo|life|general\s+insurance|insurance|securities|mutual\s+fund|amc|"
    r"housing\s+finance|asset\s+management|cards?|capital)\b", re.I)
# Payment aggregators settle for big brands on their own handles (Netflix via Razorpay).
_AGGREGATOR_HANDLE_RE = re.compile(r"razorpay|rzp|payu|cashfree|ccavenue|billdesk|juspay|pinelabs|easebuzz|instamojo")
# Agent/registration words that, next to a bank or government name on a personal mobile UPI ID, still need a check.
_AGENT_WORD_RE = re.compile(r"\b(?:agents?|registered|associates|consultants?|advis[eo]rs?)\b", re.I)
# "Pay Rs 500 and receive 5% cashback on your purchase" is a purchase promo; "Pay Rs 1 to receive cashback" is not.
_PROMO_PURCHASE_RE = re.compile(r"\d+\s*%|\bon\s+(?:your\s+|the\s+|this\s+)?(?:purchase|order|bill|shopping|payment)\b", re.I)
_PROMO_PURPOSE_RE = re.compile(r"\bto\s+(?:receive|claim|get|unlock)\b", re.I)
_PROMO_BREAKER_RE = re.compile(
    r"\b(?:receive|claim|credited?\s+to)\b|\bpay\s*(?:rs\.?|inr|₹)?\s*\d", re.I)
# Small local shops legitimately name a brand they resell ("Airtel Recharge Shop", "Jio Point").
_LOCAL_SHOP_RE = re.compile(
    r"\b(?:shop|store|kirana|mart|point|corner|traders|enterprises|agency|"
    r"recharge|stall|bakery|medicals|pharmacy|emporium|hardware|centre|center|"
    # Businesses that name an agency or brand they serve ("Sharma Income Tax Consultants",
    # "SEBI Registered Adviser", "LIC Agent R Sharma", "Speed Post Courier", "RBI Grade B Coaching").
    r"consultants?|consultancy|advis[eo]rs?|associates|coaching|classes|academy|institute|tutorials?|"
    r"agents?|courier|couriers|forwarders?|logistics|registered|chartered|practitioners?|"
    r"house\s+agents?)\b",
    re.I,
)

# Brands checked for digit-swap imitation inside `vpa_user` (e.g., amaz0n, sb1, fl1pkart).
_SWAP_BRANDS = (
    "amazon", "flipkart", "paytm", "phonepe", "gpay", "google", "irctc",
    "sbi", "hdfc", "icici", "axis", "kotak", "pnb", "uidai", "aadhaar",
    "incometax", "epfo", "npci", "bhim", "sebi", "trai", "airtel",
    "indiapost", "netflix", "swiggy", "zomato", "bses", "bescom", "msedcl",
    "uppcl", "official", "refund", "cashback",
)
_DIGIT_TO_LETTER = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b"})
_DIGIT_TO_LETTER_ALT = str.maketrans({"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b"})

# Scam-themed keywords inside VPA username (`pa` local-part).
_VPA_SCAM_TOKEN_RE = re.compile(
    r"(?:^|[._\-0-9])("
    r"refund|cashback|kyc|unblock|reactivat\w*|claim|lottery|winner|prize|jackpot|"
    r"customercare|custcare|helpdesk|helpline|customs|police|digitalarrest|"
    r"olxbuyer|armyofficer|disconnection|bijlicut|subsidy|pmkisan|itrefund|"
    r"taxrefund|bonusclaim|rewardclaim|receivemoney|payreceive|verif(?:y|ication)"
    r")(?:$|[._\-0-9])|"
    r"(?:sbi|hdfc|icici|axis|kotak|pnb|rbi|npci|uidai|irctc|amazon|amzn|flipkart|"
    r"paytm|phonepe|gpay|google|airtel|jio|bses|bescom|msedcl|uppcl|indiapost|epfo)"
    r"[._\-]?(?:refund|cashback|kyc|care|support|help|helpdesk|verify|official|claim|desk|bill|cut)",
    re.I,
)

# Receive-money / PIN-to-receive / collect lure patterns (English, Hinglish, Devanagari).
_PIN_TO_RECEIVE_RE = re.compile(
    r"(?:enter|type|put|input|give|scan|submit|confirm|dal\w*|daal\w*|bhar\w*)"
    r"[^.;!?।\n]{0,35}(?:upi\s*)?(?:pin|mpin|पिन)"
    r"[^.;!?।\n]{0,35}(?:receive|get|credit|claim|refund|cashback|money|amount|paisa|paise|pane|paane|milenge|पाने|प्राप्त|रिफंड|कैशबैक|पैसे)"
    r"|(?:receive|get|claim|credit|refund|cashback|paise\s*pa+ne|paisa\s*pa+ne|पाने|प्राप्त)"
    r"[^.;!?।\n]{0,35}(?:enter|using|with|via|by|dal\w*|daal\w*|डाल\w*)"
    r"[^.;!?।\n]{0,20}(?:upi\s*)?(?:pin|mpin|पिन)"
    r"|scan(?:(?!\bpay)[^.;!?।\n]){0,25}(?:to\s+)?(?:receive\b(?!\s+(?:(?:the|your|a)\s+)?(?:payment\s+)?(?:receipt|confirmation|details|link|sms|alert|bill|invoice))|"
    r"get\s+paid\b|(?:get|claim|credit|collect)\s+(?:(?:your|the|a|an)\s+)?(?:money|payment|amount|refund|cashback|cash|paisa|paise|funds?|prize|reward|gift|bonus|rs\.?|inr|₹)|paise\s*pa+ne|paisa\s*pa+ne|पैसे\s*पाने|प्राप्त\s*करने)"
    r"|(?:approve|accept|confirm)[^.;!?।\n]{0,25}(?:to\s+)?(?:receive|claim|credit|refund|cashback|"
    r"get\s+(?:(?:your|the)\s+)?(?:money|payment|amount|refund|cashback|paisa|paise|rs\.?|₹))"
    # Hindi grammar puts the goal before the action: "पैसे पाने के लिए स्कैन करें", "UPI PIN डालकर राशि प्राप्त करें".
    r"|(?:upi\s*)?(?:pin|mpin|पिन)\s*(?:डाल\w*|दर्ज\s*कर\w*|daal\w*|dal\w*|enter\w*)[^।;!?\n]{0,30}"
    r"(?:पैसे|पैसा|प्राप्त\s*कर|पाने|मिलेंगे|रिफंड|कैशबैक|paisa|paise|refund|cashback|receive)"
    r"|(?:पैसे|पैसा|राशि|रिफंड|कैशबैक|पेमेंट)\s*(?:पाने|प्राप्त\s*करने|लेने)[^।;!?\n]{0,25}(?:स्कैन|scan|पिन|pin)"
    r"|(?:paisa|paise|refund|cashback|payment)\s*(?:milne|pane|paane|lene)\s*(?:ke|k)\s*(?:liye|lie)[^.;!?\n]{0,20}(?:scan|pin)"
    r"|scan[^.;!?\n]{0,20}(?:paisa|paise|refund|cashback)\s*(?:pa+o|pa\s*lo|lo|milega|milenge)"
    r"|पिन\s*(?:डाल|दर्ज)[^।;!?\n]{0,25}(?:पैसे|राशि|रिफंड|कैशबैक|प्राप्त|मिलेंगे)",
    re.I,
)

# Refund / cashback / prize / incoming-payment claim inside a debit QR's `tn` or `pn`.
_RECEIVE_LURE_RE = re.compile(
    r"\b(?:refund|cash\s*back|cashback|money\s*back|"
    r"receive\s+(?:the\s+|your\s+)?(?:money|payment|amount|funds?|cash|reward|gift|prize|bonus)(?!\s*(?:receipt|confirmation|details|link|sms|alert))|"
    r"receive\s*(?:rs\.?|inr|₹)?\s*\d[\d,]*(?![\d,])(?!\s*%)|payment\s+receive|pay\s+receive|"
    # "Get Rs 100 off", "get Rs 1299 worth of products", "you get Rs 100 change" are discounts, not credits.
    r"get\s*(?:rs\.?|inr|₹)\s*\d[\d,]*(?![\d,])(?!\s*(?:off|discount|worth|instant|talktime|change|extra\s+off))|"
    r"pay\s*(?:rs\.?|inr|₹)?\s*\d[\d,]*\s*(?:to|and)\s*(?:get|receive|win)\s*(?:rs\.?|inr|₹)?\s*\d[\d,]*(?![\d,])(?!\s*(?:off|discount|worth|instant|talktime))|"
    r"paise\s*(?:pa+ne|pa+o|milne|milenge|receive)|paisa\s*(?:pa+ne|pa+o|milne|milega|receive)|"
    r"credit\s+(?:to|in|into)\s+(?:your\s+)?(?:account|bank|upi|a/c)|"
    r"(?:instant|order|tax|itr|gst|ticket|bank|amazon|flipkart|paytm|phonepe)\s+refund|"
    r"claim\s+(?:your\s+)?(?:prize|reward|refund|cashback|winnings?|lottery|gift)|claim\s+your\s+(?:amount|money|voucher|subsidy)|"
    r"(?<!no\s)claim\s+(?:your\s+)?bonus|"
    r"lottery|lucky\s*draw|jackpot|you\s+won|prize\s*(?:money|claim|win|winner)|winner\s*(?:payout|claim|prize)|"
    r"olx\s*(?:payment|buyer|receive|credit|advance|deal)|army\s*(?:buyer|officer|payment|receive)|"
    r"subsidy\s*(?:credit|receive|claim)|pm\s*kisan\s*(?:claim|receive|credit|payout)|"
    r"salary\s*credit|payout\s*receive|withdrawal\s*credit|credit\s*amount)\b"
    r"|रिफंड|धनवापसी|कैशबैक|इनाम|लॉटरी|पैसे\s*(?:पाएं|पाएँ|पाने|प्राप्त|मिलेंगे|आएंगे|आएँगे)|पैसा\s*(?:पाएं|पाने|मिलेगा)"
    r"|(?:राशि|पेमेंट|भुगतान)\s*प्राप्त\s*कर",
    re.I,
)
_LEGIT_CREDIT_CARD_RE = re.compile(r"\bcredit\s*card\s*(?:bill|payment|due|repayment|emi)\b", re.I)

# KYC / account block / disconnection / authority / secret / upfront-fee threats in `tn` or `pn`.
_KYC_THREAT_RE = re.compile(
    r"\b(?:kyc\s*(?:update|verify|verification|fee|charge|pending|expire[sd]?|block|suspend|reactivat\w*|mandatory)|"
    r"(?:update|complete|verify)\s+(?:your\s+)?kyc|"
    r"(?:pan|aadhaar|aadhar|account|upi|sim|card)\s*(?:verify|verification|update|reactivat\w*|unblock|kyc)\s*(?:fee|charge|now|urgent)?|"
    r"re-?kyc)\b"
    r"|केवाईसी|सत्यापन\s*शुल्क|kyc\s*(?:अपडेट|सत्यापन|वेरिफिकेशन)",
    re.I,
)
_BLOCK_DISCONNECT_RE = re.compile(
    r"\b(?:account|khata|sim|card|electricity|power|bijli|light|meter|connection|upi|number)\b"
    r"[^.;!?।\n]{0,30}\b(?:block\w*|suspend\w*|cut\b|kat\b|disconnect\w*|deactivat\w*|freez\w*|band\b)"
    r"|\b(?:avoid|prevent)\s+(?:disconnection|blocking|suspension|cut[- ]?off|account\s*block)\b"
    r"|(?:बिजली|खाता|सिम|अकाउंट|कनेक्शन)\s*(?:कट|बंद|ब्लॉक|निलंबित)",
    re.I,
)
_AUTHORITY_CUSTOMS_RE = re.compile(
    r"\b(?:police|cbi|ncb|court|warrant|digital\s*arrest|cyber\s*cell|fir)\b"
    r"[^.;!?।\n]{0,30}\b(?:fee|charge|duty|fine|clearance|release|hold|settlement|bail|deposit|penalty|case)\b"
    # "Courier charge" / "Customs duty for shipment" are routine; held/seized/release/penalty wording is the scam.
    r"|\b(?:customs|parcel|courier|package|shipment)\b[^.;!?।\n]{0,30}"
    r"\b(?:held|hold|seized|detained|release|penalty|fine|illegal|drugs|clearance\s+(?:fee|charge))\b"
    r"|\bdigital\s*arrest\b"
    r"|कस्टम\s*शुल्क|पार्सल\s*(?:शुल्क|चार्ज)|डिजिटल\s*अरेस्ट",
    re.I,
)
_UPFRONT_SCAM_FEE_RE = re.compile(
    r"\b(?:loan|job|task|refund|prize|lottery|parcel|kyc|withdrawal|payout|bonus|work\s*from\s*home)\b"
    r"[^.;!?।\n]{0,25}\b(?:processing|registration|verification|activation|unlock|release|security|approval|disbursal|recharge|advance)\s*(?:fee|charge|deposit)\b"
    r"|\b(?:processing|verification|activation|unlock|release|disbursal|approval)\s*(?:fee|charge)\b"
    r"[^.;!?।\n]{0,25}\b(?:loan|job|task|refund|prize|lottery|parcel|kyc|withdrawal|payout|account)\b",
    re.I,
)
_SECRET_ASK_RE = re.compile(
    r"\b(?:enter|share|send|type|give|provide|confirm|submit)\s+(?:your\s+)?(?:upi\s*)?(?:pin|mpin|otp|cvv|password)\b"
    r"|\b(?:upi\s*pin|mpin|otp|cvv)\s+(?:required|needed|mandatory|here)\b",
    re.I,
)
_URGENCY_RE = re.compile(
    r"\b(?:urgent|immediately|pay\s+now|within\s+\d+\s*(?:min|mins|minute|minutes|hr|hrs|hour|hours)|"
    r"tonight|last\s+chance|expire[sd]?\s*(?:today|soon|in\s+\d)|act\s+now|hurry|"
    r"turant|jaldi|abhi\s+pay)\b|तुरंत|जल्दी",
    re.I,
)
_CODE_DISGUISE_RE = re.compile(
    r"\b(?:refund\s*code|verification\s*code|otp\s*code|claim\s*code|secret\s*code|"
    r"enter\s*code|security\s*code)\b",
    re.I,
)

# High-risk MCCs and broad category checks (conservative to avoid false positives on valid shops).
HIGH_RISK_MCCS = {
    "7995": "betting or gambling",
    "5967": "inbound teleservices",
    "6051": "quasi-cash or crypto",
}
_RETAIL_UNRELATED_FOR_OFFICIAL = {
    "5812": "restaurant",
    "5814": "fast food",
    "7230": "salon or beauty shop",
    "7995": "betting or gambling",
    "5921": "liquor store",
    "5967": "inbound teleservices",
}
_MERCHANT_ONLY_MODES = frozenset({"02", "15", "16", "17"})
_THRESHOLD_AMOUNTS = frozenset({9999, 19999, 29999, 39999, 49990, 49999, 99990, 99999})
_HIGH_P2P_AMOUNT = 49000.0
_HIGH_LIMIT_MCCS = frozenset({"6211", "6300", "6012", "6010", "6540", "8062", "8011", "8211", "8220", "8241",
                              "8244", "8249", "8299", "9311", "9399", "9222", "4900", "7011", "4511", "4722"})
_UPI_P2P_CAP = 100000.0
_UPI_MERCHANT_CAP = 500000.0


@dataclass(frozen=True)
class UpiFinding:
    code: str
    severity: str       # "high" | "medium" | "low"
    description: str    # full human-readable evidence line
    compact: str        # short phrase for Llama prompt opening
    field: str = ""     # primary UPI param name ("pa", "pn", "am", "tn", "mc", "url", "action", ...)


_EDGE_NOISE_RE = re.compile(r"^(?:\s|" + _HIDDEN_RE.pattern + r")+|(?:\s|" + _HIDDEN_RE.pattern + r")+$")


def _clean_invisible(text: str) -> tuple[str, bool]:
    cleaned = _HIDDEN_RE.sub("", text)
    return cleaned, bool(_SUSPICIOUS_HIDDEN_RE.search(text))


def is_upi_payload(text: str) -> bool:
    """Return True if *text* is a UPI URI, Indian PSP UPI intent link, or bare UPI QR query."""
    if not isinstance(text, str):
        return False
    raw = _HIDDEN_RE.sub("", text).strip()
    if not raw or len(raw) > MAX_UPI_LEN:
        return False
    if _UPI_SCHEME_RE.match(raw) or _INTENT_UPI_RE.match(raw):
        return True
    if _BARE_QUERY_RE.match(raw):
        pairs = parse_qsl(raw, keep_blank_values=True)
        keys = {k.lower() for k, _ in pairs}
        pa_vals = [v for k, v in pairs if k.lower() == "pa" and "@" in v]
        if pa_vals and len(keys & _UPI_PARAM_KEYS) >= 2:
            return True
    return False


def _decode_param(val: str) -> str:
    """URL-decode a query value cleanly without destroying literal '+' in names unless query-encoded."""
    return unquote_plus(val).strip()


def _parse_amount(val: str) -> float | None:
    if not val:
        return None
    s = val.strip().replace(",", "")
    if not re.fullmatch(r"\d+(?:\.\d{1,4})?", s):
        return None
    try:
        n = float(s)
    except ValueError:
        return None
    return n if math.isfinite(n) else None


def _format_amount(val: str, num: float | None) -> str:
    if num is None:
        return val
    s = val.strip().replace(",", "")
    whole, _, frac = s.partition(".")
    if not frac.strip("0"):
        return f"{int(num):,}"
    return f"{int(whole or 0):,}.{frac}"


_KNOWN_UPI_ACTIONS = frozenset({"pay", "collect", "mandate", "global"})


def _split_uri(s: str) -> tuple[str, str, str, str]:
    """(scheme, host, path, query); never raises on malformed authorities like '[broken'."""
    try:
        p = urlparse(s)
        return p.scheme, p.netloc, p.path, p.query
    except ValueError:
        scheme, _, rest = s.partition("://")
        head, _, query = rest.partition("?")
        host, _, path = head.partition("/")
        return scheme, host, path, query


def parse_upi(text: str) -> dict | None:
    """Parse a UPI URI or QR payload offline into normalized fields."""
    if not is_upi_payload(text):
        return None
    # Edge BOMs/zero-width chars are copy-paste noise; only ones inside the payload can hide fields.
    cleaned, had_hidden = _clean_invisible(_EDGE_NOISE_RE.sub("", text))
    cleaned = cleaned.strip()
    scheme = "upi"
    action = "pay"
    query = ""
    unknown_action = False

    if _INTENT_UPI_RE.match(cleaned):
        scheme = "intent"
        before_frag = cleaned.split("#Intent;", 1)[0]
        _s, p_host, p_path, query = _split_uri(before_frag)
        action = (p_host or p_path.strip("/") or "pay").lower()
    elif _UPI_SCHEME_RE.match(cleaned):
        p_scheme, p_host, p_path, query = _split_uri(cleaned)
        scheme = (p_scheme or "upi").lower()
        host = (p_host or "").lower()
        path = p_path.strip("/").lower()
        # Handle both upi://pay?... and tez://upi/pay?... / phonepe://pay?...
        if host in ("pay", "collect", "mandate", "global"):
            action = host
        elif path in ("pay", "collect", "mandate", "global"):
            action = path
        elif path.startswith("upi/"):
            action = path.split("/", 1)[1] or "pay"
        else:
            action = host or path or "pay"
    else:
        scheme = "raw"
        action = "pay"
        query = cleaned
    if scheme in ("upi", "intent") and action not in _KNOWN_UPI_ACTIONS:
        unknown_action = True

    raw_pairs = parse_qsl(query, keep_blank_values=True)
    params_multi: dict[str, list[str]] = {}
    params: dict[str, str] = {}
    double_encoded = False
    for raw_k, raw_v in raw_pairs:
        k = raw_k.strip().lower()
        if not k:
            continue
        v = raw_v.strip()
        if re.search(r"%[0-9a-fA-F]{2}", v):
            v2 = unquote(v).strip()
            if v2 != v:
                double_encoded = True
                v = v2
        v_clean = _HIDDEN_RE.sub("", v)
        if v_clean != v:
            if _SUSPICIOUS_HIDDEN_RE.search(v):
                had_hidden = True
            v = v_clean.strip()
        params_multi.setdefault(k, []).append(v)
        if k not in params or (not params[k] and v):
            params[k] = v

    duplicates = {}
    for k, vals in params_multi.items():
        distinct = []
        for item in vals:
            if item and item not in distinct:
                distinct.append(item)
        if len(distinct) > 1:
            duplicates[k] = distinct

    pa = params.get("pa", "")
    vpa_user, vpa_handle = "", ""
    if pa.count("@") == 1:
        vpa_user, vpa_handle = pa.split("@", 1)
    elif "@" in pa:
        vpa_user, vpa_handle = pa.split("@", 1)

    pn = params.get("pn", "")
    am = params.get("am", "")
    mam = params.get("mam", "")
    cu = params.get("cu", "")
    # A second tn must not hide a scam note behind an innocent first one: keep every distinct note.
    tn = " ; ".join(duplicates["tn"]) if "tn" in duplicates else params.get("tn", "")
    mc = params.get("mc", "")
    tr = params.get("tr", "")
    tid = params.get("tid", "")
    mode = params.get("mode", "")
    purpose = params.get("purpose", "")
    ref_url = params.get("url", "") or params.get("refurl", "")
    orgid = params.get("orgid", "")
    sign = params.get("sign", "")
    recur = params.get("recur", "")
    amrule = params.get("amrule", "")
    mn = params.get("mn", "")

    amount_num = _parse_amount(am)
    mam_num = _parse_amount(mam)

    is_mandate = (
        action == "mandate"
        or bool(recur or amrule or params.get("validityend") or params.get("recurvalue"))
    )
    if is_mandate:
        direction = "recurring_mandate"
    elif action == "collect":
        direction = "collect_request"
    else:
        direction = "sends_money"

    valid_merchant_mc = bool(re.fullmatch(r"\d{4}", mc)) and mc != "0000"
    is_merchant_format = valid_merchant_mc or bool(_MERCHANT_VPA_PREFIX_RE.match(vpa_user))

    return {
        "raw": text.strip(),
        "scheme": scheme,
        "action": action,
        "pa": pa,
        "vpa_user": vpa_user,
        "vpa_handle": vpa_handle.lower(),
        "pn": pn,
        "am": am,
        "amount_num": amount_num,
        "mam": mam,
        "mam_num": mam_num,
        "cu": cu,
        "tn": tn,
        "mc": mc,
        "tr": tr,
        "tid": tid,
        "mode": mode,
        "purpose": purpose,
        "url": ref_url,
        "orgid": orgid,
        "sign": sign,
        "recur": recur,
        "amrule": amrule,
        "mn": mn,
        "params": params,
        "params_multi": params_multi,
        "duplicates": duplicates,
        "had_hidden_chars": had_hidden,
        "double_encoded": double_encoded,
        "is_mandate": is_mandate,
        "valid_merchant_mc": valid_merchant_mc,
        "is_merchant_format": is_merchant_format,
        "direction": direction,
        "unknown_action": unknown_action,
    }


def _is_known_psp(handle: str) -> bool:
    h = handle.lower()
    return h in KNOWN_PSP_HANDLES or bool(_SEBI_VALID_HANDLE_RE.fullmatch(h))


def _digit_swap_brand(token: str) -> str | None:
    """Return the brand imitated via digit-for-letter substitution (e.g. amaz0n, sb1), else None."""
    low = token.lower()
    if not any(ch.isdigit() for ch in low):
        return None
    parts = [p for p in re.split(r"[^a-z0-9]+", low) if p]
    for part in parts:
        # Ignore opaque merchant IDs / phone numbers (all digits or trailing numeric IDs like amzn0012345).
        if part.isdigit():
            continue
        stripped = re.sub(r"\d+$", "", part)
        if not any(ch.isdigit() for ch in stripped) and len(stripped) >= 3:
            # Digits only at the very end (e.g., amazon123 or sbi99) are not digit-swaps,
            # EXCEPT short 2-letter + digit tokens like sb1, rb1, j10, vi1.
            if stripped not in ("sb", "rb", "pn", "gp", "ax", "ic", "hd"):
                continue
        for table in (_DIGIT_TO_LETTER, _DIGIT_TO_LETTER_ALT):
            folded = part.translate(table)
            for brand in _SWAP_BRANDS:
                idx = folded.find(brand)
                if idx != -1:
                    orig_slice = part[idx:idx + len(brand)]
                    if orig_slice != brand and any(c.isdigit() for c in orig_slice):
                        return brand
    return None


def _digit_swap_psp(handle: str) -> str | None:
    low = handle.lower()
    if not any(ch.isdigit() for ch in low):
        return None
    for table in (_DIGIT_TO_LETTER, _DIGIT_TO_LETTER_ALT):
        folded = low.translate(table)
        if folded in _PSP_CORE and folded != low:
            return folded
    return None


def _pn_entities(pn: str) -> list[tuple[str, str, tuple[str, ...]]]:
    """Major brands/organisations named in payee name *pn*."""
    found = []
    if not pn:
        return found
    for label, cat, pat, tokens in _IMPERSONATED_ENTITIES:
        if re.search(pat, pn, re.I):
            found.append((label, cat, tokens))
    return found


def _vpa_brand_hits(vpa_user: str) -> list[str]:
    low = vpa_user.lower()
    hits = []
    for label, _cat, _pat, tokens in _IMPERSONATED_ENTITIES:
        for tok in tokens:
            if len(tok) >= 3 and tok in low:
                hits.append(label)
                break
    return hits


def _has_non_ascii(s: str) -> bool:
    return any(ord(c) > 127 for c in s)


def _normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", s or "")).strip()


def analyze_upi(text: str) -> dict:
    """Analyze a UPI QR or upi:// intent payload and return structured verdict & evidence."""
    parsed = parse_upi(text)
    if parsed is None:
        return {
            "is_upi": False,
            "parsed": None,
            "findings": [],
            "label": "uncertain",
            "score": 0.5,
            "summary": None,
            "evidence": ["input is not a valid UPI payment payload"],
            "compact_evidence": ["not a valid UPI payment payload"],
            "scam_type": "a UPI payment QR worth checking",
            "benign_evidence": [],
        }

    findings: list[UpiFinding] = []
    seen_codes: set[str] = set()

    def add(code: str, severity: str, description: str, compact: str, field: str = "") -> None:
        key = f"{code}:{description}"
        if key in seen_codes:
            return
        seen_codes.add(key)
        findings.append(UpiFinding(code, severity, description, compact, field))

    pa = parsed["pa"]
    vpa_user = parsed["vpa_user"]
    vpa_handle = parsed["vpa_handle"]
    pn = _normalize_text(parsed["pn"])
    tn = _normalize_text(parsed["tn"])
    mn = _normalize_text(parsed["mn"])
    am = parsed["am"]
    amount_num = parsed["amount_num"]
    mam = parsed["mam"]
    mam_num = parsed["mam_num"]
    cu = parsed["cu"]
    mc = parsed["mc"]
    action = parsed["action"]
    mode = parsed["mode"]
    ref_url = parsed["url"]
    is_mandate = parsed["is_mandate"]
    valid_mc = parsed["valid_merchant_mc"]
    is_merchant_fmt = parsed["is_merchant_format"]
    is_mobile_vpa = bool(_MOBILE_VPA_RE.fullmatch(vpa_user))
    note_and_name = " ; ".join(part for part in (tn, mn, pn) if part).strip()

    # 1. Hidden/invisible characters or parameter pollution
    if parsed["had_hidden_chars"]:
        pa_tail = re.split(r"pa=", text, flags=re.I)[-1][:40] if re.search(r"pa=", text, re.I) else ""
        sev = "high" if _HIDDEN_RE.search(pa_tail) else "medium"
        add(
            "hidden_chars",
            sev,
            "the UPI payload contains invisible characters that can hide the recipient or amount",
            "invisible characters inside the UPI payload",
            "pa",
        )

    for dup_key in ("am", "pa", "pn", "mc", "cu"):
        if dup_key in parsed["duplicates"]:
            vals = parsed["duplicates"][dup_key][:2]
            add(
                "param_pollution",
                "high",
                f"the UPI payload repeats '{dup_key}' with conflicting values ({vals[0]} vs {vals[1]})",
                f"conflicting duplicate '{dup_key}' values ({vals[0]} vs {vals[1]})",
                dup_key,
            )

    # 2. Prompt injection inside tn / pn / mn / pa, and characters no real UPI ID can hold
    all_values = " ; ".join(v for vals in parsed["params_multi"].values() for v in vals if v)
    if all_values and rules.injection_indicators(all_values):
        add(
            "prompt_injection",
            "high",
            "the UPI payload tries to inject instructions into the assistant",
            "an instruction aimed at the assistant (prompt injection) inside the UPI note",
            "tn",
        )
    if vpa_user and not re.fullmatch(r"[A-Za-z0-9._\-]+", vpa_user):
        add(
            "malformed_vpa",
            "high",
            "the UPI ID contains spaces, quotes or symbols that a real UPI ID cannot have",
            "UPI ID with characters a real UPI ID cannot have",
            "pa",
        )

    # 3. Collect / AutoPay mandate / "scan or enter PIN to receive money" trick
    has_pin_receive = bool(_PIN_TO_RECEIVE_RE.search(note_and_name))
    cleaned_for_lure = _LEGIT_CREDIT_CARD_RE.sub(" ", note_and_name)
    promo_broken = bool(_PROMO_BREAKER_RE.search(cleaned_for_lure)) and (
        bool(_PROMO_PURPOSE_RE.search(cleaned_for_lure)) or not _PROMO_PURCHASE_RE.search(cleaned_for_lure))
    if valid_mc and not _OFFICIAL_DESK_RE.search(pn) and not promo_broken:
        cleaned_for_lure = _MERCHANT_PROMO_RE.sub(" ", cleaned_for_lure)
    has_receive_lure = bool(_RECEIVE_LURE_RE.search(cleaned_for_lure))

    if has_pin_receive:
        add(
            "receive_money_trick",
            "high",
            "asks you to scan or enter your UPI PIN to receive money; paying or approving a UPI request only sends money out of your account",
            "asks to scan or enter a UPI PIN to receive money (a UPI payment only sends money out)",
            "tn",
        )
    elif has_receive_lure:
        add(
            "receive_money_trick",
            "high",
            "promises a refund, cashback, prize or incoming payment, but paying or approving a UPI request only sends money out of your account",
            "promises a refund or incoming payment on a UPI QR that sends money out of your account",
            "tn" if _RECEIVE_LURE_RE.search(_LEGIT_CREDIT_CARD_RE.sub(" ", tn)) else "pn",
        )

    if parsed["unknown_action"]:
        add(
            "unknown_action",
            "medium",
            f"uses an unrecognised UPI action 'upi://{action[:20]}' instead of pay, collect or mandate",
            f"unrecognised UPI action 'upi://{action[:20]}'",
            "action",
        )

    if action == "collect":
        collect_sev = "high" if (am or not valid_mc or has_receive_lure or has_pin_receive) else "medium"
        add(
            "collect_intent",
            collect_sev,
            "uses a upi://collect payment request, commonly abused to trick people into approving debits",
            "uses a upi://collect debit request instead of a standard merchant payment",
            "action",
        )

    if is_mandate:
        risky_mandate = (
            has_pin_receive
            or has_receive_lure
            or bool(_KYC_THREAT_RE.search(note_and_name))
            or bool(_URGENCY_RE.search(note_and_name))
            or not valid_mc
            or (parsed["amrule"].upper() == "MAX" and (amount_num or 0) >= 5000)
        )
        add(
            "mandate_autopay",
            "high" if risky_mandate else "medium",
            "sets up a recurring UPI AutoPay mandate that can debit your account repeatedly"
            + (f" (up to Rs {_format_amount(am, amount_num)})" if am and amount_num is not None else ""),
            "sets up a recurring UPI AutoPay mandate"
            + (f" (up to Rs {_format_amount(am, amount_num)})" if am and amount_num is not None else ""),
            "action",
        )

    # 4. VPA validation, lookalikes, and PSP handles
    psp_known = False
    if not pa or pa.count("@") != 1 or not vpa_user or not vpa_handle:
        add(
            "vpa_malformed",
            "high",
            "the payee UPI ID (pa) is missing or malformed",
            "missing or malformed payee UPI ID",
            "pa",
        )
    else:
        if _has_non_ascii(pa):
            add(
                "vpa_malformed",
                "high",
                f"the UPI ID {pa} mixes in non-Latin characters to imitate a handle",
                f"lookalike UPI ID {pa} with non-Latin characters",
                "pa",
            )
        if "." in vpa_handle or not re.fullmatch(r"[a-z0-9]{2,32}", vpa_handle):
            add(
                "vpa_malformed",
                "high",
                f"the UPI ID {pa} uses an invalid handle '@{vpa_handle}' instead of a valid bank PSP handle",
                f"invalid UPI handle '@{vpa_handle}' in {pa}",
                "pa",
            )
        elif vpa_handle in SPOOFED_PSP_HANDLES:
            add(
                "lookalike_psp",
                "high",
                f"the UPI handle '@{vpa_handle}' imitates an official organisation or lure rather than a real Indian bank PSP",
                f"spoofed UPI handle '@{vpa_handle}' in {pa}",
                "pa",
            )
        else:
            swapped_psp = _digit_swap_psp(vpa_handle)
            if swapped_psp:
                add(
                    "lookalike_psp",
                    "high",
                    f"the UPI handle '@{vpa_handle}' swaps letters for digits to imitate '@{swapped_psp}'",
                    f"lookalike UPI handle '@{vpa_handle}' imitating '@{swapped_psp}'",
                    "pa",
                )
            elif _is_known_psp(vpa_handle):
                psp_known = True
            else:
                add(
                    "unknown_psp_handle",
                    "medium",
                    f"the UPI handle '@{vpa_handle}' is not on the known Indian bank and payment-app PSP list",
                    f"unrecognized UPI handle '@{vpa_handle}' in {pa}",
                    "pa",
                )

        # Digit-swap brand imitation inside VPA local-part
        swapped_brand = _digit_swap_brand(vpa_user)
        if swapped_brand:
            add(
                "lookalike_vpa",
                "high",
                f"the UPI ID {pa} swaps letters for digits to imitate '{swapped_brand}'",
                f"lookalike UPI ID {pa} imitating '{swapped_brand}'",
                "pa",
            )
        # Scam-themed keywords inside VPA local-part (e.g. refund@ybl, sbi.kyc@okaxis)
        elif (m_tok := _VPA_SCAM_TOKEN_RE.search(vpa_user)) and not (
            m_tok.group(1) is None and m_tok.group(0).lower().endswith("bill")
            and any(b in m_tok.group(0).lower() and b in vpa_handle for b in ("sbi", "hdfc", "icici", "axis", "kotak", "pnb"))
        ):
            add(
                "lookalike_vpa",
                "high",
                f"the UPI ID {pa} uses refund, KYC, prize or support-desk wording typical of scam handles",
                f"scam-themed UPI ID {pa}",
                "pa",
            )

    # 5. Payee VPA / Name mismatch
    pn_brands = _pn_entities(pn)
    vpa_brands = _vpa_brand_hits(vpa_user)
    pn_official_desk = bool(_OFFICIAL_DESK_RE.search(pn)) or bool(pn_brands and _OFFICIAL_DESK_WEAK_RE.search(pn))
    pn_local_shop = bool(_LOCAL_SHOP_RE.search(pn)) and not pn_official_desk

    if pn_brands and pa and "@" in pa and not pn_local_shop:
        matched_any_brand = any(
            any(tok in vpa_user.lower() for tok in tokens)
            for _label, _cat, tokens in pn_brands
            if tokens
        )
        primary_brand, primary_cat, _ = pn_brands[0]
        if not matched_any_brand:
            # Brand A in payee name vs Brand B in VPA local-part
            if vpa_brands and primary_brand not in vpa_brands:
                add(
                    "payee_vpa_mismatch",
                    "high",
                    f"payee name '{pn}' claims '{primary_brand}', but the UPI ID {pa} names '{vpa_brands[0]}'",
                    f"payee name '{pn}' conflicts with UPI ID {pa}",
                    "pn",
                )
            elif is_mobile_vpa:
                add(
                    "payee_vpa_mismatch",
                    "high",
                    f"payee name '{pn}' claims '{primary_brand}', but the UPI ID {pa} is a personal mobile number",
                    f"payee name '{pn}' does not match personal mobile UPI ID {pa}",
                    "pn",
                )
            elif pn_official_desk or (not is_merchant_fmt and not valid_mc):
                add(
                    "payee_vpa_mismatch",
                    "high",
                    f"payee name '{pn}' claims '{primary_brand}', which does not match personal UPI ID {pa}",
                    f"payee name '{pn}' does not match UPI ID {pa}",
                    "pn",
                )
            elif valid_mc and not _MERCHANT_VPA_PREFIX_RE.match(vpa_user) and not (primary_cat == "bank" and _GROUP_COMPANY_RE.search(pn)) \
                    and not _AGGREGATOR_HANDLE_RE.search(vpa_handle):
                # Any QR can carry a 4-digit mc, so it cannot vouch for the name. Real brand QRs put the
                # brand in the UPI ID (amazonupi@apl, bsesrajdhani.bbps@hdfcbank); flag for a check.
                add(
                    "payee_vpa_mismatch",
                    "medium",
                    f"payee name '{pn}' claims '{primary_brand}', but the UPI ID {pa} does not carry that name",
                    f"payee name '{pn}' is not reflected in UPI ID {pa}",
                    "pn",
                )
    elif pn_brands and pn_local_shop and is_mobile_vpa and _AGENT_WORD_RE.search(pn) \
            and any(cat in ("bank", "gov") for _, cat, _ in pn_brands):
        add(
            "payee_vpa_mismatch",
            "medium",
            f"payee name '{pn}' names '{pn_brands[0][0]}' but pays a personal mobile-number UPI ID {pa}",
            f"'{pn}' names '{pn_brands[0][0]}' on personal mobile UPI ID {pa}",
            "pn",
        )
    elif pn_official_desk and pa and "@" in pa and (is_mobile_vpa or not is_merchant_fmt):
        add(
            "payee_vpa_mismatch",
            "high",
            f"payee name '{pn}' poses as an official support, KYC or refund desk using personal UPI ID {pa}",
            f"payee name '{pn}' poses as an official desk on personal UPI ID {pa}",
            "pn",
        )

    # 6. Urgency / KYC / disconnection / authority / secret-asking text in `tn` (and `pn`)
    if _SECRET_ASK_RE.search(tn) and not has_pin_receive:
        add(
            "secret_ask_note",
            "high",
            "the transaction note asks for a UPI PIN, OTP, CVV or password",
            "transaction note asks for a UPI PIN or OTP",
            "tn",
        )
    if _KYC_THREAT_RE.search(note_and_name):
        add(
            "kyc_threat_note",
            "high",
            "the UPI payload mentions KYC, PAN or Aadhaar verification to pressure a payment",
            "mentions KYC or verification in a payment QR",
            "tn" if _KYC_THREAT_RE.search(tn) else "pn",
        )
    if _BLOCK_DISCONNECT_RE.search(note_and_name):
        add(
            "block_threat_note",
            "high",
            "the transaction note threatens account blocking or service disconnection",
            "threatens account blocking or disconnection in the payment note",
            "tn",
        )
    if _AUTHORITY_CUSTOMS_RE.search(note_and_name) or (not is_merchant_fmt and _PERSONAL_PARCEL_FEE_RE.search(note_and_name)):
        add(
            "authority_threat_note",
            "high",
            "the transaction note cites customs, parcel release, police or court action to demand money",
            "cites customs, parcel or police threats in the payment note",
            "tn",
        )
    if _UPFRONT_SCAM_FEE_RE.search(note_and_name):
        add(
            "upfront_fee_note",
            # Only a loan/processing charge on a genuine merchant QR (NBFC fee) is weak; job, task, prize,
            # parcel, KYC or payout fees stay high whatever mc the QR carries.
            ("low" if _MERCHANT_VPA_PREFIX_RE.match(vpa_user) else "medium")
            if (valid_mc and not is_mobile_vpa and not pn_official_desk and not _HARD_FEE_RE.search(note_and_name)) else "high",
            "the transaction note asks for an upfront processing, verification or release fee",
            "asks for an upfront processing or verification fee",
            "tn",
        )
    if _URGENCY_RE.search(note_and_name):
        add(
            "urgency_note",
            "medium",
            "the transaction note uses urgent wording to pressure an immediate payment",
            "urgent wording in the payment note",
            "tn",
        )

    # 7. Suspicious embedded reference URL (`url=` or URL in `tn`)
    urls_to_check = []
    if ref_url:
        urls_to_check.append(ref_url)
    for u in rules.find_urls(tn):
        if u not in urls_to_check:
            urls_to_check.append(u)
    for u in urls_to_check:
        uev = rules.url_indicators(u)
        unames = {n for n, _ in uev}
        if "official_domain" in unames:
            continue
        host_l = (rules.host_of(u) or "").lower()
        own_tokens = {t for t in re.split(r"[^a-z0-9]+", vpa_user.lower()) if len(t) >= 4}
        own_tokens |= {tok for _l, _c, toks in pn_brands for tok in toks if len(tok) >= 3}
        label = host_l.split(".")[-3 if host_l.endswith(".co.in") else -2] if "." in host_l else ""
        if unames <= {"brand_lookalike", "brand_mention"} and re.search(r"\.(?:com|in|co\.in|org|net|gov\.in)$", host_l) \
                and label in own_tokens and not _URL_SCAM_WORD_RE.search(label):
            continue
        strong_url = unames & {"brand_lookalike", "digit_swap", "ip_host", "shortener", "punycode", "homoglyph", "hidden_chars", "at_sign"}
        if strong_url:
            host = rules.host_of(u)
            add(
                "suspicious_ref_url",
                "high",
                f"includes a suspicious reference link ({host or u[:48]})",
                f"suspicious reference link ({host or u[:40]})",
                "url",
            )
        elif "risky_tld" in unames:
            host = rules.host_of(u)
            add(
                "suspicious_ref_url",
                "medium",
                f"includes a reference link on a throwaway domain ({host})",
                f"reference link on throwaway domain {host}",
                "url",
            )

    # 8. Amount patterns (`am`, `mam`, `cu`)
    if cu and cu.upper() != "INR":
        add(
            "currency_anomaly",
            "medium",
            f"the currency '{cu}' is not INR, which is unusual for domestic Indian UPI",
            f"non-INR currency '{cu}'",
            "cu",
        )

    if am:
        if amount_num is None:
            add(
                "amount_malformed",
                "medium",
                f"the pre-filled amount '{am}' is malformed",
                f"malformed pre-filled amount '{am}'",
                "am",
            )
        else:
            amt_str = _format_amount(am, amount_num)
            if has_pin_receive or has_receive_lure:
                add(
                    "debit_on_receive_lure",
                    "high",
                    f"pre-fills Rs {amt_str} to debit from your account despite claiming a refund or incoming payment",
                    f"pre-fills Rs {amt_str} debit despite claiming a refund or incoming payment",
                    "am",
                )
            if _CODE_DISGUISE_RE.search(tn) and 1000 <= amount_num <= 999999 and amount_num == int(amount_num):
                add(
                    "code_as_amount",
                    "high",
                    f"pre-fills Rs {amt_str} alongside code or verification wording — scammers disguise debit amounts as codes",
                    f"disguises a Rs {amt_str} debit as a verification or refund code",
                    "am",
                )
            if not is_merchant_fmt and amount_num > _UPI_P2P_CAP:
                add(
                    "amount_above_cap",
                    "medium",
                    f"pre-fills Rs {amt_str}, above the standard Rs 1,00,000 UPI person-to-person limit",
                    f"pre-fills Rs {amt_str} above the Rs 1,00,000 P2P limit",
                    "am",
                )
            elif is_mobile_vpa and amount_num > _UPI_P2P_CAP:
                add(
                    "amount_above_cap",
                    "medium",
                    f"pre-fills Rs {amt_str} to a personal mobile-number UPI ID, above the standard Rs 1,00,000 person-to-person limit",
                    f"pre-fills Rs {amt_str} to a personal UPI ID above the Rs 1,00,000 P2P limit",
                    "am",
                )
            elif valid_mc and amount_num > _UPI_MERCHANT_CAP and mc not in _HIGH_LIMIT_MCCS:
                add(
                    "amount_above_cap",
                    "medium",
                    f"pre-fills Rs {amt_str}, far above normal UPI per-payment limits",
                    f"pre-fills Rs {amt_str}, far above normal UPI limits",
                    "am",
                )
            elif not is_merchant_fmt and (amount_num >= _HIGH_P2P_AMOUNT or int(amount_num) in {49990, 49999, 99990, 99999}):
                add(
                    "high_p2p_amount",
                    "medium",
                    f"pre-fills a high amount (Rs {amt_str}) on an unverified personal UPI QR",
                    f"pre-fills a high amount (Rs {amt_str}) on an unverified personal QR",
                    "am",
                )
            elif amount_num == int(amount_num) and int(amount_num) in _THRESHOLD_AMOUNTS and not valid_mc and findings:
                add(
                    "threshold_amount",
                    "low",
                    f"pre-fills Rs {amt_str}, a common threshold-hugging scam amount",
                    f"threshold-hugging pre-filled amount of Rs {amt_str}",
                    "am",
                )
            if 0 < amount_num <= 10 and (is_mandate or _KYC_THREAT_RE.search(note_and_name) or has_receive_lure):
                add(
                    "micro_verify_amount",
                    "low",
                    f"uses a small Rs {amt_str} amount alongside KYC, refund or AutoPay wording",
                    f"small Rs {amt_str} test amount with KYC, refund or AutoPay wording",
                    "am",
                )

    if mam:
        if mam_num is None:
            add(
                "amount_malformed",
                "medium",
                f"the minimum amount '{mam}' is malformed",
                f"malformed minimum amount '{mam}'",
                "mam",
            )
        else:
            if amount_num is not None and mam_num > amount_num:
                add(
                    "mam_exceeds_am",
                    "medium",
                    f"minimum amount (Rs {_format_amount(mam, mam_num)}) exceeds the listed amount (Rs {_format_amount(am, amount_num)})",
                    f"minimum amount exceeds listed amount",
                    "mam",
                )
            elif not is_merchant_fmt and mam_num >= 10000:
                add(
                    "high_min_amount",
                    "medium",
                    f"sets a high minimum payment of Rs {_format_amount(mam, mam_num)} on a personal UPI QR",
                    f"high minimum payment of Rs {_format_amount(mam, mam_num)} on a personal QR",
                    "mam",
                )

    # 9. Merchant code (`mc`) anomalies
    if mc:
        if not re.fullmatch(r"\d{4}", mc):
            add(
                "mc_malformed",
                "medium",
                f"merchant category code '{mc}' is malformed (expected a 4-digit MCC)",
                f"malformed merchant code '{mc}'",
                "mc",
            )
        elif mc == "0000":
            if parsed["orgid"] or parsed["sign"] or mode in _MERCHANT_ONLY_MODES or parsed["params"].get("mid"):
                add(
                    "mc_p2p_with_merchant_fields",
                    # Low: PhonePe/Paytm small-merchant static QRs legitimately carry mc=0000 + mode=02.
                    "low",
                    "includes merchant QR metadata alongside P2P merchant code 0000",
                    "merchant QR metadata paired with P2P code 0000",
                    "mc",
                )
            if pn_official_desk or (pn_brands and not pn_local_shop):
                add(
                    "mc_p2p_for_brand",
                    "medium",
                    f"uses personal P2P merchant code 0000 despite claiming '{pn}'",
                    f"personal P2P code 0000 for claimed organisation '{pn}'",
                    "mc",
                )
        else:
            if mc in HIGH_RISK_MCCS:
                mcc_label = HIGH_RISK_MCCS[mc]
                mismatch = bool(pn_brands or pn_official_desk or _KYC_THREAT_RE.search(note_and_name) or has_receive_lure)
                add(
                    "mc_high_risk",
                    "high" if mismatch else "medium",
                    f"merchant code {mc} ({mcc_label}) does not match the stated payee or note"
                    if mismatch else f"merchant code {mc} belongs to a high-risk category ({mcc_label})",
                    f"high-risk merchant code {mc} ({mcc_label})",
                    "mc",
                )
            elif mc in _RETAIL_UNRELATED_FOR_OFFICIAL and any(cat in ("bank", "gov", "utility") for _, cat, _ in pn_brands):
                mcc_label = _RETAIL_UNRELATED_FOR_OFFICIAL[mc]
                # A bank/govt/utility name on a restaurant/salon/liquor code is odd; when the UPI ID
                # also lacks the claimed brand, nothing on the QR backs the claim, so escalate.
                vpa_backs_brand = any(
                    tok in vpa_user.lower() for _l, cat, tokens in pn_brands
                    if cat in ("bank", "gov", "utility") for tok in tokens
                )
                add(
                    "mc_category_mismatch",
                    "medium" if vpa_backs_brand else "high",
                    f"merchant code {mc} ({mcc_label}) does not match claimed organisation '{pn}'",
                    f"merchant code {mc} ({mcc_label}) mismatches '{pn}'",
                    "mc",
                )
    elif (pn_brands or pn_official_desk) and not is_merchant_fmt and not pn_local_shop and not (
        not pn_official_desk and any(tok in vpa_user.lower() for _l, _c, toks in pn_brands for tok in toks)
    ):
        # Claiming a bank/govt/utility/official desk with no merchant code at all
        if pn_official_desk or any(cat in ("bank", "gov", "utility") for _, cat, _ in pn_brands):
            add(
                "mc_missing_for_org",
                "medium",
                f"has no merchant category code (mc) despite claiming '{pn}'",
                f"no merchant code despite claiming '{pn}'",
                "mc",
            )

    # Urgent wording ("delivery within 24 hours", "table booking tonight") is routine on its own;
    # it only adds weight next to another risk signal.
    if not any(f.severity != "low" and f.code != "urgency_note" for f in findings):
        findings = [replace(f, severity="low") if f.code == "urgency_note" else f for f in findings]

    # Order findings: high first, then medium, then low.
    rank = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda f: rank[f.severity])

    n_high = sum(1 for f in findings if f.severity == "high")
    n_med = sum(1 for f in findings if f.severity == "medium")
    n_low = sum(1 for f in findings if f.severity == "low")

    if n_high >= 1:
        label: int | str = 1
        score = min(0.99, round(0.84 + 0.04 * min(n_high, 3) + 0.02 * min(n_med, 2), 4))
    elif n_med >= 2:
        label = 1
        score = min(0.92, round(0.74 + 0.06 * min(n_med, 3) + 0.02 * n_low, 4))
    elif n_med == 1:
        label = "uncertain"
        score = min(0.58, round(0.48 + 0.04 * n_low, 4))
    else:
        label = 0
        score = round(0.06 if valid_mc and psp_known else 0.10 if psp_known else 0.14, 4)

    benign_lines = _build_benign_evidence(parsed, psp_known)
    evidence = [f.description for f in findings[:6]] if label != 0 else benign_lines
    compact = [f.compact for f in findings[:2]] if label != 0 else benign_lines[:1]

    return {
        "is_upi": True,
        "parsed": parsed,
        "psp_known": psp_known,
        "findings": findings,
        "label": label,
        "score": score,
        "evidence": evidence,
        "compact_evidence": compact,
        "benign_evidence": benign_lines,
        "scam_type": _scam_type_from(findings, label),
        "summary": _build_summary(parsed, psp_known),
    }


def _build_benign_evidence(parsed: dict, psp_known: bool) -> list[str]:
    """Factual, honest summary lines for a cleared UPI QR (never invents missing fields)."""
    pa = parsed["pa"]
    pn = parsed["pn"]
    mc = parsed["mc"]
    am = parsed["am"]
    amount_num = parsed["amount_num"]
    valid_mc = parsed["valid_merchant_mc"]

    who = f"{pn} ({pa})" if pn else pa
    kind_desc = "merchant UPI QR" if valid_mc else "UPI payment QR"
    handle_part = " on a known UPI handle" if psp_known else ""
    mcc_part = f" (MCC {mc})" if valid_mc else ""
    lines = [f"{kind_desc} for {who}{handle_part}{mcc_part}"]
    if am and amount_num is not None:
        cu = (parsed["cu"] or "INR").upper()
        lines.append(f"pre-fills Rs {_format_amount(am, amount_num)} ({cu}) to send from your account")
    return lines


def _scam_type_from(findings: list[UpiFinding], label: int | str) -> str:
    if label == 0:
        return ""
    codes = {f.code for f in findings}
    if label == 1:
        if "mandate_autopay" in codes:
            # Mandate advice (review and cancel unknown mandates) also covers a refund lure on a mandate.
            return "a UPI AutoPay mandate scam"
        if "receive_money_trick" in codes or "debit_on_receive_lure" in codes:
            return "a UPI refund or receive-money QR scam"
        if "collect_intent" in codes:
            return "a UPI collect-request QR scam"
        if codes & {"kyc_threat_note", "block_threat_note", "authority_threat_note",
                    "payee_vpa_mismatch", "lookalike_vpa", "lookalike_psp"}:
            return "a UPI KYC or impersonation QR scam"
        return "a UPI QR payment scam"
    if "mandate_autopay" in codes:
        return "a UPI AutoPay mandate to review"
    return "a UPI payment QR worth checking"


def _build_summary(parsed: dict, psp_known: bool) -> dict:
    """Compact parsed details for Android/Web UI display."""
    am = parsed["am"]
    amount_num = parsed["amount_num"]
    direction = parsed["direction"]
    intent_label = {
        "sends_money": "Sends money from your account",
        "collect_request": "Collect payment request (debits your account)",
        "recurring_mandate": "Recurring UPI AutoPay mandate",
    }[direction]
    return {
        "scheme": parsed["scheme"],
        "action": parsed["action"],
        "payee_vpa": parsed["pa"],
        "payee_name": parsed["pn"],
        "psp_handle": parsed["vpa_handle"],
        "psp_known": psp_known,
        "amount": _format_amount(am, amount_num) if am else "",
        "currency": (parsed["cu"] or "INR").upper() if parsed["cu"] else "INR",
        "note": parsed["tn"],
        "merchant_code": parsed["mc"],
        "is_merchant": parsed["is_merchant_format"],
        "direction": direction,
        "intent_label": intent_label,
    }


def classify(text: str) -> tuple[int | str, float, list[str]]:
    """Detector contract: returns (label, score, evidence)."""
    res = analyze_upi(text)
    return res["label"], res["score"], res["evidence"]


def predict_upi(payloads: list[str]) -> list[tuple[int | str, float, list[str]]]:
    return [classify(p) for p in payloads]


def compact_evidence_for(text: str, verdict: int | str | None = None) -> list[str]:
    """Short, honest evidence phrases for the Llama prompt opening."""
    res = analyze_upi(text)
    if verdict == 0:
        # Never repeat an overruled risk finding on a NO RISK verdict.
        return res["benign_evidence"][:1] if res["is_upi"] and not any(
            f.severity == "high" for f in res["findings"]
        ) else []
    return res["compact_evidence"][:2]


def benign_evidence_for(text: str) -> list[str]:
    res = analyze_upi(text)
    return res["benign_evidence"] if res["is_upi"] else []


def scam_type_for(text: str, verdict: int | str) -> str:
    res = analyze_upi(text)
    return _scam_type_from(res["findings"], verdict)


def prompt_snippet(text: str) -> str:
    """Structured, compact, URL-defanged summary of parsed UPI fields for Llama."""
    parsed = parse_upi(text)
    if not parsed:
        return text[:300]
    def clean(v: str, n: int) -> str:
        # Payload fields are attacker text: one line, no fence-closing quotes, bounded length.
        return re.sub(r'"{2,}', '"', re.sub(r"\s+", " ", v))[:n]

    parts = [f"Intent: {parsed['scheme']}://{clean(parsed['action'], 20)}"]
    if parsed["pa"]:
        parts.append(f"Payee UPI ID: {clean(parsed['pa'], 64)}")
    if parsed["pn"]:
        parts.append(f"Payee name: {clean(parsed['pn'], 64)}")
    if parsed["am"]:
        cu = (parsed["cu"] or "INR").upper()
        parts.append(f"Amount: {clean(cu, 6)} {clean(parsed['am'], 16)}")
    if parsed["mc"]:
        parts.append(f"Merchant code: {clean(parsed['mc'], 8)}")
    if parsed["tn"]:
        note = re.sub(r"(https?://[^\s<>\"']+)", lambda m: m.group(0).replace(".", "[.]"), parsed["tn"])
        parts.append(f"Note: {clean(note, 100)}")
    if parsed["url"]:
        safe_url = parsed["url"].replace(".", "[.]")
        parts.append(f"Ref URL: {clean(safe_url, 64)}")
    if parsed["recur"] or parsed["amrule"]:
        parts.append(f"Mandate: {clean(parsed['recur'] or 'recurring', 16)} {clean(parsed['amrule'], 8)}".strip())
    out = "; ".join(parts)
    return out if len(out) <= 320 else out[:317] + "..."


DEMO_FIXTURES = [
    ("legit_p2p", 0, "upi://pay?pa=priya.verma@okhdfcbank&pn=Priya%20Verma&am=450&cu=INR&tn=Dinner%20split"),
    ("legit_merchant", 0, "upi://pay?pa=sharma.kirana@okicici&pn=Sharma%20Kirana%20Store&mc=5411&cu=INR&tn=Grocery%20bill"),
    ("collect_scam", 1, "upi://collect?pa=9876543210@ibl&pn=OLX%20Army%20Buyer&am=15000&cu=INR&tn=Enter%20UPI%20PIN%20to%20receive%20payment"),
    ("refund_scam", 1, "upi://pay?pa=cashback.refund99@ybl&pn=Amazon%20Refund%20Desk&am=4999&cu=INR&tn=Scan%20to%20receive%20Amazon%20refund"),
]


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args or args == ["--demo"]:
        rows = []
        for name, expected, uri in DEMO_FIXTURES:
            res = analyze_upi(uri)
            rows.append({
                "name": name,
                "expected": expected,
                "label": res["label"],
                "score": res["score"],
                "scam_type": res["scam_type"],
                "evidence": res["evidence"],
                "summary": res["summary"],
            })
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    for uri in args:
        res = analyze_upi(uri)
        print(json.dumps({
            "label": res["label"],
            "score": res["score"],
            "scam_type": res["scam_type"],
            "evidence": res["evidence"],
            "summary": res["summary"],
        }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
