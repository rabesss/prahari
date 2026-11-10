"""Mechanism-level analysis of a message: what it asks the reader to DO.

A scam is a *request that harms*: hand over a secret, pay to receive money, approve a
collect request, install a remote-access app, move funds to a "safe" account, or act on a
threat through a channel the real organisation does not use. A genuine alert may mention
amounts, codes, links and deadlines, so none of those alone is evidence: the decision needs
both the mechanism and the absence of the legitimate channel that would explain it.

Everything here is clause-scoped and negation-aware ("do not share", "share na karein",
"किसी को न बताएं"), so protection statements are read as protection, not as requests.
"""
import re
import unicodedata
from urllib.parse import urlparse

SPLIT = ".!?।;\n"
NEG = re.compile(
    r"\b(no|not|never|without|n't|dont|don't|doesn't|does not|will not|won't|avoid|"
    r"nahi|nahin|mat|bina|na)\b"
    r"|(?:^|[\s,;:])(न|मत|बिना|नहीं|कोई नहीं)(?:[\s,;:]|$)", re.I)

SECRET = (r"(otp|one[- ]?time (password|code|pin)|verification code|login code|security code|"
          r"\bpin\b|mpin|upi pin|cvv|password|passcode|card (number|details|no)|"
          r"net ?banking|internet banking|account (number|details)|aadhaar|आधार|\bpan\b|"
          r"date of birth|\bdob\b|personal (details|information)|"
          r"पिन|ओटीपी|कोड|पासवर्ड|सीवीवी|कार्ड|खाता संख्या|पैन|जन्मतिथि|जानकारी|विवरण|केवाईसी|\bkyc\b)")
REQUEST = (r"(share|send|reply|tell|give|enter|type|provide|submit|forward|confirm|verify|update|"
           r"read out|dictate|batao|bataen|bataein|bhejein|bhejo|daalein|daal|darj|karein|karo|kijiye|"
           r"भेजें|बताएं|बताओ|डालें|दर्ज|दें|साझा|पुष्टि|स्वीकार|भरें|अपडेट|करें)")
PAY = (r"\b(pay|paid|send|transfer|deposit|remit|fund)\b|(bhejein|bhejo)|"
       r"भुगतान|भेजें|स्वीकार|भरें")
AMOUNT = r"(rs\.?|inr|₹|rupees|रुपये|राशि|amount|money|balance|bill|dues|शुल्क|फीस)"
DEST_OFFICIAL = (r"(in|via|through|using|on|at)\s+(the\s+)?(official\s+)?(bank\s+|payment\s+|provider\s+|"
                 r"insurer\s+|company\s+|merchant\s+)?(app|application|portal|website|site|account settings|ATM)|"
                 r"official (app|portal|website|site)|आधिकारिक (ऐप|पोर्टल|वेबसाइट)|"
                 r"(ऐप|पोर्टल|वेबसाइट)\s*(में|पर|से|द्वारा)\s*(भुगतान|देखें|करें|करें।)|"
                 r"at the (ATM|branch)|back of your card|signed[- ]in|"
                 r"official (helpline|number)|number on (the )?(back of )?your card|"
                 r"(in|via) your (banking |payment )?app")
DEST_PERSONAL = (
    r"(to|into|at|on)\s+(this|the|following|my|a)\s+(account|number|wallet|upi|vpa)|"
    r"(is|iss|is) (account|number) (me|mein|par)|"
    r"(temporary|safe|secure)\s+account|"
    r"\b[6-9]\d{9}\b|\+91|"
    r"\b[a-z0-9._%+-]+@[a-z]{2,}\b|"
    r"(इस|नीचे दिए|दिए गए)\s+(लिंक|अकाउंट|खाते)|"
    r"(phone|mobile|whatsapp|telegram)\s*(number|par|pe|se)|"
    r"crypto|bitcoin|usdt|wallet address")
PAY_TO_RECEIVE = (
    r"(pay|send|transfer|deposit|bhejein|jama|भरें|भेजें|जमा)[^.;!?।\n]{0,70}"
    r"(to (get|receive|claim|unlock|release|accept|activate)|before (credit|release|refund|delivery)|"
    r"to receive|to claim|to unlock|to release|राशि पाने|प्राप्त करने|प्राप्त होने|इनाम|पुरस्कार|"
    r"रिफंड|वापसी|refund|prize|award|cashback|profits?|guaranteed)"
    r"|(refund|prize|award|lottery|इनाम|रिफंड|वापसी|delivery|पार्सल|डिलीवरी)[^.;!?।\n]{0,70}"
    r"(\bpay\b|\bsend\b|\bfee\b|\bcharge\b|\bdeposit\b|शुल्क|भरें|भेजें|जमा|पाएं|पाने)")
FEE = (r"(processing|registration|verification|activation|shipping|customs|clearance|delivery|release|"
       r"reset|late|penalty|unlock|reactivation|redemption|starter|security|training|service)\s*"
       r"(fee|charge|amount|cost|deposit)"
       r"|(शुल्क|फीस|चार्ज)")
COLLECT = (r"(collect request|payment request|कलेक्ट अनुरोध|भुगतान अनुरोध)")
COLLECT_ACTION = (r"(approve|accept|स्वीकार|अनुमोदन)")
REMOTE = (r"\b(anydesk|teamviewer|quicksupport|rustdesk|screen shar\w*|screen mirror\w*)\b|"
          r"\.apk\b|\bapk\b|install (this|the|our|meter|profile|remote|any)[a-z ]{0,20}(app|application|apk)|"
          r"grant (contacts|sms|access|permissions)|"
          r"ऐप (लगाकर|इंस्टॉल)|ऐप डाउनलोड")
THREAT = (
    r"\b(block|blocked|suspend|suspended|deactivat\w*|disconnect\w*|cut[- ]?off|freeze|frozen|"
    r"expire\w*|penalty|arrest|warrant|legal action|fir|closure)\b[^.;!?।\n]{0,60}"
    r"\b(account|sim|card|service|connection|number|access|electricity|power|water|gas|bill|itr|"
    r"खाता|सिम|सेवा|बिजली|कार्ड)"
    r"|\b(account|sim|card|connection|number|electricity|power|bill|खाता|सिम|बिजली|कार्ड)\b"
    r"[^.;!?।\n]{0,60}\b(will be|ho gaya|ho jayega|हो जाएगा|हो गया|हो सकता|हो गई|कर दिया|काट दिया|बंद|निलंबित|फ्रीज)"
    r"[^.;!?।\n]{0,40}\b(block|blocked|cut|suspend|deactiv\w*|disconnect\w*|closed|reject\w*|बंद|निलंबित|फ्रीज)"
    r"|\b(block|blocked|band|बंद|ब्लॉक|निलंबित|फ्रीज)\b[^.;!?।\n]{0,40}\b(account|card|sim|number|खाता|कार्ड|सिम)")
AUTHORITY = (r"\b(police|cbi|\bed\b|customs|court|narcotics|cyber cell|\btrai\b|\brbi\b|income tax|"
             r"enforcement directorate)\b"
             r"|(पुलिस|सीबीआई|कस्टम|अदालत|नारकोटिक्स|आयकर|प्रवर्तन)")
AUTHORITY_ACT = (r"\b(case|warrant|arrest|legal action|fir|penalty|parcel|summons|notice|inquiry|"
                 r"जांच|मामला|वारंट|गिरफ्तारी|कार्रवाई|नोटिस)")
JOB = (r"(work from home|work-from-home|part[- ]time job|part time job|paid batch|work batch|"
       r"daily income|earn (rs\.?|₹|inr)?\s?\d+|data entry|घर से काम|कमाई|नौकरी|"
       r"\binterview\b|shortlisted)")
LOAN = (r"(instant loan|loan approval|loan approved|pre[- ]approved|personal loan|"
        r"बिना दस्तावेज|without documents|लोन|ऋण|आसान कमाई)")
UPFRONT = (r"(starter kit|buy training|training fee|processing fee|registration fee|security deposit|"
           r"(काम|task|batch|job|work)[^.;!?।\n]{0,35}(जमा राशि|deposit|फीस|fee|शुल्क)|"
           r"(pay|send|transfer|deposit|bhejein|jama|भेजें|जमा|भरें)[^.;!?।\n]{0,45}"
           r"(registration|booking|seat|confirmation|interview|fee|charge)[^.;!?।\n]{0,25}"
           r"(rs\.?|inr|₹|rupees|रुपये)?\s*\d{2,6}|"
           r"(pay|send|transfer|deposit|bhejein|jama|भेजें|जमा|भरें)[^.;!?।\n]{0,30}"
           r"\d{2,6}[^.;!?।\n]{0,20}(registration|booking|seat|confirmation|interview|fee|charge)|"
           r"pay (a )?(small )?(fee|charge|deposit)|fee (bhejein|jama)|(शुल्क|फीस|जमा)\s*(भरें|भेजें|करें)|"
           r"pay to (unlock|activate|start|join))")
PRIZE = (r"\b(won|winner|lottery|lucky draw|jackpot|prize|इनाम|लॉटरी|जीत|पुरस्कार|लकी ड्रॉ)\b"
         r"|(guaranteed (profit|return)|fixed weekly return|निश्चित साप्ताहिक|गारंटीड)")
PRIZE_ACT = (r"(pay|send|fee|charge|details|claim|deposit|शुल्क|भरें|भेजें|जमा|विवरण|जानकारी|प्राप्त)")
SAFE_ACCOUNT = (r"(temporary|safe|secure)\s+(account|खाते|account me)"
                r"|(transfer|send|move|भेजें|ट्रांसफर)[^.;!?।\n]{0,45}"
                r"(whole|entire|full|all the|savings|balance|पूरी राशि|सारा पैसा)")
CRYPTO = r"(crypto|bitcoin|usdt|binance|wallet address|क्रिप्टो|बिटकॉइन)"
RISKY_BRANDS = ("sbi", "hdfc", "icici", "axis", "kotak", "pnb", "paytm", "phonepe", "gpay", "bhim",
                "npci", "amazon", "flipkart", "irctc", "uidai", "aadhaar", "incometax", "epfo", "airtel",
                "jio", "indiapost", "netflix", "paypal", "google", "apple", "microsoft", "kbc", "rbi",
                "trai", "mahadiscom", "lic", "bsnl", "vodafone")
RISKY_TLDS = {"top", "xyz", "club", "online", "site", "live", "icu", "buzz", "info", "click", "link",
              "work", "rest", "fit", "tk", "ml", "ga", "cf", "gq", "shop", "vip", "cc", "win", "loan"}
OFFICIAL_SUFFIXES = (".gov.in", ".nic.in", ".bank.in", ".ac.in", ".edu.in")
OFFICIAL_DOMAINS = {"sbi.co.in", "onlinesbi.sbi", "hdfcbank.com", "icicibank.com", "axisbank.com",
                    "kotak.com", "pnbindia.in", "paytm.com", "phonepe.com", "npci.org.in",
                    "bhimupi.org.in", "amazon.in", "amazon.com", "flipkart.com", "myntra.com",
                    "irctc.co.in", "uidai.gov.in", "incometax.gov.in", "epfindia.gov.in",
                    "indiapost.gov.in", "pib.gov.in", "cybercrime.gov.in", "sancharsaathi.gov.in",
                    "airtel.in", "jio.com", "bsnl.co.in", "mahadiscom.in", "google.com", "apple.com",
                    "microsoft.com", "netflix.com", "paypal.com"}
SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd", "cutt.ly", "rb.gy", "shorturl.at",
              "tiny.cc", "ow.ly"}
URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>\"']+|"
                    r"\b(?:[a-z0-9-]+\.)+(?:com|in|net|org|top|xyz|info|co|ly|me|io|site|online|link|"
                    r"click|live|vip|cc|shop|club|app|biz|pro|icu|buzz|work|rest|fit|tk|ml|ga|cf|gq|"
                    r"dev|net|org)(?:/[^\s<>\"']*)?", re.I)

SAFE = [
    ("official_channel", DEST_OFFICIAL),
    ("transaction_receipt",
     r"(debited|credited|withdrawn|paid to|received from|has (been )?(delivered|shipped|booked|processed|"
     r"credited|debited|renewed|received|cancelled)|order (id|#|no)|a/c\s*(no\.?)?\s*x*\d|"
     r"account\s*xx|salary[^.;!?।\n]{0,25}(credited|received|paid)|refund[^.;!?।\n]{0,30}processed|"
     r"ticket[^.;!?।\n]{0,25}confirmed|\bpnr\b|booking (is )?confirmed|"
     r"recharge[^.;!?।\n]{0,25}(successful|active|done)|is now active|(successfully|successful)[^.;!?।\n]{0,20}(done|active|completed)|"
     r"(टिकट|बुकिंग|ऑर्डर|रिचार्ज|रिफंड|वेतन)[^।;!?\n]{0,25}"
     r"(कन्फर्म|सफल|सक्रिय|आ गया|आ गई|जमा|प्राप्त|पहुंच)|पीएनआर|"
     r"(recharge|ticket|booking|order|refund|salary|payment)[^.;!?।\n]{0,30}"
     r"(ho gaya|ho gayi|aa gaya|aa gayi|jama hua|successful|credited)|"
     r"जमा हुआ|प्राप्त हुआ|नवीनीकरण|डिलीवर हो गया|डिलीवर हुआ|पहुंच गया|सफलतापूर्वक|स्वीकार कर लिया|वेतन|रिटर्न)"),
    ("otp_notification",
     r"((your|aapka|आपका)?\s*(otp|code|pin|password|कोड|ओटीपी|पिन)\s*(is|है)?\s*[:#-]?\s*\d{4,8})"
     r"|(code\s*(is)?\s*\d{4,8})|(\d{4,8}\s*(is your|aapka)\s*(otp|code))|"
     r"(\d{4,8}\s*(is|है)\s*(your|aapka|आपका)?\s*(one[- ]?time (password|code)|otp|verification code))"),
    ("protective",
     r"(never|will not|won't|does not|doesn't|do not|don't)\s+(ask|asks|share|send|reply|call)|"
     r"no (payment|fee|charge|otp|pin|cvv|code|link|reply|deposit|action|shortlink|secret-code)"
     r"[^.;!?।\n]{0,40}(required|needed|due|asked|attached|necessary|is needed|request)|"
     r"do not share|don't share|never share|share na karein|share mat karein|mat (bat|bhej)|"
     r"na (bhejein|bataen|karein)|न भेजें|न बताएं|मत बताएं|साझा न करें|नहीं मांगा|नहीं मांगेगा|"
     r"(needs|requires) no (code|payment|link|fee|otp|reply|pin)|"
     r"koi (secret )?code kisi ko mat|"
     r"reply stop|opt out|unsubscribe|works only at the keypad|"
     r"(कोई\s+)?(शुल्क|भुगतान|पिन|कोड|राशि|लिंक|फीस)[^।;!?\n]{0,45}"
     r"(नहीं चाहिए|नहीं लगेगा|नहीं लगती|की जरूरत नहीं|नहीं मांगा|नहीं है|नहीं)"),
    ("notice",
     r"\b(appointment|scheduled|rescheduled|meeting|notice|reminder|admit card|result|interview|"
     r"application|shortlisted|portal|office|campus|school|college|policy|renewal|statement)\b|"
     r"(सूचना|सूचि|बैठक|नोटिस|रिमाइंडर|पोर्टल|कार्यालय|विद्यालय|पॉलिसी|नवीनीकरण)"),
    ("appointment_notice",
     r"\b(appointment|appointments|scheduled|rescheduled|consultation|follow[- ]?up|check[- ]?up|"
     r"delayed|running late|platform (changed|change)|gate (changed|change)|diversion)\b|"
     r"(अपॉइंटमेंट|परामर्श|जांच|विलंब)"),
    ("bill_notice",
     r"(bill|बिल)[^.;!?।\n]{0,40}(is )?(ready|due|generated|issued|reminder)|"
     r"amount due|due date|(देय तिथि|देय राशि|बिल तैयार)|bill (for|of)\b|"
     r"(प्रीमियम|बीमा|पॉलिसी|policy|premium)[^।.;!?\n]{0,25}(देय|due|renew)"),
    ("promo",
     r"\b(sale|discount|% ?off|cashback|deal|coupon|offer|win up to|save up to|free trial)\b|"
     r"(छूट|ऑफर|सेल|कैशबैक)"),
    ("personal",
     r"(family note|good night|see you|call me|reach(ed)? home|lunch|dinner|ghar pahunch|khana)"),
]


def clean(text):
    """Undo cheap obfuscations a scam may use: zero-width joiners, full-width forms, spaced capitals."""
    s = unicodedata.normalize("NFKC", text)
    s = re.sub(r"[\u200b-\u200f\u2060\ufeff\u00ad]", "", s)
    s = re.sub(r"\b(?:[A-Z]\s){2,}[A-Z]\b", lambda m: m.group(0).replace(" ", ""), s)
    return s.replace("\u00a0", " ")


def clauses(t):
    """Split on sentence punctuation; keep the text lowercased."""
    out, start = [], 0
    for m in re.finditer("[" + re.escape(SPLIT) + "]", t):
        if m.start() > start:
            out.append((start, t[start:m.start()]))
        start = m.end()
    if start < len(t):
        out.append((start, t[start:]))
    return out


def _negated(clause):
    return bool(NEG.search(clause))


def _clause_hit(pattern, t):
    """True when pattern matches a clause that is not negated."""
    for _, c in clauses(t):
        if re.search(pattern, c, re.I) and not _negated(c):
            return True
    return False


def _clause_find(pattern, t):
    for off, c in clauses(t):
        m = re.search(pattern, c, re.I)
        if m and not _negated(c):
            return c.strip(), off + m.start(), off + m.end()
    return None


def _any(pattern, t):
    return bool(re.search(pattern, t, re.I))


def hosts(t):
    out = []
    for m in URL_RE.finditer(t):
        raw = m.group(0).rstrip(".,;:)!?")
        u = raw if "://" in raw else "http://" + raw
        h = (urlparse(u).hostname or "").lower().strip(".")
        if h and h not in out:
            out.append(h)
    return out


def is_official(h):
    return h in OFFICIAL_DOMAINS or h.endswith(OFFICIAL_SUFFIXES) or any(
        h.endswith("." + d) for d in OFFICIAL_DOMAINS)


def host_risk(h):
    parts = h.split(".")
    if len(parts) < 2:
        return ""
    tld, label = parts[-1], parts[-2]
    if is_official(h):
        return ""
    brand = next((b for b in RISKY_BRANDS if b in h), None)
    if brand and tld in RISKY_TLDS:
        return f"the domain {h} imitates '{brand}' on .{tld}"
    if brand and any("-" in p and brand in p for p in parts):
        return f"the domain {h} is a hyphenated lookalike of '{brand}'"
    if tld in RISKY_TLDS:
        return f"the domain {h} uses .{tld}, common for throwaway scam sites"
    if re.search(r"\d", label) and any(b in label.replace("0", "o") for b in RISKY_BRANDS):
        return f"the domain {h} swaps letters for digits to imitate a brand"
    if h.count("-") >= 2 or h.count(".") >= 4:
        return f"the domain {h} is unusually long or hyphenated"
    return ""


def analyze(text):
    """Return a dict of mechanism findings used by the decision layer."""
    t = clean(text).lower()
    a = {"text": t, "harm": [], "safe": [], "hosts": [], "risky": [], "official_host": False,
         "secret": False, "pay_to_receive": False, "pay_unverified": False, "collect": False,
         "remote": False, "crypto": False, "authority": False, "threat": False, "job_upfront": False,
         "prize_claim": False, "safe_account": False, "fee": False, "official_channel": False,
         "receipt": False, "otp_note": False, "protective": False, "notice": False, "promo": False,
         "bill": False, "appointment": False}

    hs = hosts(t)
    a["hosts"] = hs
    for h in hs:
        r = host_risk(h)
        if r:
            a["risky"].append(r)
        elif is_official(h):
            a["official_host"] = True

    for name, pat in SAFE:
        if _any(pat, t):
            a["safe"].append(name)
    a["official_host"] = a["official_host"] and not a["risky"]
    a["official_channel"] = "official_channel" in a["safe"] or a["official_host"]
    a["receipt"] = "transaction_receipt" in a["safe"]
    a["otp_note"] = "otp_notification" in a["safe"]
    a["protective"] = "protective" in a["safe"]
    a["notice"] = "notice" in a["safe"]
    a["bill"] = "bill_notice" in a["safe"]
    a["appointment"] = "appointment_notice" in a["safe"]
    a["promo"] = "promo" in a["safe"]

    risky_any = bool(a["risky"])
    # A request for a secret only counts when the reader is asked to hand it over and the
    # channel is not a known official app/portal; a notification ("your code is 123456")
    # and a protection statement ("do not share") are excluded.
    handover = (r"(share|send|reply|tell|give|enter|type|provide|submit|forward|confirm|verify|fill|"
                r"read out|dictate|batao|bataen|bataein|bhejein|bhejo|daalein|daal|darj|"
                r"साझा|भेजें|बताएं|बताओ|डालें|दर्ज|दें|भरें|भरो)")
    phish_page = _clause_hit(r"(click|enter|login|log in|sign in|submit|verify|confirm|update|pay|share)"
                             r"[^.;!?।\n]{0,40}(link|page|site|portal|here|below|unlock|account|kyc|otp|"
                             r"pin|reactivate|blocked)", t) or \
        bool(re.search(r"(click|enter|login|log in|sign in|submit|verify|confirm|update|pay|share)"
                       r"[^\n]{0,60}(https?://|www\.)", t, re.I))
    if _clause_hit(handover + r"[^.;!?।\n]{0,60}" + SECRET, t) or \
       _clause_hit(SECRET + r"[^.;!?।\n]{0,60}" + handover, t) or \
       (risky_any and phish_page and _clause_hit(SECRET, t)):
        if not a["official_channel"]:
            a["secret"] = True
            a["harm"].append(("secret_request", "asks you to share a PIN, OTP, card or account detail"))
    if risky_any and phish_page and (re.search(SECRET, t, re.I) or
                                     _clause_hit(r"(account|kyc|otp|pin|unlock|verify|blocked|reactivate)", t)):
        a["harm"].append(("phish_link", "sends you to a lookalike page and asks you to act there"))

    fee = _clause_hit(FEE, t)
    pay = _clause_hit(PAY, t)
    a["fee"] = fee
    if _clause_hit(PAY_TO_RECEIVE, t):
        a["pay_to_receive"] = True
        a["harm"].append(("pay_to_receive", "asks for a payment before a refund, prize or delivery is released"))
    elif pay and (fee or _clause_hit(AMOUNT, t)) and not a["official_channel"] and not a["official_host"] and \
            (_clause_hit(DEST_PERSONAL, t) or risky_any or (fee and _clause_hit(r"https?://|www\.|link", t))):
        a["pay_unverified"] = True
        a["harm"].append(("pay_unverified", "asks for a payment to a personal number, account or unverified link"))
    if _clause_hit(COLLECT, t) and _clause_hit(COLLECT_ACTION, t):
        a["collect"] = True
        a["harm"].append(("collect_request", "pushes you to approve a UPI collect or payment request"))
    if _clause_hit(REMOTE, t):
        a["remote"] = True
        a["harm"].append(("remote_access", "asks you to install an app or share your screen"))
    if _clause_hit(CRYPTO, t) and (pay or _clause_hit(r"(send|transfer|deposit|bhejein|भेजें)", t)):
        a["crypto"] = True
        a["harm"].append(("crypto_transfer", "asks you to move money into crypto"))
    if _clause_hit(SAFE_ACCOUNT, t):
        a["safe_account"] = True
        a["harm"].append(("safe_account", "asks you to move funds to a 'safe' account"))
    if _clause_hit(AUTHORITY, t) and _clause_hit(AUTHORITY_ACT, t) and \
            (pay or a["secret"] or _clause_hit(r"(video call|join the call|call|transfer|तुरंत|भुगतान)", t)):
        a["authority"] = True
        a["harm"].append(("authority_threat", "poses as police, customs or a regulator and demands action"))
    if _clause_hit(THREAT, t) and not (a["official_channel"] and not a["pay_to_receive"]):
        a["threat"] = True
        a["harm"].append(("block_threat", "threatens to block, cut or freeze an account, SIM or connection"))
    if (_clause_hit(JOB, t) or _clause_hit(LOAN, t)) and _clause_hit(UPFRONT, t):
        a["job_upfront"] = True
        a["harm"].append(("job_upfront", "offers a job or loan that needs an upfront fee or deposit"))
    elif _clause_hit(JOB, t) and _clause_hit(r"(daily|per day|roz|रोज|turant|immediately|whatsapp|telegram)", t):
        a["job_upfront"] = True
        a["harm"].append(("job_offer", "offers easy daily income through a personal chat channel"))
    if _clause_hit(r"(private (recording|video|photo)|intimate|morphed|nude)", t) and \
            _clause_hit(r"(post|publish|leak|share|send to|वायरल)", t):
        a["sextortion"] = True
        a["harm"].append(("sextortion", "threatens to publish private material unless you pay"))
    if _clause_hit(PRIZE, t) and _clause_hit(PRIZE_ACT, t):
        a["prize_claim"] = True
        a["harm"].append(("prize_claim", "promises a prize that needs a fee or personal details to claim"))

    # Evidence texts are deduplicated in order.
    return a


DECISIVE = {"secret_request", "pay_to_receive", "collect_request", "remote_access", "crypto_transfer",
            "safe_account", "authority_threat", "job_upfront", "prize_claim", "sextortion", "phish_link"}


def decide(p_model, a):
    """Turn the mechanism analysis plus the text-model probability into a label and score.

    Order matters: a decisive harmful mechanism wins over a receipt or protection clause, because
    scammers write "no OTP needed, just pay the fee". A benign explanation (official channel, a
    completed-transaction record, an OTP notification, a protection statement) only clears a message
    when no harmful mechanism is present. The model probability is a tie-breaker for novel wording.
    """
    harm = [n for n, _ in a["harm"]]
    strong = [h for h in harm if h in DECISIVE]
    if strong:
        return 1, max(p_model, 0.85), a
    if a["threat"] and (a["risky"] or a["pay_unverified"] or a["secret"] or a["fee"]):
        return 1, max(p_model, 0.75), a
    if (a["pay_unverified"] or a["secret"]) and a["risky"]:
        return 1, max(p_model, 0.75), a
    if not harm and (a["receipt"] or a["otp_note"]):
        # A completed transaction or an OTP notification is a record, not a request.
        return 0, min(p_model, 0.35), a
    if not harm and (a["protective"] or a["promo"] or a["official_channel"] or a["notice"] or a["bill"]
                     or a["appointment"]):
        return 0, min(p_model, 0.40), a
    if p_model >= 0.85 and not (a["official_channel"] or a["receipt"] or a["otp_note"] or a["protective"]):
        return 1, p_model, a
    if harm:
        return "uncertain", p_model, a
    return 0, p_model, a


DEVANAGARI = re.compile(r"[\u0900-\u097F]")
HINGLISH = re.compile(
    r"\b(hai|hain|aap|aapka|aapki|aapke|karein|karo|kijiye|karna|nahi|nahin|bhejein|bhejo|"
    r"turant|jaldi|paisa|paise|khata|namaste|milega|zaroorat|chahiye|sakte|hoga|gaya|gayi|"
    r"raha|rahi|bhai|didi|kripya|dhanyavad|swagat|wala|wali|abhi|mera|tera|hum|tum|bhej|"
    r"kare|karen|kar|jaye|jayega|hoga|hogi)\b", re.I)
INDIA = re.compile(
    r"\b(upi|kyc|aadhaar|pan|inr|lakh|crore|npci|irctc|uidai|epfo|trai|rbi|sbi|hdfc|icici|"
    r"axis|kotak|pnb|paytm|phonepe|gpay|bhim|indiapost|mahadiscom|bsnl|jio|airtel|lic|"
    r"collect request|digital arrest|cyber cell|electricity|disconnection|meter|courier|"
    r"customs|parcel|otp|rupees|शुल्क)\b|[₹]|\brs\.?\s?\d|\+91|\b[6-9]\d{9}\b|\.in\b", re.I)


def indic_context(text):
    """True for Indian-language or Indian-context messages; routes them to the Indic detector.

    Obfuscated text is cleaned first so zero-width characters cannot hide an Indian marker.

    The generic English SMS model is trained on a British SMS corpus and must keep serving that
    distribution unchanged. Indian messages carry at least one marker the corpus does not use:
    Devanagari script, Hinglish function words, an Indian entity, rupee amounts or a +91 number.
    """
    text = clean(text)
    return bool(DEVANAGARI.search(text) or HINGLISH.search(text) or INDIA.search(text))


SAFE_DESC = {
    "official_channel": "the payment or check happens inside the organisation's official app or portal",
    "transaction_receipt": "reads like a normal payment receipt or delivery record",
    "otp_notification": "reads like a normal OTP notification",
    "protective": "explicitly says that no payment, code or reply is needed",
    "notice": "reads like a routine notice or appointment",
    "bill_notice": "reads like a routine bill reminder with a payment due",
    "appointment_notice": "reads like a routine appointment or schedule change",
    "promo": "reads like a promotional offer with a discount or cashback",
    "personal": "reads like a personal conversation",
}


def evidence(a):
    """Human-readable evidence lines for the API (harm first, then the benign explanation)."""
    out = [d for _, d in a["harm"]]
    for r in a["risky"]:
        if r not in out:
            out.append(r)
    if not a["harm"]:
        for s in ("official_channel", "transaction_receipt", "otp_notification", "protective", "notice", "promo"):
            if s in a["safe"]:
                out.append(SAFE_DESC[s])
    return out[:5]
