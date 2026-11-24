"""Controller tests for the explanation checks in run_eval.py. Run: python eval/test_scorer.py"""
import importlib.util
import pathlib

spec = importlib.util.spec_from_file_location("run_eval", pathlib.Path(__file__).with_name("run_eval.py"))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)

CONSISTENCY = [  # (gold label, explanation, expected)
    (1, "this message is a scam because it asks for your otp.", 1.0),
    (1, "this message is suspicious; it looks legitimate but asks for your otp.", 1.0),
    (1, "it is not safe to reply.", 1.0),
    (1, "this is a scam message that looks legitimate.", 1.0),
    (1, "the link is official-looking, but the domain is a lookalike.", 1.0),
    (1, "it is legitimate-looking but the sender asks for a deposit.", 1.0),
    (1, "this text message is safe because it does not ask you to open a link.", 0.0),
    (1, "this network event is safe because it is regular traffic.", 0.0),
    (1, "this is not a scam.", 0.0),
    (0, "this link is suspicious because it is from indiapost.gov.in.", 0.0),
    (0, "this message seems suspicious.", 0.0),
    (0, "this is a genuine otp message from your bank. never share the code.", 1.0),
    (0, "the message is not a scam: it is a routine debit alert.", 1.0),
    (0, "it looks alarming, but this is a normal bill reminder from the official site.", 1.0),
    (0, "scammers often send messages like this, but this one is legitimate.", 1.0),
]
MENTION = [  # (required, explanation, expected)
    (["failed logins", "brute force"], "repeated brute-force attempts on ssh", True),
    (["threat", "payment"], "they want you to transfer money now", True),
    (["beaconing", "periodic"], "the host contacts a server every 30 seconds", True),
    (["lookalike domain", "kyc"], "the website imitates your bank", True),
    (["port scan", "scan"], "connections from one address in 14 seconds", False),
    (["upi pin", "collect request"], "it asks for your password", False),
]


def test_consistency():
    for y, text, want in CONSISTENCY:
        assert r.consistent(y, text) == want, (y, text)


def test_mention():
    for req, text, want in MENTION:
        assert r.mentions({"required_mentions": req}, text) == want, (req, text)


def test_record_path_is_repo_relative():
    assert r.record_path(r.PROJ / "candidates" / "BEST") == "candidates/BEST"
    assert r.record_path("/nonexistent/elsewhere/cand") == "cand"
    assert not r.record_path(pathlib.Path.home() / "x").startswith("/")

if __name__ == "__main__":
    test_consistency()
    test_mention()
    print("ok", len(CONSISTENCY) + len(MENTION))
