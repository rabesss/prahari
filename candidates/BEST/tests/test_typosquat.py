"""Typosquats of Indian official domains and direct .apk links (triage/typosquat.py)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from triage import detect, indicrules, llm, mech, rules, typosquat  # noqa: E402

HITS = {
    # one letter dropped, doubled or two letters swapped
    "hdfcbnk.com": "hdfcbank.com", "hfdcbank.com": "hdfcbank.com", "icicibnak.com": "icicibank.com",
    "www.hdfcbankk.com": "hdfcbank.com", "ucobnak.com": "ucobank.com", "patym.com": "paytm.com",
    "phonpe.com": "phonepe.com", "airtle.in": "airtel.in", "digilockr.com": "digilocker.gov.in",
    "bluedartt.com": "bluedart.com", "delhivry.com": "delhivery.com",
    "unionbankofindla.co.in": "unionbankofindia.co.in",
    # letters that look alike: l for i, rn for m
    "epfindla.com": "epfindia.gov.in", "lcicibank.com": "icicibank.com", "paytrn.com": "paytm.com",
    # brand plus filler words, joined or hyphenated
    "sbionline.com": "sbi.co.in", "sbi-online-in.com": "sbi.co.in", "irctcrefund.com": "irctc.co.in",
    "irctc-refund.in": "irctc.co.in", "incometax-gov.in": "incometax.gov.in", "hdfcbank-kyc.com": "hdfcbank.com",
    "hdfcbnk-online.com": "hdfcbank.com", "epfo-claim.in": "epfindia.gov.in", "secure.sbionline.co": "sbi.co.in",
    # tenants of free hosting platforms and multi-label country endings
    "hfdcbank.github.io": "hdfcbank.com", "icicibnak.vercel.app": "icicibank.com",
    "sbionline.web.app": "sbi.co.in", "unionbankofindla.com.br": "unionbankofindia.co.in",
    "hfdcbank.com.br": "hdfcbank.com",
}
NON_HITS = [
    # official sites, their subdomains and restricted registries
    "www.hdfcbank.com", "netbanking.hdfcbank.com", "retail.onlinesbi.sbi", "onlinesbi.sbi.bank.in", "sbi.bank.in",
    "www.irctc.co.in", "irctc.com", "www.incometax.gov.in", "lncometax.gov.in", "eportal.incometax.gov.in",
    "m.paytm.com", "digilocker.gov.in", "kotak.bank.in",
    # bank group companies and brand-owned sister domains
    "sbicard.com", "sbilife.co.in", "sbimf.com", "hdfclife.com", "hdfcergo.com", "icicidirect.com",
    "iciciprulife.com", "jiomart.com", "jiocinema.com", "mypaytm.com", "paytm.me", "paytmbank.com", "mydtdc.in",
    "airtel.com", "onlinesbi.com", "axisbank.co.in", "hdfcbk.io", "phon.pe", "npcisupport.org.in",
    # other real companies one edit away (top-1M check)
    "ecobank.com", "cobank.com", "rbcbank.com", "axosbank.com", "idfcbank.com", "bluecart.com", "indiahost.co",
    "delivery.com", "kodak.com", "kotaku.com", "kotka.fi", "recharge.com", "canadabanks.net", "xpressbet.com",
    "google.com", "example.org",
    # placeholders, IPs and non-Latin hosts are other rules' business
    "paytm.example", "hdfcbnk.test", "10.0.0.1", "xn--hdfcbnk-xyz.com",
]


@pytest.mark.parametrize("host,official", sorted(HITS.items()))
def test_typosquat_hits(host, official):
    assert typosquat.match(host) == official


@pytest.mark.parametrize("host", NON_HITS)
def test_typosquat_non_hits(host):
    assert typosquat.match(host) is None


@pytest.mark.parametrize("reg", sorted(typosquat.OFFICIAL))
def test_official_domains_never_flagged(reg):
    for host in (reg, "www." + reg, "login." + reg, "netbanking.secure." + reg, "airbilling." + reg):
        assert typosquat.match(host) is None
        names = [n for n, _ in rules.url_indicators("https://" + host + "/")]
        assert "typosquat" not in names and "brand_lookalike" not in names and "official_domain" in names
        # The SMS rules keep main's official list; the typosquat check adds nothing for these hosts.
        assert "lookalike of the official" not in mech.host_risk(host)
        assert "typosquat" not in (indicrules.host_risk(host) or ("",))


@pytest.mark.parametrize("text", [
    "SBI customer, enter OTP at https://sbi-login.ecomexpress.in/verify",
    "SBI customer, enter OTP at https://login.ecomexpress.in/verify",
    "Vodafone customer, enter OTP at https://vodafone-login.ecomexpress.in/verify",
])
def test_listed_domain_does_not_clear_a_phish_in_a_message(text):
    # Terra on #70 (rounds 1 and 3): the new list must not make a message's link an official channel.
    assert detect.predict_text([text])[0][0] != 0


def test_distance():
    assert typosquat.distance("hdfcbank", "hdfcbnak") == 1
    assert typosquat.distance("hdfcbank", "hdfcbak") == 1
    assert typosquat.distance("ucobank", "ecobank") == 1
    assert typosquat.distance("ucobank", "ecobank", sub_cost=2) == 2
    assert typosquat.distance("epfindia", "epfindla", sub_cost=2) == 1


def test_url_indicator_only_when_brand_rules_miss():
    names = [n for n, _ in rules.url_indicators("https://hfdcbank.com/login")]
    assert names.count("typosquat") == 1 and "brand_lookalike" not in names
    # "hdfc" is already in the host, so the brand rule fires and the typosquat is not counted twice.
    names = [n for n, _ in rules.url_indicators("https://hdfcbnk.com/login")]
    assert "brand_lookalike" in names and "typosquat" not in names


def test_url_typosquat_is_not_cleared():
    lab, _, ev = detect.predict_url(["https://hfdcbank.com/login"])[0]
    assert lab != 0
    assert any("lookalike of the official hdfcbank.com" in e for e in ev)


@pytest.mark.parametrize("url,hit", [
    ("http://sbi-rewards.top/SBI_Rewards.apk", True), ("https://files.example.in/app.APK?v=2", True),
    ("http://x.in/SBI%2Eapk", True), ("x.in/a.apk#top", True), ("https://a.in/dl?file=x.apk", False),
    ("https://a.in/apk-guide.html", False), ("https://www.sbi.co.in/yono.apk", False),
    ("https://play.google.com/store/apps/details?id=com.sbi.lotusintouch", False),
])
def test_apk_download(url, hit):
    assert typosquat.apk_download(url) is hit
    names = [n for n, _ in rules.url_indicators(url)]
    assert ("apk_download" in names) is hit


def test_sms_with_typosquat_link_is_risky():
    a = mech.analyze("Dear customer, your ICICI account is blocked. Verify at icicibnak.com today.")
    assert any("lookalike of the official icicibank.com" in r for r in a["risky"])
    # A plain .com lookalike carrying the brand name was not risky to the SMS rules before.
    a = mech.analyze("Your HDFC netbanking will expire. Update at hdfcbnk.com")
    assert any("hdfcbank.com" in r for r in a["risky"])


def test_sms_with_official_link_is_not_risky():
    for text in ("Book tickets only on irctc.co.in or irctc.com.",
                 "Your Vi bill is ready. Pay on myvi.in or the Vi app."):
        a = mech.analyze(text)
        assert not any("lookalike of the official" in r for r in a["risky"])


def test_compact_evidence_and_hindi():
    url = "https://hfdcbank.com/login"
    ev = llm.compact_evidence("url", url, [], verdict=1)
    assert ev and ev[0].endswith("lookalike domain hfdcbank.com")
    assert llm.scam_type("url", url, 1) == "a phishing link on a lookalike domain"
    apk = "http://update-app.in/kyc.apk"
    assert llm.APK_SHORT in llm.compact_evidence("url", apk, [], verdict=1)
    from triage import explain_hi
    hi = explain_hi.translate(typosquat.describe("icicibnak.com", "icicibank.com"))
    assert hi and "icicibnak[.]com" in hi and "icicibank.com" in hi
    assert explain_hi.translate(llm.APK_SHORT)
