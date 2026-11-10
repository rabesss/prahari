import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from triage import detect, rules  # noqa: E402


def test_lookalike_domain_flagged():
    names = [n for n, _ in rules.url_indicators("http://sbi-kyc.in-verify.top/login")]
    assert "brand_lookalike" in names and "risky_tld" in names


def test_official_domain_not_lookalike():
    names = [n for n, _ in rules.url_indicators("https://www.irctc.co.in/nget/train-search")]
    assert "brand_lookalike" not in names and "official_domain" in names


def test_text_detector_runs():
    (lab, score, ev), = detect.predict_text(["Your OTP for login is 123456. Do not share it with anyone."])
    assert 0.0 <= score <= 1.0 and isinstance(ev, list)
