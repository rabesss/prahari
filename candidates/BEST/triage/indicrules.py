"""Indian-context scam evidence for English, Hinglish and Devanagari messages.

Two transparent lists: requests/threats that scammers make, and protection phrases that
genuine bank, OTP, delivery and government alerts use. Matching is negation-aware: a
phrase inside a clause that carries a negator ("do not share", "no customs fee", "पिन न भेजें")
is not counted as a scam request. The detector uses the counts as evidence, so every
decision stays explainable.
"""
import re
from urllib.parse import urlparse

NEG = re.compile(r"\b(no|not|never|without|n't|don't|doesn't|nahi|nahin|mat|bina)\b"
                 r"|(?:^|[\s;,:])(न|मत|बिना|कोई नहीं)(?:[\s;,:]|$)", re.I)

# (name, pattern, human description)
REQUESTS = [
    ("secret_request",
     r"(share|send|tell|reply|enter|forward|provide|submit|confirm|batao|bhejo|भेजें|बताएं|डालें|साझा|स्वीकार|दर्ज|पुष्टि)"
     r"[^.;!?।\n]{0,60}\b(otp|one[- ]time|pin|cvv|password|passcode|code|seed words|recovery phrase|"
     r"पिन|कोड|पासवर्ड|ओटीपी|गोपनीय)\b"
     r"|\b(otp|one[- ]time|pin|cvv|password|passcode|पिन|कोड|पासवर्ड|ओटीपी)\b[^.;!?।\n]{0,60}"
     r"(share|send|reply|enter|forward|submit|provide|भेजें|बताएं|डालें|साझा)",
     "asks you to share or send an OTP, PIN, CVV or password"),
    ("money_request",
     r"\b(pay|send|transfer|deposit|remit|buy|भेजें|जमा|भुगतान|स्वीकार)\b[^.;!?।\n]{0,45}"
     r"(rs\.?|inr|₹|rupees|रुपये|राशि|शुल्क|fee|charge|amount|money|balance|bill|dues|training|deposit)"
     r"|\bpay (to|for|now|today|immediately)\b"
     r"|(processing|registration|verification|activation|shipping|customs|delivery|release|reset|late|penalty)"
     r"\s*(fee|charge|amount|cost)|(processing|registration|verification|activation|shipping|customs|"
     r"delivery|release|reset)[^.;!?।\n]{0,12}(rs\.?|₹|inr|\d)"
     r"|(rs\.?|₹|inr)\s?\d[^.;!?।\n]{0,25}(fee|charge|deposit|registration|shipping|customs)"
     r"|(?:₹|rs\.?|inr)\s?\d{1,7}[^.;!?।\n]{0,40}"
     r"\b(pay|paid|bhej\w*|jama\w*|transfer|deposit)\b"
     r"|\b(pay|bhej\w*|jama\w*|transfer)\b[^.;!?।\n]{0,20}"
     r"\b(karo|kare|karke|kar do|kar dena|dena|do)\b"
     r"|collect request|कलेक्ट अनुरोध|भुगतान अनुरोध|अनुरोध स्वीकार|outstanding (balance|amount|dues)",
     "asks you to pay or approve a money request"),
    ("block_threat",
     r"\b(block|blocked|suspend|suspended|deactivat\w*|disconnect\w*|cut[- ]?off|expire\w*|penalty|"
     r"reject\w*|काट|बंद|निलंबित|ब्लॉक)\b[^.;!?।\n]{0,50}"
     r"\b(account|sim|card|service|connection|number|access|electricity|power|water|gas|bill|itr|"
     r"खाता|सिम|सेवा|बिजली)\b"
     r"|\b(account|sim|card|connection|number|electricity|power|bill|खाता|सिम|बिजली)\b"
     r"[^.;!?।\n]{0,50}(will be|ho gaya|हो जाएगा|हो गया|हो रहा|हो गई)[^.;!?।\n]{0,30}"
     r"(block|cut|suspend|deactiv\w*|disconnect\w*|closed|reject\w*|बंद|निलंबित)"
     r"|\b(account|card|sim|service|connection|number|खाता|सिम|कार्ड)\b"
     r"[^.;!?।\n]{0,20}\b(block|blocked|band|बंद)\b",
     "threatens to block, cut or suspend an account, SIM, connection or bill"),
    ("collect_pressure",
     r"(collect request|कलेक्ट अनुरोध|payment request|भुगतान अनुरोध|request awaits approval|"
     r"approve the (collect )?request|accept the (receive|collect) request|स्वीकार करें)",
     "pushes you to approve a UPI collect or payment request"),
    ("keep_access",
     r"(to keep access|avoid a branch visit|before (it|the offer|the link)? ?expires|"
     r"समय सीमा|deadline|last day|today itself|"
     r"otherwise (your|the) (account|service)|warna)",
     "creates a deadline or loss of access to pressure a quick response"),
    ("prize_offer",
     r"\b(won|winner|lottery|lucky draw|jackpot|prize|इनाम|लॉटरी|जीत|मिला है|gold coin)\b|"
     r"fixed weekly return|guaranteed profit|daily returns|earn (rs\.?|₹|inr)|cashback|"
     r"धनवापसी|रिफंड|कैशबैक|निवेश|मुनाफा|गारंटीड|टैक्स वापसी|पुरस्कार|लकी ड्रॉ|"
     r"क्रिप्टो|बिटकॉइन",
     "promises a prize, lottery win or guaranteed investment return"),
    ("job_offer",
     r"work from home|part[- ]time job|paid batch|work batch|daily income|घर से काम|"
     r"withdraw (your )?earnings|buy training|starter kit|instant loan|loan approval|"
     r"bina documents|बिना दस्तावेज|without documents|free me milega|low interest|लोन|ऋण|आसान कमाई",
     "offers easy money for online tasks, easy loans or a job"),
    ("screen_share",
     r"\b(anydesk|teamviewer|quicksupport|rustdesk|screen shar\w*)\b|\.apk\b|install (this|the) app",
     "asks you to install an app or share your screen"),
    ("authority_threat",
     r"\b(police|cbi|ed|customs|court|narcotics|arrest|fir|cyber cell|trai|rbi|income tax)\b"
     r"[^.;!?।\n]{0,70}\b(case|warrant|arrest|legal action|suspend|illegal|parcel|penalty)\b"
     r"|digital arrest|non[- ]bailable"
     r"|(पुलिस|सीबीआई|कस्टम|अदालत|गिरफ्तार|वारंट|एफआईआर|नारकोटिक्स|आयकर|कानूनी)"
     r"[^।;!?\n]{0,70}(कार्रवाई|गिरफ्तारी|मामला|वारंट|अवैध|पार्सल|जुर्माना|वीडियो कॉल)",
     "claims to be police, customs or a regulator and makes threats"),
    ("fake_official",
     r"\b(verification office|account support|payments review|profile desk|service desk|customer care|"
     r"fraud department|security team|our records show|a review slot is reserved|"
     r"संदिग्ध गतिविधि|असामान्य गतिविधि|सुरक्षा समीक्षा|धोखाधड़ी)\b",
     "poses as a bank, payment or verification desk"),
    ("urgency",
     r"\b(immediately|urgent|emergency|within \d+ ?(hours?|hrs|minutes?|days?)|tonight|last chance|"
     r"turant|abhi|jaldi|तुरंत)\b",
     "pressures you to act immediately"),
    ("click_link",
     r"(click|लिंक|क्लिक|jayein|जाएं|खोलो|open (this|the) link|https?://|www\.|this link|following link|"
     r"link below|is form|form ko bhariye|fill (this|the) form)",
     "asks you to open a link or fill a form"),
    ("verify_details",
     r"\bkyc\b|सत्यापन|सत्यापित|\bverify (your|the|account|investment|details)\b|\bverification\b|"
     r"अपडेट|update (your|the) (details|account|kyc|sim|pan)|pan card|aadhaar|itr|"
     r"details (update|verify|verification)|detail update",
     "asks you to verify or update personal, PAN or KYC details"),
    ("new_number",
     r"\b(call|contact|whatsapp|sampark|संपर्क)\b[^.;!?।\n]{0,30}(\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}",
     "asks you to call or message a personal mobile number"),
]

PROTECTIVE = [
    ("no_need",
     r"\b(not a request|asks for no|needs no|contains no|no link is attached|"
     r"no (advance|customs|processing|registration|delivery) (fee|charge)|"
     r"no (payment|fee|charge|otp|pin|cvv|code|link|reply|deposit)[^.;!?।\n]{0,25}"
     r"(required|needed|due|asked|attached|necessary|is needed)|"
     r"(pin|code|payment|fee|paisa|पैसा|पिन|कोड|राशि)[^.;!?।\n]{0,25}"
     r"(नहीं चाहिए|की जरूरत नहीं|ki zarurat nahi)|नहीं चाहिए)",
     "says that no payment, OTP, PIN or link is needed"),
    ("no_need_hi",
     r"(कोई\s+)?(शुल्क|भुगतान|पिन|कोड|राशि|लिंक|फीस|पैसा|फोन)[^।;!?\n]{0,20}"
     r"(नहीं चाहिए|नहीं लगेगा|नहीं लगती|की जरूरत नहीं|की आवश्यकता नहीं|नहीं मांगा)"
     r"|(कोई|कोई भी)\s+(शुल्क|भुगतान|पिन|कोड|राशि|लिंक|फीस)\s+(नहीं|मत)"
     r"|(शुल्क|भुगतान|पिन|कोड|राशि|फीस)\s+(नहीं|मत)\s+(लगेगा|लगती|चाहिए|भेजें|बताएं|करें)",
     "says in Hindi that no fee, payment or PIN is needed"),
    ("bill_notice_hi",
     r"(बिजली|पानी|गैस|ब्रॉडबैंड|बिल)[^।!?\n]{0,60}(देय|देय तिथि|बिल तैयार|बिल भेजा)"
     r"|बिल तैयार|देय राशि|देय तिथि|ऑटोपे|स्वचालित भुगतान|बिल भेजा गया",
     "reads like a routine Hindi bill notice or autopay reminder"),
    ("no_charges_hinglish",
     r"\b(koi|koyi|koee)\b[^.;!?\n]{0,25}\b(charge|fees|fee|paise|payment|otp|pin|link|code)\b"
     r"[^.;!?\n]{0,15}\b(nahi|nahin|mat)\b"
     r"|\b(charge|fees|fee|paise|payment|otp|pin)\b[^.;!?\n]{0,20}\b(nahi|nahin|mat) (lagega|lagti|chahiye|bhejein|batao)\b",
     "says in Hinglish that no extra charge or secret is needed"),
    ("dont_share",
     r"(do not|don't|does not|doesn't|never|will not|won't|mat|न)\s+"
     r"(share|send|reply|forward|click|bhej|bat|साझा|भेजें|बताएं|करें)"
     r"|ignore any caller|work(s)? only at the keypad",
     "tells you not to share the code or not to reply"),
    ("official_channel",
     r"official (app|portal|website|site|account)|signed-in|staff portal|provider app|"
     r"your (banking |payment )?app\b|in your app\b|आधिकारिक|desk number on your card|back of your card",
     "points you to the official app, portal or the number on your card"),
    ("never_ask_secret",
     r"(never|will not|won't|does not|doesn't|do not)\s+ask[^.;!?।\n]{0,30}"
     r"(otp|pin|cvv|password|code|details|payment|पिन|कोड|ओटीपी)",
     "states that the sender never asks for OTP, PIN or payment details"),
    ("transaction_update_hi",
     r"(भुगतान|राशि|धनराशि)[^।;!?\n]{0,20}(सफल|प्राप्त|जमा|कटौती|हो गया|कर दिया)"
     r"|(प्राप्त हुआ|जमा हो गया|सफलतापूर्वक|धन्यवाद)",
     "reads like a routine Hindi transaction receipt"),
    ("bill_notice",
     r"bill is ready|view (and pay )?(your )?bill|amount due|due date|pay by|auto-?pay|"
     r"\b(electricity|water|gas|broadband|postpaid|utility|power|bijli)\b[^.!?।\n]{0,25}\bbill\b"
     r"[^.!?।\n]{0,50}\b(is )?(due|ready|generated|issued)\b|"
     r"\bbill\b[^.!?।\n]{0,25}\b(is )?(due|ready|generated|issued)\b",
     "reads like a routine bill notice or payment reminder"),
    ("opt_out",
     r"reply stop|opt out|to unsubscribe",
     "offers an opt-out instead of asking for details"),
    ("transaction_update",
     r"(payment (of|for)?[^.;!?\n]{0,30}(has been |was )?received|"
     r"has (been )?(delivered|shipped|booked|credited|debited|renewed|received)|track(ing)? id|order (id|#)|"
     r"reference no|credited to your account|debited from your account|auto-?debit\w*|salary|"
     r"at your convenience|no action needed|thank you for paying|payment successful)",
     "reads like a routine transaction receipt or delivery update"),
]

STRONG = {"secret_request", "collect_pressure", "screen_share", "job_offer", "authority_threat"}


def _match(pattern, text):
    """First non-negated match of pattern, or None. A negator anywhere in the same clause vetoes it."""
    for m in re.finditer(pattern, text, re.I):
        start, end = m.span()
        left = max(text.rfind(c, 0, start) for c in ".!?।\n")
        right_candidates = [text.find(c, end) for c in ".!?।\n"]
        right_candidates = [c for c in right_candidates if c != -1]
        right = min(right_candidates) if right_candidates else len(text)
        clause = text[left + 1:right]
        if not NEG.search(clause):
            return m
    return None


def indicators(text):
    """Return (evidence list, request score, protective count, strong_request flag)."""
    t = text.lower()
    ev, score, prot = [], 0.0, 0
    names = set()
    weights = {"secret_request": 1.5, "money_request": 1.1, "collect_pressure": 1.2,
               "block_threat": 1.0, "fake_official": 0.7, "job_offer": 1.0, "prize_offer": 0.8,
               "keep_access": 0.8, "urgency": 0.4, "click_link": 0.35, "verify_details": 0.7,
               "screen_share": 1.2, "new_number": 0.5, "authority_threat": 1.0}
    for name, pat, desc in REQUESTS:
        if _match(pat, t):
            names.add(name)
            ev.append((name, desc))
            score += weights[name]
    pweight = {"no_need": 1.2, "no_need_hi": 1.2, "dont_share": 1.2, "never_ask_secret": 1.6,
               "official_channel": 0.8, "transaction_update": 0.9, "transaction_update_hi": 0.9,
               "bill_notice": 0.9, "bill_notice_hi": 0.9, "no_charges_hinglish": 1.0, "opt_out": 0.3}
    if names & {"block_threat", "click_link"}:
        # A bill notice or receipt is only routine when nothing threatens the reader and
        # nothing asks them to open a link. A stray "act now" on a completed receipt is
        # common in this dataset's benign hard negatives, so urgency alone does not veto it.
        pweight["bill_notice"] = pweight["bill_notice_hi"] = 0.3
        pweight["transaction_update"] = pweight["transaction_update_hi"] = 0.3
    for name, pat, desc in PROTECTIVE:
        if re.search(pat, t):
            ev.append((name, desc))
            prot += pweight[name]
    risky_host = official_host = False
    for host in _hosts(t):
        if is_official(host):
            official_host = True
            continue
        risky = host_risk(host)
        if risky:
            ev.append(risky)
            score += 0.9
            risky_host = True
    if official_host:
        ev.append(("official_domain", "the message links to an official company or government domain"))
        prot += 0.8
    # A request is "strong" when it names an explicit scam mechanic, not just a stray keyword:
    # a secret to hand over, a collect request, a screen-share app, a fake job or authority,
    # or a payment bundled with a link, deadline, prize or urgent tone.
    strong = bool(names & STRONG)
    strong = strong or ("money_request" in names and
                        bool(names & {"click_link", "keep_access", "urgency", "prize_offer", "block_threat"}))
    strong = strong or ("verify_details" in names and "click_link" in names and
                        (risky_host or "keep_access" in names or not official_host))
    strong = strong or (bool(re.search(r"[\u0900-\u097F]", t)) and "click_link" in names and not official_host
                        and bool(names & {"secret_request", "money_request", "collect_pressure", "verify_details",
                                          "prize_offer", "block_threat", "authority_threat", "job_offer"}))
    strong = strong or ("prize_offer" in names and "click_link" in names)
    strong = strong or ("new_number" in names and
                        bool(names & {"money_request", "prize_offer", "click_link", "verify_details"}))
    strong = strong or ("money_request" in names and re.search(r"parcel|customs|पार्सल|कस्टम", t)
                        and not official_host)
    if re.search(r"[\u0900-\u097F]", t):
        strong = strong or ("verify_details" in names and
                            bool(names & {"urgency", "block_threat", "keep_access", "new_number"}))
    if (re.search(r"\b(bill|electricity|water|gas|broadband|consumer|autopay)\b", t)
            and _hosts(t) and not risky_host
            and not (names & {"block_threat", "urgency", "verify_details", "secret_request",
                              "collect_pressure", "new_number", "screen_share", "authority_threat"})
            and not re.search(r"\b(block|blocked|disconnect\w*|cut[- ]?off|suspend\w*|deactivat\w*|"
                              r"verify|kyc|otp|pin|cvv|password)\b", t)):
        # A plain-host utility message with no threat, no secret request and no deadline
        # reads like a routine reminder, not a disconnection scam.
        strong = bool(names & STRONG)
        prot = max(prot, 0.8)
    return ev, score, prot, strong


def _hosts(t):
    seen = []
    for m in re.finditer(r"(?:https?://)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s<>\"']*)?", t):
        h = (urlparse(m.group(0) if "://" in m.group(0) else "http://" + m.group(0)).hostname or "").lower()
        if h and h not in seen:
            seen.append(h)
    return seen


OFFICIAL_SUFFIXES = (".gov.in", ".nic.in", ".bank.in")
OFFICIAL_DOMAINS = {"sbi.co.in", "onlinesbi.sbi", "hdfcbank.com", "icicibank.com", "axisbank.com",
                    "kotak.com", "pnbindia.in", "paytm.com", "phonepe.com", "npci.org.in", "bhimupi.org.in",
                    "amazon.in", "flipkart.com", "myntra.com", "irctc.co.in", "uidai.gov.in",
                    "incometax.gov.in", "epfindia.gov.in", "indiapost.gov.in", "pib.gov.in",
                    "cybercrime.gov.in", "sancharsaathi.gov.in", "airtel.in", "jio.com", "bsnl.co.in",
                    "google.com", "apple.com", "microsoft.com", "netflix.com", "paypal.com"}
BRANDS = ("sbi", "hdfc", "icici", "axis", "kotak", "pnb", "paytm", "phonepe", "gpay", "bhim", "npci",
          "amazon", "flipkart", "irctc", "uidai", "aadhaar", "incometax", "epfo", "airtel", "jio",
          "indiapost", "netflix", "paypal", "google", "apple", "microsoft", "kbc", "rbi", "trai")
RISKY_TLDS = {"top", "xyz", "club", "online", "site", "live", "icu", "buzz", "info", "click", "link",
              "work", "rest", "fit", "tk", "ml", "ga", "cf", "gq", "shop", "vip", "cc", "win", "loan"}


def is_official(host):
    if host in OFFICIAL_DOMAINS or host.endswith(OFFICIAL_SUFFIXES):
        return True
    return any(host.endswith("." + d) for d in OFFICIAL_DOMAINS)


def host_risk(host):
    """One evidence tuple when a host looks like a lookalike or throwaway domain."""
    parts = host.split(".")
    if len(parts) < 2:
        return None
    tld = parts[-1]
    label = parts[-2]
    if is_official(host):
        return None
    brand = next((b for b in BRANDS if b in host), None)
    if brand and tld in RISKY_TLDS:
        return ("brand_lookalike", f"the domain {host} imitates '{brand}' and uses .{tld}, a throwaway registry")
    if brand and any("-" in part and brand in part for part in parts):
        return ("brand_lookalike", f"the domain {host} imitates '{brand}' in a hyphenated lookalike name")
    if tld in RISKY_TLDS:
        return ("risky_tld", f"the domain ends in .{tld}, common for scam sites")
    if re.search(r"\d", label) and any(b in label.replace("0", "o") for b in BRANDS):
        return ("digit_swap", f"the domain {host} swaps letters for digits to imitate a brand")
    return None
