"""Unsafe Llama advice is removed from risky explanations; warnings and the opening are kept."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "candidates" / "BEST"))
from triage import llm  # noqa: E402

OPEN = "This message is DANGEROUS: threatens to block the account or service"
TAIL = llm.ACTIONS[1][0]


def test_drops_compliance_on_scam():
    text = OPEN + ". Immediately verify the KYC process to avoid account suspension."
    assert llm._consistent(text, 1, OPEN, TAIL) == OPEN + ". " + TAIL


def test_network_events_are_not_compliance_checked():
    opening = "This network event is DANGEROUS: looks like a port scan"
    text = opening + ". Update your firewall rules and check the logs."
    assert llm._consistent(text, 1, opening, None) == text


def test_keeps_warning_on_scam():
    text = OPEN + ". Do not click on it, it may harm your device."
    assert llm._consistent(text, 1, OPEN, TAIL) == text


def test_keeps_trusted_channel_advice():
    text = OPEN + ". Call your bank on the number you already trust."
    assert llm._consistent(text, 1, OPEN, TAIL) == text


def test_opening_is_never_dropped():
    opening = "This link is DANGEROUS: asks you to verify KYC or personal details"
    assert llm._consistent(opening + ".", 1, opening, TAIL) == opening + "."


def test_suspicious_drops_compliance():
    opening = "This message needs a check: asks to verify KYC or personal details"
    text = opening + ". Update your details at the link today."
    tail = llm.ACTIONS["uncertain"][0]
    assert llm._consistent(text, "uncertain", opening, tail) == opening + ". " + tail


def test_benign_advice_untouched():
    text = "No risk found for this message: reads like a routine bill reminder. Pay it in the app."
    assert llm._consistent(text, 0, "No risk found") == text

