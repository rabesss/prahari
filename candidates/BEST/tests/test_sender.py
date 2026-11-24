"""Optional sender check (triage/sender.py): warn-only, negative-only.

The property test draws texts from the visible fixtures and stress suites (never a holdout set)
and senders from DLT headers, mobile numbers and junk, and checks that a sender never lowers a
result, that only a personal mobile number changes anything, and that no output gains safe or
verified wording because of a sender.
"""
import json
import random
import re
import sys
from pathlib import Path

import pytest

C = Path(__file__).resolve().parents[1]
ROOT = C.parents[1]
sys.path.insert(0, str(C))
from triage import detect, llm, sender  # noqa: E402

MOBILE = "+91 98765 43210"


def _texts():
    out = []
    for path in [ROOT / "bench/fixtures/sms.jsonl", C / "tests/explain_cases.jsonl",
                 *sorted((ROOT / "research/stress").glob("*.jsonl"))]:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                text = row.get("input") or row.get("text")
                if isinstance(text, str) and text.strip():
                    out.append(text)
    return out


TEXTS = _texts()
HEADERS = ["AX-HDFCBK-S", "AX-HDFCBK-T", "VM-SBIINB-P", "AD-GOVTIN-G", "HDFCBK", "JD-ICICIB", "VK-123456",
           "BZ-AIRTEL", "ax-hdfcbk-s", "TX-INDPST-T"]
MOBILES = ["9876543210", "+91 98765 43210", "+919876543210", "09876543210", "98765-43210", "6123456789"]
OTHER = ["", "   ", None, "hello", "123456", "5876543210", "+1 415 555 0100", "1600123456", "140123456",
         "AX-HDFCBK-X", "Mom", "SBI Bank", "98765"]
SAFE_WORDS = re.compile(r"\b(?:safe|verified|genuine|legit\w*|authentic|trusted)\b|"
                        r"सुरक्षित|असली|सत्यापित|भरोसेमंद", re.I)


# ---------------------------------------------------------------------------------- parser
@pytest.mark.parametrize("raw,kind,entity,suffix", [
    ("AX-HDFCBK-S", "dlt", "HDFCBK", "S"), ("AX-HDFCBK-T", "dlt", "HDFCBK", "T"),
    ("VM-SBIINB-P", "dlt", "SBIINB", "P"), ("AD-GOVTIN-G", "dlt", "GOVTIN", "G"),
    ("HDFCBK", "dlt", "HDFCBK", None), ("ax-hdfcbk-s", "dlt", "HDFCBK", "S"),
    ("VK-123456", "dlt", "123456", None), ("JD-ICICIB", "dlt", "ICICIB", None),
])
def test_parse_dlt_headers(raw, kind, entity, suffix):
    p = sender.parse(raw)
    assert p["kind"] == kind and p["entity"] == entity and p["suffix"] == suffix


@pytest.mark.parametrize("raw", MOBILES)
def test_parse_mobile_numbers(raw):
    p = sender.parse(raw)
    assert p["kind"] == "mobile" and len(p["number"]) == 10 and p["number"][0] in "6789"


@pytest.mark.parametrize("raw,kind", [
    ("1600123456", "1600"), ("+91-1600-123-456", "1600"), ("123456", "other"), ("5876543210", "other"),
    ("+1 415 555 0100", "other"), ("SBI Bank", "other"), ("AX-HDFCBK-X", "other"), ("98765", "other"),
])
def test_parse_other_senders(raw, kind):
    assert sender.parse(raw)["kind"] == kind


@pytest.mark.parametrize("raw", ["", "   ", None])
def test_parse_empty(raw):
    assert sender.parse(raw) is None


# ---------------------------------------------------------------------------------- raising
RAISE = [
    ("Dear customer, your SBI a/c XX1234 is debited Rs 5000. Not you? Call 1800111109", "alert"),
    ("Your OTP for login is 482910. Do not share it with anyone. -HDFC Bank", "alert"),
    ("Please share the OTP you just received, I sent it by mistake", "request"),
    ("Your Jio SIM will be deactivated today. Call 9123456780", "identity"),
    ("Your parcel is held at customs, pay Rs 49 at http://indiapost-fee.example", "identity"),
    ("प्रिय ग्राहक, आपका खाता बंद हो जाएगा, केवाईसी अपडेट करें", "request"),
    ("Aapka bijli connection aaj raat kat jayega, turant call karein", "identity"),
    ("Dear customer your SBI KYC is expiring, update now or the account will be blocked", "request"),
]
NO_RAISE = [
    "Papa I paid the bank EMI today, will call later",
    "I have an SBI statement for our meeting tomorrow",
    "SBI never asks for your OTP or PIN. Stay alert.",
    "मैं बैंक जा रहा हूँ, शाम को बात करते हैं",
    "bhai bank ka kaam ho gaya, kal milte hai",
    "Send 500 for dinner yaar",
    "Reached home. The courier guy was late again lol",
]


@pytest.mark.parametrize("text,why", RAISE)
def test_mobile_sender_raises_official_looking_text(text, why):
    assert sender.reason("sms", text, MOBILE) == why
    lab, score, ev = detect.classify_any("sms", text, MOBILE)
    base = detect.classify_any("sms", text)
    assert sender.rank(lab) >= max(sender.rank(base[0]), sender.rank("uncertain"))
    assert ev[0] == sender.SENDER_LINE
    assert float(score) >= float(base[1])


@pytest.mark.parametrize("text", NO_RAISE)
def test_personal_chat_and_warnings_are_not_raised(text):
    assert sender.reason("sms", text, MOBILE) is None
    assert detect.classify_any("sms", text, MOBILE) == detect.classify_any("sms", text)


@pytest.mark.parametrize("text,_", RAISE)
@pytest.mark.parametrize("hdr", HEADERS)
def test_registered_header_changes_nothing(text, _, hdr):
    assert sender.reason("sms", text, hdr) is None
    assert detect.classify_any("sms", text, hdr) == detect.classify_any("sms", text)


def test_only_text_kinds_use_the_sender():
    assert sender.reason("url", "http://sbi-kyc.example/your-account", MOBILE) is None
    assert sender.reason("flow", "dear customer your bank account", MOBILE) is None
    assert sender.reason("upi", "upi://pay?pa=x@ybl&pn=Your%20SBI%20account", MOBILE) is None


def test_dangerous_stays_dangerous():
    text = "Your SBI KYC expires tonight. Send your OTP to 9123456780 now or the account will be blocked."
    assert detect.classify_any("sms", text)[0] == 1
    lab, _, ev = detect.classify_any("sms", text, MOBILE)
    assert lab == 1 and ev[0] == sender.SENDER_LINE


# ------------------------------------------------------------------- negative-only property
def test_property_sender_never_lowers_risk_and_only_mobiles_matter():
    rng = random.Random(20261124)
    pool = HEADERS + MOBILES + OTHER
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-+ "
    raised = 0
    for i, text in enumerate(TEXTS):
        kind = "injection" if i % 7 == 0 else "sms"
        base = detect.classify_any(kind, text)
        senders = rng.sample(pool, 4) + ["".join(rng.choice(letters) for _ in range(rng.randint(1, 14)))]
        for sid in senders:
            got = detect.classify_any(kind, text, sid)
            assert sender.rank(got[0]) >= sender.rank(base[0]), (text, sid)
            assert float(got[1]) >= float(base[1]), (text, sid)
            p = sender.parse(sid)
            if not p or p["kind"] != "mobile":
                assert got == base, (text, sid)
            else:
                raised += got != base
            added = [e for e in got[2] if e not in base[2]]
            assert not any(SAFE_WORDS.search(str(e)) for e in added), (text, sid, added)
    assert len(TEXTS) > 100 and raised > 0


def test_cli_rows_without_sender_are_unchanged(tmp_path):
    from triage import cli
    rows = [{"id": str(i), "text": t} for i, t in enumerate(TEXTS[:40])]
    inp, a, b = tmp_path / "in.jsonl", tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    cli.write_jsonl(inp, rows)
    cli.main(["predict", "--task", "sms", "--in", str(inp), "--out", str(a)])
    expect = [{"id": r["id"], "label": lab, "score": round(s, 4), "evidence": ev}
              for r, (lab, s, ev) in zip(rows, detect.predict_text([r["text"] for r in rows]))]
    assert cli.read_jsonl(a) == expect
    cli.write_jsonl(inp, [dict(r, sender="AX-HDFCBK-S") for r in rows])
    cli.main(["predict", "--task", "sms", "--in", str(inp), "--out", str(b)])
    assert cli.read_jsonl(b) == expect


def test_cli_mobile_sender_raises_row(tmp_path):
    from triage import cli
    inp, out = tmp_path / "in.jsonl", tmp_path / "out.jsonl"
    cli.write_jsonl(inp, [{"id": "1", "text": RAISE[0][0], "sender": MOBILE}])
    cli.main(["predict", "--task", "sms", "--in", str(inp), "--out", str(out)])
    row = cli.read_jsonl(out)[0]
    assert row["label"] in ("uncertain", 1) and row["evidence"][0] == sender.SENDER_LINE


# ---------------------------------------------------------------------- wording and Llama
def test_vetted_lines_have_no_safe_wording_and_hindi_is_devanagari():
    for line in [sender.SENDER_LINE, sender.SENDER_FACT, sender.NOTE_1600, *sender.OPENING.values()]:
        assert not SAFE_WORDS.search(line)
    for hi in [sender.SENDER_LINE_HI, sender.NOTE_1600_HI]:
        assert re.search(r"[ऀ-ॿ]", hi) and not SAFE_WORDS.search(hi)
    table = json.loads((ROOT / "android/python/strings_hi.json").read_text(encoding="utf-8"))
    assert table["evidence"][sender.SENDER_LINE] == sender.SENDER_LINE_HI
    for key in ("sender_label", "sender_hint", "sender_note"):
        item = table["new"][key]
        assert item["en"] and re.search(r"[ऀ-ॿ]", item["hi"])


class _FakeExplainer(llm.Explainer):
    def __init__(self, reply):
        self.reply = reply
        self.prompts = []

    def _run(self, prompt):
        self.prompts.append(prompt)
        return self.reply(prompt), {"generated_tokens": 30}


def test_prompt_carries_vetted_sender_phrase_and_fact():
    text = RAISE[0][0]
    why = sender.reason("sms", text, MOBILE)
    lab, _, ev = detect.classify_any("sms", text, MOBILE)
    ex = _FakeExplainer(lambda p: "")
    prompt = ex.prompt("sms", text, lab, ev, sender_reason=why, sender_id=MOBILE)
    assert sender.OPENING[why] in prompt and sender.SENDER_FACT in prompt
    # Without a sender the prompt is exactly the old one.
    base = detect.classify_any("sms", text)
    assert ex.prompt("sms", text, base[0], base[2]) == ex.prompt("sms", text, base[0], base[2], None, None)


def test_paraphrase_survives_and_header_never_reaches_prompt():
    text = RAISE[0][0]
    why = sender.reason("sms", text, MOBILE)
    lab, _, ev = detect.classify_any("sms", text, MOBILE)
    opening = f"This message needs a check: {sender.OPENING[why]}"
    ex = _FakeExplainer(lambda p: f"{opening}. Real banks use registered sender IDs, not mobile numbers.")
    out, _ = ex.generate(ex.prompt("sms", text, lab, ev, sender_reason=why, sender_id=MOBILE))
    assert out.startswith(opening)
    ex2 = _FakeExplainer(lambda p: "x")
    ex2.prompt("sms", text, *detect.classify_any("sms", text, "AX-HDFCBK-S")[::2])
    assert "AX-HDFCBK" not in "".join(ex2.prompts)


def test_call_note_is_advisory_only():
    from triage import callguard
    t = "Hello, this is a routine security reminder from State Bank of India. Never share your OTP."
    res = callguard.classify_call(t)
    assert res["advisory"] == sender.NOTE_1600 and res["advisory_hi"] == sender.NOTE_1600_HI
    res.pop("advisory"), res.pop("advisory_hi")
    assert "1600" not in json.dumps(res)
    assert sender.call_note("Your package will arrive tomorrow") is None


@pytest.mark.parametrize("tail,dropped", [
    ("Real banks use registered sender IDs, not mobile numbers.", False),
    ("Check the payment in your bank app before acting.", False),
    ("The bank sent this from a verified number.", True),
    ("This is a genuine sender, so you can trust it.", True),
    ("Banks use registered sender IDs, so this verified sender is fine, not a scam.", True),
    ("The sender ID looks official.", True),
])
def test_validator_drops_sentences_that_vouch_for_the_sender(tail, dropped):
    text = RAISE[0][0]
    why = sender.reason("sms", text, MOBILE)
    lab, _, ev = detect.classify_any("sms", text, MOBILE)
    opening = f"This message needs a check: {sender.OPENING[why]}"
    ex = _FakeExplainer(lambda p: f"{opening}. {tail}")
    out, stats = ex.generate(ex.prompt("sms", text, lab, ev, sender_reason=why, sender_id=MOBILE))
    assert ("sender_contradiction" in stats["validator"]["dropped"]) == dropped
    if dropped:
        assert tail not in out and sender.SENDER_FACT in out


def test_sender_contradiction_rule_is_off_without_a_sender():
    # The same sentence on a sender-less item is judged by the existing rules only.
    ctx = {"kind": "sms", "input": "Your OTP is 123456", "verdict": 0, "fact": "", "evidence": []}
    assert llm.unsupported("The sender ID looks official.", ctx) != "sender_contradiction"


def test_cli_explain_carries_sender_to_prompt_and_hindi(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from triage import cli
    seen = []

    class Fake:
        def prompt(self, kind, inp, lab, ev, **extra):
            seen.append(extra)
            return inp

        def generate(self, prompt):
            return "Model explanation.", {"generated_tokens": 3}

    monkeypatch.setattr(llm, "Explainer", Fake)
    inp, out = tmp_path / "in.jsonl", tmp_path / "out.jsonl"
    rows = [{"id": 0, "kind": "sms", "input": RAISE[0][0], "sender": MOBILE},
            {"id": 1, "kind": "sms", "input": RAISE[0][0], "sender": "AX-SBIINB-S"},
            {"id": 2, "kind": "sms", "input": RAISE[0][0]}]
    cli.write_jsonl(inp, rows)
    cli.cmd_explain(SimpleNamespace(inp=inp, out=out))
    got = cli.read_jsonl(out)
    assert seen == [{"sender_reason": "alert", "sender_id": MOBILE}, {}, {}]
    assert got[0]["sender_raised"] == "alert" and got[0]["evidence_used"][0] == sender.SENDER_LINE
    assert sender.SENDER_LINE_HI in got[0].get("summary_hi", "")
    strip = lambda r: {k: v for k, v in r.items() if k not in ("id", "latency_ms")}  # noqa: E731
    assert strip(got[1]) == strip(got[2]) and "sender_raised" not in got[2]


def test_web_api_sender_is_optional_and_raise_only():
    from app import server
    plain = server.triage("sms", RAISE[0][0], False)
    assert server.triage("sms", RAISE[0][0], False, "AX-SBIINB-S") == plain
    raised = server.triage("sms", RAISE[0][0], False, MOBILE)
    assert raised["sender_raised"] == "alert" and raised["evidence"][0] == sender.SENDER_LINE
    assert raised["verdict"] in ("uncertain", "malicious")


# Round-1 review (gpt-6.1-terra) regressions.
@pytest.mark.parametrize("text,why", [
    ("Please complete KYC today", "request"),
    ("The door code is 1234. See you!", None),
    ("Gate code is 4521, come up", None),
    ("Banks never ask you to update KYC through a link.", None),
    ("KYC kar do bhai, form mein PAN chahiye tha", None),
])
def test_review_r1_reason_cases(text, why):
    assert sender.reason("sms", text, MOBILE) == why


@pytest.mark.parametrize("sent,bad", [
    ("This sender is verified and not a scam.", True),
    ("Not a scam, this is a genuine sender.", True),
    ("The number is not verified.", False),
    ("It did not come from a registered sender.", False),
    # CodeRabbit round 1
    ("The sender is verified and never requests an OTP.", True),
    ("Banks use registered sender IDs instead of mobiles and this sender is genuine.", True),
    ("Banks send SMS from registered sender IDs, not personal mobile numbers.", False),
])
def test_review_r1_negation_does_not_hide_vouching(sent, bad):
    ctx = {"kind": "sms", "input": "x", "verdict": "uncertain", "fact": "", "evidence": [], "sender_raised": "alert"}
    assert (llm.unsupported(sent, ctx) == "sender_contradiction") == bad


# Round-2 review (gpt-6.1-terra) regressions.
@pytest.mark.parametrize("text,why", [
    ("Your code is 123456 for SBI login", "alert"),
    ("Please complete KYC today. Never share OTP.", "request"),
    ("My KYC is pending, will do it tomorrow", None),
    ("KYC update kar diya bhai, thanks", None),
    ("मेरा केवाईसी अपडेट हो गया", None),
])
def test_review_r2_reason_cases(text, why):
    assert sender.reason("sms", text, MOBILE) == why


@pytest.mark.parametrize("sent,bad", [
    ("The sender is not suspicious and is verified.", True),
    ("The number is not verified.", False),
    ("It did not come from a registered sender.", False),
])
def test_review_r2_negation_stops_at_conjunction(sent, bad):
    ctx = {"kind": "sms", "input": "x", "verdict": "uncertain", "fact": "", "evidence": [], "sender_raised": "alert"}
    assert (llm.unsupported(sent, ctx) == "sender_contradiction") == bad


@pytest.mark.parametrize("sent,bad", [
    # CodeRabbit round 2: over-drops of correct warnings
    ("This message was not sent from your bank.", False),
    ("The sender is not verified and banks use registered IDs.", False),
    ("This was sent from your bank.", True),
])
def test_review_r2_coderabbit_scoping(sent, bad):
    ctx = {"kind": "sms", "input": "x", "verdict": "uncertain", "fact": "", "evidence": [], "sender_raised": "alert"}
    assert (llm.unsupported(sent, ctx) == "sender_contradiction") == bad


# Round-2 review (Grok 4.7) regressions.
@pytest.mark.parametrize("text,why", [
    ("Dear customer, your KYC has expired. Do not share OTP with anyone.", "request"),
    ("Rs.500.00 has been debited from a/c XX1234 on 24Nov. Avl Bal Rs.9000.", "alert"),
    ("Your password is 482910 for HDFC net banking login", "alert"),
    ("bhai aapka refund aa gaya SBI se", None),
    ("आपका पार्सल आ गया?", None),
    ("did your bank card work at the store", None),
    ("bhai tumhara SBI loan kab tak hai", None),
    ("My PAN card update is done", None),
])
def test_review_r2_grok_reason_cases(text, why):
    assert sender.reason("sms", text, MOBILE) == why


@pytest.mark.parametrize("sent,bad", [
    ("The sender is absolutely and fully verified.", True),
    ("The sender of this particular message is verified.", True),
    ("You can trust this sender.", True),
    ("This sender can be trusted.", True),
    ("This came straight from the bank.", True),
    ("You should use this verified sender.", True),
    ("Please trust the official sender.", True),
    ("The real risk is the sender asking for an OTP.", False),
    ("Check the official bank app before acting.", False),
    ("Do not trust this sender.", False),
])
def test_review_r2_grok_vouching(sent, bad):
    ctx = {"kind": "sms", "input": "x", "verdict": "uncertain", "fact": "", "evidence": [], "sender_raised": "alert"}
    assert (llm.unsupported(sent, ctx) == "sender_contradiction") == bad


def test_call_note_needs_a_bank_not_any_card():
    assert sender.call_note("Your SIM card will be blocked, press 9") is None
    assert sender.call_note("This is HDFC Bank calling about your card") == sender.NOTE_1600
