"""Tests for Call Guard: digital-arrest call rules, pure-NumPy ASR helpers, fusion, feature flag & CLI."""
import base64
import json
import os
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

CAND = Path(__file__).resolve().parents[1]
REPO = CAND.parents[1]
sys.path.insert(0, str(CAND))

from app import server  # noqa: E402
from triage import asr, callguard, callrules, llm  # noqa: E402


# ---- Indian 'digital arrest' & call-script rules ------------------------------------------------

@pytest.mark.parametrize("transcript,expected_signal", [
    (
        "This is Inspector Rajesh Sharma from Mumbai Cyber Crime and CBI. An arrest warrant has been "
        "issued in your name because a parcel with illegal drugs was seized by customs. Do not "
        "disconnect this call and stay on video call alone. Transfer fifty thousand rupees to the "
        "RBI safe verification account immediately or police will arrest you.",
        "safe_account_verify",
    ),
    (
        "Alert from Tri-Telicum Department, your mobile number will be disconnected within two hours "
        "due to an illegal narcotics parcel link to your ad-har card. Stay on the line and do not "
        "tell your family. Press 9 to speak to the cyber officer and verify your bank account.",
        "telecom_ivr_scam",
    ),
    (
        "You are under digital arrest by Delhi Police and Enforcement Directorate. Keep the camera "
        "on, close the room door and do not inform your spouse or lawyer.",
        "video_isolation",
    ),
    (
        "नमस्ते, मैं मुंबई साइबर पुलिस और सीबीआई से बोल रहा हूँ। आपके नाम से पार्सल में ड्रग्स मिले हैं "
        "और गिरफ्तारी वारंट जारी हुआ है। फोन मत काटिए, कमरे में अकेले वीडियो कॉल पर रहिए और "
        "किसी को मत बताइए। तुरंत आरबीआई वेरिफिकेशन खाते में पैसे ट्रांसफर कीजिए।",
        "arrest_warrant",
    ),
    (
        "Hi sir, this is customs department calling. Your FedEx parcel contains MDMA drugs linked to "
        "your Aadhaar. Break your fixed deposit and move funds to the Supreme Court escrow account "
        "which will be refunded after verification.",
        "contraband_parcel",
    ),
    (
        "Please install AnyDesk on your phone and read out the six digit OTP so our bank officer "
        "can cancel the charge.",
        "call_secret_or_remote",
    ),
])
def test_digital_arrest_and_call_scam_scripts_flagged(transcript, expected_signal):
    res = callrules.analyze_call(transcript)
    assert res["label"] == 1
    assert expected_signal in res["signals"]
    assert res["evidence"]
    fused = callguard.classify_call(transcript)
    assert fused["verdict"] == "malicious"
    assert fused["stop_warning"] is True
    assert any("1930" in a for a in fused["actions"])
    assert any("Chakshu" in a or "sancharsaathi" in a.lower() for a in fused["actions"])
    assert "STOP" in fused["speech_script"]


@pytest.mark.parametrize("transcript", [
    "Hello, this is a routine security reminder from State Bank of India. Never share your OTP, "
    "you be pin or password on any phone call. If you did not authorize a card transaction, block "
    "your card directly inside the official Yonu app or visit your home branch.",
    "Hi, this is Priya from City Dental Clinic calling to confirm your appointment tomorrow at "
    "11 AM. Also, your courier delivery arrived at the building reception desk. No fee or payment "
    "is required. Please call back whenever it is convenient.",
    "Fraud awareness bulletin: real police, CBI and RBI never conduct digital arrest over video "
    "call and never ask citizens to transfer money to a safe verification account.",
    "Hey mom, I reached Pune safely. Call me back in the evening when you are free, no hurry.",
])
def test_benign_calls_and_security_reminders_not_flagged(transcript):
    res = callrules.analyze_call(transcript)
    assert res["label"] == 0, res
    fused = callguard.classify_call(transcript)
    assert fused["verdict"] == "benign", fused
    assert fused["stop_warning"] is False


def test_callguard_fuses_existing_sms_detector_on_non_digital_arrest_scam():
    # A voice note reading out a KBC lottery / upfront fee scam should still be caught by the
    # existing Prahari SMS/Indic detector even without digital-arrest keywords.
    transcript = "Congratulations! You won Rs 25 lakh in KBC lottery. Pay Rs 5000 processing fee to 9876543210 to claim your prize."
    fused = callguard.classify_call(transcript)
    assert fused["verdict"] == "malicious"
    assert fused["stop_warning"] is True
    assert fused["evidence"]


# ---- Pure-NumPy ASR utilities (no torch / executorch required in CI) ----------------------------

def _write_wav(path: Path, sr: int = 16000, seconds: float = 0.5, channels: int = 1, width: int = 2):
    t = np.linspace(0.0, seconds, int(sr * seconds), endpoint=False)
    sig = (0.25 * np.sin(2.0 * np.pi * 440.0 * t))
    if width == 2:
        arr = (sig * 32767.0).astype(np.int16)
    elif width == 1:
        arr = np.clip((sig * 127.0) + 128.0, 0, 255).astype(np.uint8)
    else:
        arr = (sig * 2147483647.0).astype(np.int32)
    if channels > 1:
        arr = np.repeat(arr[:, None], channels, axis=1).reshape(-1)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(width)
        wf.setframerate(sr)
        wf.writeframes(arr.tobytes())


def test_wav_loader_and_log_mel_shape_and_resampling(tmp_path):
    p = tmp_path / "tone_8k_stereo.wav"
    _write_wav(p, sr=8000, seconds=0.5, channels=2, width=2)
    wav16, dur = asr.load_audio_16k(p)
    assert wav16.dtype == np.float32
    assert 0.48 <= dur <= 0.52
    assert abs(len(wav16) - 8000) <= 2

    mel = asr.log_mel_spectrogram(wav16)
    assert mel.shape == (1, 80, 3000)
    assert mel.dtype == np.float32
    assert np.isfinite(mel).all()
    assert mel.max() <= 1.5 and mel.min() >= -1.5


def test_split_chunks_caps_long_audio():
    long_wav = np.zeros(asr.SAMPLE_RATE * 150, dtype=np.float32)
    chunks = asr.split_chunks(long_wav)
    assert len(chunks) == asr.MAX_CHUNKS
    assert all(len(c) == asr.CHUNK_SAMPLES for c in chunks)


def test_pure_whisper_tokenizer_decodes_bpe_and_skips_specials(tmp_path):
    tok_json = tmp_path / "tokenizer.json"
    tok_json.write_text(json.dumps({
        "model": {"vocab": {"Hello": 10, "\u0120world": 11, "!": 12}},
        "added_tokens": [
            {"id": 50258, "content": "<|startoftranscript|>", "special": True},
            {"id": 50257, "content": "<|endoftext|>", "special": True},
        ],
    }), encoding="utf-8")
    tok = asr.PureWhisperTokenizer(tok_json)
    assert tok.decode([50258, 10, 11, 12, 50257], skip_special_tokens=True) == "Hello world!"


def test_repetition_guard_detects_loop():
    assert asr.find_repeated_suffix_pattern([1, 2, 3, 4, 3, 4, 3, 4]) == 2
    assert asr.find_repeated_suffix_pattern([1, 2, 3, 4, 5, 6]) is None


def test_missing_whisper_model_raises_helpful_error(tmp_path, monkeypatch):
    monkeypatch.setenv("PRAHARI_WHISPER_DIR", str(tmp_path / "empty"))
    monkeypatch.setenv("HC_MODEL_REGISTRY", str(tmp_path / "no_reg.json"))
    with pytest.raises(asr.ModelMissingError, match="setup-model"):
        asr.resolve_whisper_dir(tmp_path / "empty")


# ---- Llama STOP prompt, consent gate, feature flag, demo fixtures & CLI -------------------------

def test_call_prompt_forces_stop_opening_and_explain_with_fake_runner():
    transcript = "This is CBI Mumbai. Do not disconnect and transfer money to RBI safe account."
    res = callguard.classify_call(transcript)
    prompt = callguard.build_call_prompt(transcript, res["label"], res["evidence"], res["is_digital_arrest"])
    assert "STOP — This call is DANGEROUS" in prompt
    assert "Verdict: DANGEROUS" in prompt
    assert llm._prompt_verdict(prompt) == 1

    class FakeExplainer:
        def generate(self, p):
            return "STOP — This call is DANGEROUS: fake CBI arrest scam. Hang up and report on Chakshu or 1930.", {
                "backend": "executorch", "model": "llama32-1b-qlora", "generated_tokens": 18,
            }

    explained = callguard.explain_call(transcript, res, explainer=FakeExplainer())
    assert explained["explanation_status"] == "success"
    assert explained["explanation"].startswith("STOP")
    assert explained["llm"]["backend"] == "executorch"


def test_record_requires_explicit_consent(tmp_path):
    with pytest.raises(ValueError, match="consent"):
        callguard.record_mic_with_consent(5, tmp_path / "out.wav", consent=False)


def test_feature_flag_default_off_and_server_isolation(monkeypatch):
    monkeypatch.delenv("PRAHARI_CALL_GUARD", raising=False)
    assert callguard.is_enabled() is False
    monkeypatch.setenv("PRAHARI_CALL_GUARD", "1")
    assert callguard.is_enabled() is True


def test_server_callguard_endpoint_gated_by_feature_flag(monkeypatch):
    import http.client
    import threading

    monkeypatch.delenv("PRAHARI_CALL_GUARD", raising=False)
    httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.H)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        # Disabled by default -> 404 on /api/callguard, core UI unchanged.
        conn = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=5)
        conn.request("POST", "/api/callguard", json.dumps({"transcript": "hello", "explain": False}).encode())
        resp = conn.getresponse()
        assert resp.status == 404
        resp.read()
        conn.close()

        # Enabled via feature flag -> works cleanly for transcript checks.
        monkeypatch.setenv("PRAHARI_CALL_GUARD", "1")
        conn = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=5)
        body = json.dumps({
            "transcript": "This is CBI inspector. Do not disconnect and transfer money to RBI safe account.",
            "explain": False,
        }).encode()
        conn.request("POST", "/api/callguard", body)
        resp = conn.getresponse()
        assert resp.status == 200
        data = json.loads(resp.read())
        assert data["verdict"] == "malicious" and data["stop_warning"] is True
        conn.close()
    finally:
        httpd.shutdown()
        thread.join()
        httpd.server_close()


def test_cli_transcript_and_help_work_offline(tmp_path):
    env = dict(os.environ, HC_PY=sys.executable)
    p = subprocess.run([str(CAND / "bin" / "callguard"), "--help"], env=env, capture_output=True, text=True)
    assert p.returncode == 0 and "--demo" in p.stdout and "--consent" in p.stdout

    out_json = tmp_path / "res.json"
    p2 = subprocess.run(
        [
            str(CAND / "bin" / "callguard"),
            "--transcript",
            "CBI officer here. Arrest warrant issued. Do not disconnect, stay on video call, transfer to RBI safe account.",
            "--no-explain",
            "--out", str(out_json),
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert p2.returncode == 0, p2.stderr
    res = json.loads(out_json.read_text(encoding="utf-8"))
    assert res["verdict"] == "malicious" and res["is_digital_arrest"] is True


def test_demo_audio_fixtures_present_and_readable():
    items = callguard.demo_manifest()
    assert len(items) >= 4
    expected_set = {it["expected"] for it in items}
    assert {"malicious", "benign"} <= expected_set
    for it in items:
        wav, dur = asr.load_audio_16k(it["path"])
        assert len(wav) > 0 and dur >= 5.0


def test_clean_bank_reminder_text_is_benign_not_only_after_asr_errors():
    # The exact demo script (before Whisper mishears "UPI PIN" / "YONO") must also stay benign.
    res = callguard.classify_call(
        "Hello, this is a routine security reminder from State Bank of India. Never share your OTP, "
        "UPI PIN, or password on any phone call. If you did not authorize a card transaction, block "
        "your card directly inside the official YONO app or visit your home branch."
    )
    assert res["verdict"] == "benign" and res["stop_warning"] is False


def test_scam_borrowing_protective_wording_still_stops():
    res = callguard.classify_call(
        "This is the RBI vigilance department. Never share your OTP with anyone. Your account is under "
        "investigation, so transfer your savings to the RBI safe account for verification today."
    )
    assert res["verdict"] == "malicious" and res["stop_warning"] is True


def test_block_threat_call_without_protective_framing_is_not_cleared():
    res = callguard.classify_call(
        "Your SIM card will be blocked within two hours. Press 9 now and tell the officer your Aadhaar number."
    )
    assert res["verdict"] != "benign"


def test_native_stdout_is_kept_off_json_stdout(capfd):
    # The ExecuTorch LLM runner writes tokens to fd 1; the CLI's JSON on stdout must stay clean.
    with callguard._native_stdout_to_stderr():
        os.write(1, b"runner-noise\n")
    out, err = capfd.readouterr()
    assert "runner-noise" not in out and "runner-noise" in err
