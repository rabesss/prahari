"""Transparent indicator rules. Each hit becomes human-readable evidence."""
import re
from urllib.parse import urlparse

SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd", "cutt.ly", "rb.gy", "shorturl.at", "tiny.cc", "ow.ly"}
BRANDS = ["sbi", "hdfc", "icici", "axis", "paytm", "phonepe", "gpay", "amazon", "flipkart", "irctc", "uidai",
          "aadhaar", "incometax", "epfo", "npci", "bhim", "airtel", "jio", "vodafone", "bsnl", "indiapost",
          "fedex", "dhl", "bluedart", "netflix", "google", "apple", "microsoft", "paypal", "kotak", "pnb"]
OFFICIAL_SUFFIXES = (".gov.in", ".nic.in", ".bank.in")
OFFICIAL_DOMAINS = {"sbi.co.in", "onlinesbi.sbi", "hdfcbank.com", "icicibank.com", "axisbank.com", "paytm.com",
                    "phonepe.com", "amazon.in", "amazon.com", "flipkart.com", "irctc.co.in", "uidai.gov.in",
                    "incometax.gov.in", "epfindia.gov.in", "npci.org.in", "airtel.in", "jio.com", "indiapost.gov.in",
                    "google.com", "apple.com", "microsoft.com", "kotak.com", "pnbindia.in", "myntra.com"}
RISKY_TLDS = {"top", "xyz", "club", "online", "site", "live", "icu", "buzz", "info", "click", "link", "work",
              "rest", "fit", "tk", "ml", "ga", "cf", "gq", "shop", "vip", "cc"}

TEXT_RULES = [
    ("credential_request", r"\b(otp|one time password|upi pin|mpin|cvv|pin)\b.{0,40}\b(share|send|tell|enter|provide|batao|bhejo)\b|\b(share|send|tell|enter|provide|batao|bhejo)\b.{0,40}\b(otp|upi pin|mpin|cvv)\b",
     "asks you to share or enter an OTP, PIN or CVV"),
    ("kyc_threat", r"\bkyc\b.{0,60}\b(update|expire|expired|pending|suspend|block|band)\b|\b(update|complete)\b.{0,20}\bkyc\b",
     "says your KYC must be updated or your account will be blocked"),
    ("urgency", r"\b(immediately|urgent|within \d+ ?(hours?|hrs|minutes?|mins)|today itself|tonight|last chance|turant|abhi|jaldi)\b",
     "pressures you to act immediately"),
    ("disconnection", r"\b(electricity|power|connection|sim|account|number)\b.{0,40}\b(cut|disconnect|block|suspend|deactivat|band)\w*",
     "threatens to cut a service or block an account"),
    ("prize", r"\b(won|winner|lottery|lucky draw|kbc|prize|jackpot|cashback of|reward points?)\b",
     "promises a prize, lottery or reward"),
    ("payment_request", r"\b(pay|transfer|deposit|send)\b.{0,30}(rs\.?|inr|₹|rupees)\s?\d|\b(processing|registration|clearance|customs) fee\b|\bcollect request\b",
     "asks you to pay money or approve a payment request"),
    ("authority_threat", r"\b(police|cbi|ed|customs|narcotics|court|arrest|fir|cyber cell|trai|rbi)\b.{0,60}\b(case|warrant|arrest|legal action|suspend|illegal|parcel)\b|digital arrest",
     "claims to be police, a court or a regulator and makes threats"),
    ("job_task", r"\b(work from home|part[- ]time|daily income|earn rs\.? ?\d|like videos|rate (hotels|products)|task)\b.{0,40}\b(earn|income|salary|commission|per day|daily)\b",
     "offers easy money for simple online tasks"),
    ("remote_app", r"\b(anydesk|teamviewer|quicksupport|rustdesk|\.apk|install (this|the) app)\b",
     "asks you to install an app or screen-sharing tool"),
    ("call_number", r"\b(call|contact|whatsapp|sampark)\b.{0,25}(\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}",
     "asks you to call or message a personal mobile number"),
]

URL_RE = re.compile(r"(https?://[^\s<>\"']+|www\.[^\s<>\"']+|\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|in|net|org|top|xyz|info|co|ly|me|io|site|online|link|click|live|vip|cc|shop|club)(?:/[^\s<>\"']*)?)", re.I)


def find_urls(text):
    return [m.group(0).rstrip(".,);!") for m in URL_RE.finditer(text)]


def host_of(url):
    u = url if "://" in url else "http://" + url
    try:
        return (urlparse(u).hostname or "").lower()
    except ValueError:
        return ""


def registrable(host):
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in ("co", "gov", "nic", "org", "net", "ac", "edu", "bank") and parts[-1] == "in":
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def url_indicators(url):
    ev = []
    host = host_of(url)
    if not host:
        return ev
    reg = registrable(host)
    official = reg in OFFICIAL_DOMAINS or host.endswith(OFFICIAL_SUFFIXES)
    if re.fullmatch(r"[\d.]+", host):
        ev.append(("ip_host", f"the link points to a raw IP address ({host})"))
    if reg in SHORTENERS:
        ev.append(("shortener", f"the link uses a URL shortener ({reg}) that hides the real destination"))
    tld = host.rsplit(".", 1)[-1]
    if tld in RISKY_TLDS:
        ev.append(("risky_tld", f"the domain ends in .{tld}, common for throwaway scam sites"))
    for b in BRANDS:
        if b in host and not official:
            ev.append(("brand_lookalike", f"the domain {host} uses the name '{b}' but is not that company's official site"))
            break
    if host.count("-") >= 2 or host.count(".") >= 4:
        ev.append(("complex_host", f"the domain {host} is unusually long or hyphenated"))
    if re.search(r"[0-9]", reg.split(".")[0]) and any(b in re.sub(r"0", "o", reg) for b in BRANDS):
        ev.append(("digit_swap", f"the domain {host} swaps letters for digits to imitate a brand"))
    if "@" in url:
        ev.append(("at_sign", "the link contains an @ sign that can hide the real destination"))
    if url.lower().startswith("http://") and not official:
        ev.append(("no_https", "the link does not use HTTPS"))
    if official:
        ev.append(("official_domain", f"the domain {reg} is an official domain"))
    return ev


def text_indicators(text):
    t = text.lower()
    ev = [(name, desc) for name, pat, desc in TEXT_RULES if re.search(pat, t)]
    for u in find_urls(text):
        for name, desc in url_indicators(u):
            ev.append((name, desc))
    return ev


FLOW_RULES = [
    ("port_scan", r"\b(\d{2,} (different|distinct) ports|port scan|many ports|sequential ports)\b", "connections to many ports look like a port scan"),
    ("brute_force", r"\b(\d{2,} failed (logins?|login attempts|password)|brute.?force|repeated failed)\b", "many failed logins look like password guessing"),
    ("flood", r"\b(syn flood|\d{3,} (syn|half-open|connections) (packets )?(per|in|within)|flood|ddos|dos)\b", "a burst of connections looks like a flood / denial-of-service attempt"),
    ("rejected", r"\b(rejected|reset|rst|refused|s0)\b", "most connections were rejected or reset"),
    ("root", r"\b(root shell|su attempt|privilege)\b", "the session tried to gain root privileges"),
]


def flow_text_indicators(text):
    t = text.lower()
    return [(n, d) for n, p, d in FLOW_RULES if re.search(p, t)]
