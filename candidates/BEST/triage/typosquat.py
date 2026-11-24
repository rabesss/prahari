"""Typosquats of Indian official domains, and direct .apk downloads.

A scam link often sits on a near copy of a real bank, payment, government or courier domain:
one letter dropped or swapped (``hdfcbnk.com``, ``icicibnak.com``), the real name on another
ending (``onlinesbi.com``), or the real name plus words such as "online" or "kyc"
(``sbionline.com``, ``irctc-refund.in``). This module compares the registrable domain of a host
with a small bundled list of official registrable domains. It never matches an official domain,
any subdomain of one, or a host under a restricted Indian registry (.gov.in, .nic.in, .bank.in,
.ac.in, .edu.in), which only verified owners can register.

The list is short on purpose: the organisations Indian scam messages imitate most. Each entry was
fetched on 24 Nov 2026: most served the organisation's own page or redirected to its .bank.in site;
a few bank sites blocked the automated request but resolved. Domains that no longer resolve or that changed hands were left out (for example psbindia.com now
serves a gambling page), because treating a lapsed domain as official would clear a scam link.
Sources: bank and payment-app names from the RBI list of scheduled commercial banks and the NPCI
list of UPI apps; each domain from the organisation's own website.
"""
import re
from urllib.parse import unquote, urlparse

# registrable domain -> organisation. Labels shorter than five letters are matched only through
# STEMS below (sbi, jio, dtdc), because one edit away from a short name is mostly real words; iob,
# cred and myvi have no stem and are only kept off the flagged side.
OFFICIAL = {
    # banks (RBI list of scheduled commercial banks)
    "sbi.co.in": "State Bank of India", "onlinesbi.sbi": "State Bank of India",
    "hdfcbank.com": "HDFC Bank", "icicibank.com": "ICICI Bank", "axisbank.com": "Axis Bank",
    "kotak.com": "Kotak Mahindra Bank", "pnbindia.in": "Punjab National Bank",
    "bankofbaroda.in": "Bank of Baroda", "canarabank.com": "Canara Bank",
    "unionbankofindia.co.in": "Union Bank of India", "bankofindia.co.in": "Bank of India",
    "indianbank.in": "Indian Bank", "centralbankofindia.co.in": "Central Bank of India",
    "iob.in": "Indian Overseas Bank", "ucobank.com": "UCO Bank",
    "bankofmaharashtra.in": "Bank of Maharashtra", "idbibank.in": "IDBI Bank",
    "indusind.com": "IndusInd Bank", "yesbank.in": "Yes Bank", "idfcfirstbank.com": "IDFC First Bank",
    "bandhanbank.com": "Bandhan Bank", "federalbank.co.in": "Federal Bank", "aubank.in": "AU Small Finance Bank",
    "rblbank.com": "RBL Bank", "southindianbank.com": "South Indian Bank",
    "karnatakabank.com": "Karnataka Bank", "cityunionbank.com": "City Union Bank",
    "paytmbank.com": "Paytm Payments Bank", "rbi.org.in": "Reserve Bank of India",
    # UPI (NPCI and its list of UPI apps)
    "npci.org.in": "NPCI", "bhimupi.org.in": "BHIM (NPCI)", "paytm.com": "Paytm", "phonepe.com": "PhonePe",
    "mobikwik.com": "MobiKwik", "freecharge.in": "Freecharge", "cred.club": "CRED",
    # government services
    "indiapost.gov.in": "India Post", "irctc.co.in": "IRCTC", "irctc.com": "IRCTC",
    "incometax.gov.in": "Income Tax Department", "incometaxindia.gov.in": "Income Tax Department",
    "epfindia.gov.in": "EPFO", "uidai.gov.in": "UIDAI (Aadhaar)", "digilocker.gov.in": "DigiLocker",
    "licindia.in": "LIC",
    # telecoms
    "airtel.in": "Airtel", "jio.com": "Jio", "myvi.in": "Vi (Vodafone Idea)", "bsnl.co.in": "BSNL",
    # couriers
    "bluedart.com": "Blue Dart", "delhivery.com": "Delhivery", "dtdc.com": "DTDC", "dtdc.in": "DTDC",
    "ecomexpress.in": "Ecom Express", "xpressbees.com": "XpressBees", "shadowfax.in": "Shadowfax",
}
# Distinctive brand stems: a host made of a stem plus filler words only ("sbionline", "hdfc-kyc")
# imitates the official domain named here.
STEMS = {
    "sbi": "sbi.co.in", "onlinesbi": "onlinesbi.sbi", "hdfc": "hdfcbank.com", "hdfcbank": "hdfcbank.com",
    "icici": "icicibank.com", "icicibank": "icicibank.com", "axisbank": "axisbank.com",
    "kotak": "kotak.com", "pnb": "pnbindia.in", "bankofbaroda": "bankofbaroda.in", "canarabank": "canarabank.com",
    "idbi": "idbibank.in", "indusind": "indusind.com", "yesbank": "yesbank.in", "rbi": "rbi.org.in",
    "npci": "npci.org.in", "bhim": "bhimupi.org.in", "bhimupi": "bhimupi.org.in", "paytm": "paytm.com",
    "phonepe": "phonepe.com", "mobikwik": "mobikwik.com", "freecharge": "freecharge.in",
    "indiapost": "indiapost.gov.in", "irctc": "irctc.co.in", "incometax": "incometax.gov.in",
    "epfo": "epfindia.gov.in", "epfindia": "epfindia.gov.in", "uidai": "uidai.gov.in", "aadhaar": "uidai.gov.in",
    "digilocker": "digilocker.gov.in", "airtel": "airtel.in", "jio": "jio.com", "bsnl": "bsnl.co.in",
    "bluedart": "bluedart.com", "delhivery": "delhivery.com", "dtdc": "dtdc.in", "xpressbees": "xpressbees.com",
}
# Words a lookalike adds around a brand. Not "bank", "card", "life", "pay" or "money": group
# companies use those (sbicard.com, hdfclife.com, paytmbank.com). Not "my", "app", "support" or
# "india" either: brands register those for themselves (mypaytm.com, mydtdc.in, npcisupport.org.in,
# dtdcindia.com).
FILLER = {
    "online", "net", "netbanking", "ebanking", "login", "signin", "secure", "security", "verify",
    "verification", "kyc", "ekyc", "update", "updates", "care", "customer", "customercare",
    "help", "helpdesk", "helpline", "service", "services", "official", "in",
    "web", "portal", "e", "refund", "refunds", "reward", "rewards", "point", "points", "claim",
    "redeem", "bonus", "gift", "offer", "offers", "alert", "alerts", "unblock", "block", "blocked",
    "activate", "activation", "reactivate", "gov", "govt", "site", "page", "link", "info", "center",
    "centre", "desk", "team", "user", "users", "account", "accounts", "id", "pan", "upi", "tax", "track",
    "tracking", "parcel", "delivery", "courier", "status", "pending", "fine", "challan", "bill", "recharge",
}
# Real words and places that pass the edit rules below (delivery vs delhivery, kotka vs kotak).
NEAR_WORDS = {"delivery", "kotka"}
# Reserved names (RFC 2606/6761) are placeholders in samples, not registrable domains; other rules
# already treat them, and this check leaves them alone.
RESERVED_TLDS = {"example", "test", "invalid", "localhost", "local"}
RESTRICTED = (".gov.in", ".nic.in", ".bank.in", ".ac.in", ".edu.in", ".mil.in", ".res.in")
# Second-level public suffixes ("hdfcbank.co.in" registers under "co.in", "x.com.br" under "com.br").
# With these the top-1M check matches two domains (fecharge.ir, pnbonline.com.br).
SECOND_LEVEL = {"in": {"co", "gov", "nic", "org", "net", "ac", "edu", "bank", "firm", "gen", "ind", "res", "mil"}}
CC_SECOND = {"com", "co", "net", "org", "gov", "edu", "ac"}  # under any two-letter country ending
# Free hosting platforms: each tenant is its own site ("hfdcbank.github.io" is the "hfdcbank" site).
PLATFORMS = ("github.io", "vercel.app", "netlify.app", "pages.dev", "workers.dev", "web.app",
             "firebaseapp.com", "herokuapp.com", "onrender.com", "glitch.me", "blogspot.com", "wixsite.com",
             "weebly.com", "000webhostapp.com", "appspot.com", "azurewebsites.net", "replit.app", "ngrok.io",
             "ngrok-free.app", "duckdns.org", "godaddysites.com", "square.site", "webflow.io", "framer.website")

_OFFICIAL_LABELS = {}
for _reg in OFFICIAL:
    _OFFICIAL_LABELS.setdefault(_reg.split(".")[0], _reg)


def registrable(host):
    """The registrable domain of a host, using a tiny bundled public-suffix list."""
    host = host.lower().strip(".")
    parts = host.split(".")
    for suffix in PLATFORMS:
        if host.endswith("." + suffix):
            return ".".join(parts[-(suffix.count(".") + 2):])
    if len(parts) >= 3 and (parts[-2] in SECOND_LEVEL.get(parts[-1], ()) or
                            (len(parts[-1]) == 2 and parts[-1] != "in" and parts[-2] in CC_SECOND)):
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def is_official(host):
    """An official domain, any subdomain of one, or a restricted-registry host: never a typosquat."""
    host = host.lower().strip(".")
    return host.endswith(RESTRICTED) or any(host == d or host.endswith("." + d) for d in OFFICIAL)


def is_listed(host):
    """A listed official domain or a subdomain of one (no registry suffixes)."""
    host = host.lower().strip(".")
    return any(host == d or host.endswith("." + d) for d in OFFICIAL)


def distance(a, b, cap=3, sub_cost=1):
    """Damerau-Levenshtein distance (optimal string alignment), capped at ``cap``.

    With ``sub_cost=2`` a changed letter costs as much as dropping one and adding another, so only
    dropped, doubled, added or swapped letters count as a single edit. An "l" for an "i" (or the
    reverse) always costs one: the two look alike in most fonts."""
    if abs(len(a) - len(b)) >= cap:
        return cap
    prev2, prev = None, list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            x, y = a[i - 1], b[j - 1]
            cost = 0 if x == y else 1 if {x, y} == {"i", "l"} else sub_cost
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        if min(cur) >= cap:
            return cap
        prev2, prev = prev, cur
    return min(prev[-1], cap)


def _transposed(a, b):
    return len(a) == len(b) and a != b and sorted(a) == sorted(b) and sum(x != y for x, y in zip(a, b)) == 2 \
        and any(a[i] == b[i + 1] and a[i + 1] == b[i] for i in range(len(a) - 1))


def _close(core, label):
    """True when ``core`` is a typo of the official ``label``.

    Checked against the 1M most popular domains (Tranco list, 24 Nov 2026): one changed letter or
    a changed first letter mostly gives another real company (ecobank, rbcbank, axosbank, idfcbank,
    bluecart, indiahost), so the first letter must match and a changed letter costs two edits.
    Names of five or six letters allow only two neighbouring letters swapped after the first two;
    seven to nine letters allow one dropped, added or swapped letter; ten or more allow two such
    edits (or one changed letter)."""
    if core == label or core in NEAR_WORDS or not core or (core[0] != label[0] and {core[0], label[0]} != {"i", "l"}):
        return False
    n = len(label)
    if n < 5:
        return False
    if n <= 6:
        return _transposed(core, label) and core[1] == label[1]
    return distance(core, label, sub_cost=2) <= (1 if n <= 9 else 2)


def _fillers_only(s):
    """True when ``s`` (possibly empty) splits fully into filler words."""
    ok = [True] + [False] * len(s)
    for i in range(1, len(s) + 1):
        ok[i] = any(ok[j] and s[j:i] in FILLER for j in range(max(0, i - 15), i))
    return ok[-1]


def _stem_compound(core):
    for stem, reg in STEMS.items():
        if core != stem and core.startswith(stem) and _fillers_only(core[len(stem):]):
            return reg
        if core != stem and core.endswith(stem) and _fillers_only(core[:-len(stem)]):
            return reg
        # stem inside: filler + stem + filler ("my-sbi-online")
        k = core.find(stem)
        if k > 0 and k + len(stem) < len(core) and _fillers_only(core[:k]) and _fillers_only(core[k + len(stem):]):
            return reg
    return None


def match(host):
    """The official domain a host imitates, or None. Never matches an official host."""
    host = (host or "").lower().strip(".")
    if not host or "." not in host or is_official(host) or "xn--" in host:
        return None
    if re.fullmatch(r"[\d.]+", host) or any(ord(c) > 127 for c in host):
        return None  # IP hosts and non-Latin names have their own rules
    if host.rsplit(".", 1)[-1] in RESERVED_TLDS:
        return None
    reg = registrable(host)
    label = reg.split(".")[0]
    tokens = [t for t in label.split("-") if t]
    joined = "".join(tokens)
    if joined in _OFFICIAL_LABELS:
        # The real name on another ending (onlinesbi.com, paytm.me, airtel.com) is usually the
        # brand's own: the top-1M check found many such sister domains and no clear squat.
        return None
    cores = [joined]
    kept = "".join(t for t in tokens if t not in FILLER)
    if kept and kept != joined:
        # brand plus filler words joined by hyphens ("sbi-online-in", "hdfcbank-kyc")
        if kept in _OFFICIAL_LABELS or kept in STEMS:
            return _OFFICIAL_LABELS.get(kept) or STEMS[kept]
        cores.append(kept)
    # "rn" reads as "m" and "vv" as "w" in small type ("paytrn.com").
    lookalike = joined.replace("rn", "m").replace("vv", "w")
    if lookalike != joined:
        if lookalike in _OFFICIAL_LABELS:
            return _OFFICIAL_LABELS[lookalike]
        cores.append(lookalike)
    for core in cores:
        for lab, off in _OFFICIAL_LABELS.items():
            if _close(core, lab):
                return off
        hit = _stem_compound(core)
        if hit:
            return hit
    return None


def describe(host, official):
    return f"the domain {host} is a lookalike of the official {official}"


def apk_download(url):
    """True when the link itself fetches an .apk file from a non-official host."""
    u = url if "://" in url else "http://" + url
    try:
        parsed = urlparse(u)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    path = unquote(parsed.path).lower().rstrip("/.")
    return (bool(host) and path.endswith(".apk") and not is_official(host)
            and host.rsplit(".", 1)[-1] not in RESERVED_TLDS)


APK_DESC = "the link points straight to an Android app file (.apk), which installs outside the Play Store"
