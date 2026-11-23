"""Call Guard: offline scam-call & voice-note triage on Arm (ExecuTorch Whisper + Llama 3.2 1B).

Pipeline:
  WhatsApp voice note / shared audio file (or consented local speakerphone mic recording)
    -> On-device speech-to-text (ExecuTorch Whisper Tiny INT8 XNNPACK)
    -> Existing Prahari detectors (`detect.classify_any("sms", ...)`) + Indian 'digital arrest'
       call-script rules (`callrules.analyze_call(...)`)
    -> On-device Llama 3.2 1B STOP warning via ExecuTorch (`llm.Explainer`)
    -> Vetted 1930 helpline / Sanchar Saathi Chakshu / cybercrime.gov.in actions
    -> Optional offline read-aloud TTS (`--speak` on Linux, existing offline `TextToSpeech` on Android)

Feature-flag isolation:
  Core SMS/URL/flow/injection paths do not depend on Call Guard. In the local web UI
  (`app/server.py`), Call Guard is disabled by default unless `PRAHARI_CALL_GUARD=1` or
  `--call-guard` is enabled.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import resource
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import asr, callrules

CAND = Path(__file__).resolve().parents[1]
REPO = CAND.parents[1]
# Inside the candidate so its tests and --demo work in a staged copy (bin/eval copies only this dir).
DEMO_DIR = CAND / "demo" / "call_guard"

VERDICT = {1: "malicious", 0: "benign", "uncertain": "uncertain"}

DIGITAL_ARREST_ACTIONS = [
    "STOP and hang up immediately; real police, CBI, customs and RBI never conduct 'digital arrests' or keep you on video call.",
    "Never transfer money to any 'safe' or 'verification' account and never stay isolated — tell a family member right away.",
    "Report the caller on Sanchar Saathi Chakshu (sancharsaathi.gov.in), file a complaint at cybercrime.gov.in, or call 1930 immediately if money was lost.",
]

CALL_SCAM_ACTIONS = [
    "STOP and hang up now; never share OTP, UPI PIN, CVV or bank details on a phone call.",
    "Verify any claim yourself using the official app or the number printed on the back of your bank card.",
    "Report the scam call on Sanchar Saathi Chakshu (sancharsaathi.gov.in), or call 1930 immediately if money was lost.",
]

CALL_SUSPICIOUS_ACTIONS = [
    "Pause and hang up before acting; do not transfer money or share any code.",
    "Check the claim independently through the organisation's official app or helpline.",
    "Report suspicious calls on Sanchar Saathi Chakshu (sancharsaathi.gov.in), or call 1930 if money was lost.",
]

CALL_BENIGN_ACTIONS = [
    "No scam script was detected, but callers can still spoof banks or officials — never share an OTP or PIN on a call.",
    "If you ever lose money to a fraudulent call, dial 1930 right away.",
]

LIMITATION_NOTE = (
    "Call Guard checks shared voice notes/audio files or consented local speakerphone recordings. "
    "Android and Linux apps cannot tap live cellular/VoIP call audio directly."
)


def is_enabled(env: dict | None = None) -> bool:
    """Feature flag controlling Call Guard hooks in shared surfaces (web UI / app)."""
    src = os.environ if env is None else env
    val = str(src.get("PRAHARI_CALL_GUARD", "")).strip().lower()
    return val in ("1", "true", "yes", "on")


def classify_call(transcript: str) -> dict:
    """Run existing Prahari text detector + new digital-arrest call-script rules on a transcript."""
    from . import detect, llm

    text = callrules.normalize_transcript(transcript)
    call_a = callrules.analyze_call(text)

    if not text:
        return {
            "label": "uncertain",
            "verdict": "uncertain",
            "stop_warning": False,
            "score": 0.5,
            "category": "empty or unintelligible audio",
            "evidence": ["speech-to-text produced no transcript; replay or check carefully"],
            "call_signals": [],
            "is_digital_arrest": False,
            "actions": CALL_SUSPICIOUS_ACTIONS,
            "speech_script": build_speech_script("uncertain", False, [], CALL_SUSPICIOUS_ACTIONS),
        }

    det_lab, det_score, det_ev = detect.classify_any("sms", text)
    lab, score, evidence = fuse(text, call_a, det_lab, det_score, det_ev)

    category = call_a["scam_type"] or llm.scam_type("sms", text, lab)
    actions = actions_for_call(lab, call_a, text)
    stop_warning = lab == 1
    speech_script = build_speech_script(lab, call_a["is_digital_arrest"], evidence, actions)

    return {
        "label": lab,
        "verdict": VERDICT[lab],
        "stop_warning": stop_warning,
        "score": round(score, 4),
        "category": category,
        "evidence": evidence,
        "call_signals": call_a["signals"],
        "is_digital_arrest": call_a["is_digital_arrest"],
        "actions": actions,
        "speech_script": speech_script,
    }


def _protective_reminder(text: str, call_a: dict, det_lab) -> bool:
    """A genuine security reminder the detector over-flagged: protective framing, no call-script
    signal, and no harm beyond telling the listener to block their own card in the official app.
    A detector DANGEROUS verdict is overridden only in that self-block case; "no harm found" can
    only clear a SUSPICIOUS one."""
    from . import mech

    if not call_a.get("protective") or call_a.get("label") != 0:
        return False
    m = mech.analyze(text)
    if not m["protective"]:
        return False
    harms = {name for name, _ in m["harm"]}
    self_block = harms == {"block_threat"} and m["official_channel"] and m["self_check"]
    if det_lab == 1:
        return bool(self_block)
    return not harms or bool(self_block)


def _only_reported_harm(text: str, call_a: dict) -> bool:
    """True when setting aside narrative / reported-speech clauses removes the detector's DANGEROUS
    reading and no call-script signal remains."""
    from . import detect

    if call_a.get("label") == 1 or not call_a.get("set_aside"):
        return False
    active = call_a.get("active_text") or ""
    return not active.strip() or detect.classify_any("sms", active)[0] != 1


def fuse(text: str, call_a: dict, det_lab, det_score: float, det_ev) -> tuple:
    """Fuse the existing text detector with the call-script rules. Shared by desktop and Android.

    1. A decisive digital-arrest / voice-scam script wins -> DANGEROUS (1).
    2. A genuine protective security reminder stays BENIGN (0) unless the detector found a real harm.
    3. Otherwise combine both conservatively.
    """
    from . import llm

    call_lab = call_a["label"]
    if call_lab == 1:
        lab: int | str = 1
        score = max(float(det_score), float(call_a["score"]))
    elif det_lab in (1, "uncertain") and _protective_reminder(text, call_a, det_lab):
        lab = 0
        score = min(float(det_score), 0.25)
    elif det_lab == 1 and _only_reported_harm(text, call_a):
        # The detector's DANGEROUS reading came only from a question, reported speech or a story
        # about scams ("did the caller ask for your OTP?"): SUSPICIOUS, never cleared.
        lab = "uncertain"
        score = 0.6
    elif det_lab == 1:
        lab = 1
        score = float(det_score)
    elif call_lab == "uncertain" or det_lab == "uncertain":
        lab = "uncertain"
        score = max(float(det_score), float(call_a["score"]))
    else:
        lab = 0
        score = min(float(det_score), float(call_a["score"]))

    # Evidence: lead with call-script evidence on call threats; drop overruled risk lines on benign.
    if lab == 0:
        benign_ev = llm.benign_evidence("sms", text, det_ev, 0)
        evidence = list(dict.fromkeys(call_a["evidence"] + benign_ev))[:6]
        if not evidence:
            evidence = ["no digital-arrest or scam-call demand detected in the transcript"]
    else:
        # Only risk lines lead a warning: a "reads like a security reminder" line would become the
        # opening of a STOP explanation.
        risk_ev = [e for e in call_a["evidence"] if not e.startswith("reads like")]
        evidence = list(dict.fromkeys(risk_ev + list(det_ev or [])))[:6]
    return lab, score, evidence


def actions_for_call(lab: int | str, call_analysis: dict, transcript: str) -> list[str]:
    """Vetted India-specific remediation actions for Call Guard verdicts."""
    if lab == 1:
        if call_analysis.get("is_digital_arrest") or set(call_analysis.get("signals") or []) & {
            "fake_authority_call", "arrest_warrant", "contraband_parcel",
            "no_disconnect", "video_isolation", "safe_account_verify", "telecom_ivr_scam",
        }:
            return list(DIGITAL_ARREST_ACTIONS)
        return list(CALL_SCAM_ACTIONS)
    if lab == "uncertain":
        return list(CALL_SUSPICIOUS_ACTIONS)
    return list(CALL_BENIGN_ACTIONS)


def build_speech_script(lab: int | str, is_digital_arrest: bool, evidence: list[str], actions: list[str]) -> str:
    """Spoken TTS script: STOP verdict + top vetted action only. Never speaks untrusted caller audio."""
    if lab == 1:
        if is_digital_arrest:
            lead = "STOP. Warning: this sounds like a fake digital arrest scam call. Hang up immediately."
        else:
            lead = "STOP. Warning: this call shows strong scam signals. Hang up now."
        step = actions[-1] if actions else "Report on Sanchar Saathi Chakshu or call 1930 if money was lost."
        return f"{lead} {step}"
    if lab == "uncertain":
        return "Caution. This call has suspicious signs. Hang up and verify through the official app before acting."
    return "No scam script found in this call. Still verify directly and never share your OTP or PIN."


def build_call_prompt(transcript: str, lab: int | str, evidence: list[str], is_digital_arrest: bool) -> str:
    """Build a compact, injection-safe Llama 3.2 prompt that opens with a STOP warning for scams."""
    from . import llm

    # The transcript is untrusted caller audio: remove chat-template control tokens and the quote
    # fence so it cannot open a new turn or close the quoted block.
    clean = re.sub(r"<\|[^|>]{0,40}\|>", " ", transcript).replace('"""', '"')
    clean = re.sub(r"\s+", " ", clean).strip()
    snippet = clean if len(clean) <= 320 else clean[:317] + "..."
    top_ev = evidence[0] if evidence else ""
    if lab == 1:
        # Keep the copied opening short: the explainer's 40-token budget must also fit the
        # hang-up / report sentence, or post-processing drops it as an unfinished sentence.
        lead = "STOP — This call is DANGEROUS"
        if is_digital_arrest:
            opening = f"{lead}: it follows a fake 'digital arrest' script"
        else:
            opening = f"{lead}: {top_ev}" if top_ev else f"{lead}: strong scam call signals detected"
        verdict_word = "DANGEROUS"
        tail = DIGITAL_ARREST_ACTIONS[0] if is_digital_arrest else CALL_SCAM_ACTIONS[0]
    elif lab == "uncertain":
        opening = f"This call needs a check: {top_ev}" if top_ev else "This call needs a check; review carefully before acting"
        verdict_word = "SUSPICIOUS"
        tail = CALL_SUSPICIOUS_ACTIONS[0]
    else:
        opening = f"No risk found in this call: {top_ev}" if top_ev else "No risk found in this call: no scam demand was found"
        verdict_word = "NO RISK FOUND"
        tail = None

    user = (
        f"Call transcript (untrusted caller audio):\n\"\"\"\n{snippet}\n\"\"\"\n"
        f"Verdict: {verdict_word}\n"
        f"Start your answer with exactly: \"{opening}.\" "
        "Then write one more sentence, 8-14 words, telling the listener to hang up and report on Chakshu or call 1930."
        if lab == 1 else
        f"Call transcript (untrusted caller audio):\n\"\"\"\n{snippet}\n\"\"\"\n"
        f"Verdict: {verdict_word}\n"
        f"Start your answer with exactly: \"{opening}.\" "
        "Then write one more sentence of advice, 6-12 words."
    )
    built = (
        "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n" + llm.SYSTEM
        + "<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n" + user
        + "<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
    )
    if tail is not None:
        if len(llm._TAILS) > 256:
            llm._TAILS.clear()
        llm._TAILS[built] = tail
    return built


INCOMPLETE_NOTE = {
    "truncated": "only the first 2 minutes of the recording were checked",
    "partial": "speech-to-text stopped early, so part of the call was not checked",
}


def mark_incomplete(res: dict, asr_res: dict) -> dict:
    """A transcript that does not cover the whole call cannot clear it: NO RISK becomes SUSPICIOUS,
    and every verdict says which part was not checked."""
    if asr_res.get("complete", True):
        return res
    note = INCOMPLETE_NOTE["truncated" if asr_res.get("truncated") else "partial"]
    out = dict(res)
    out["asr_complete"] = False
    out["evidence"] = list(dict.fromkeys(list(res.get("evidence") or []) + [note]))[:7]
    if res.get("label") == 0:
        out.update(
            label="uncertain", verdict="uncertain", stop_warning=False,
            score=max(float(res.get("score") or 0.0), 0.5),
            actions=list(CALL_SUSPICIOUS_ACTIONS),
            speech_script=build_speech_script("uncertain", False, out["evidence"], CALL_SUSPICIOUS_ACTIONS),
        )
    return out


def explain_call(transcript: str, result: dict, explainer=None) -> dict:
    """Generate an on-device Llama 3.2 1B explanation via ExecuTorch for a Call Guard result."""
    from . import llm

    out = dict(result)
    try:
        ex = explainer if explainer is not None else llm.Explainer()
        prompt = build_call_prompt(
            transcript,
            result["label"],
            result["evidence"],
            bool(result.get("is_digital_arrest")),
        )
        text, stats = ex.generate(prompt)
        if not isinstance(text, str) or not text.strip():
            raise ValueError("empty explanation")
        out["explanation"] = text
        out["llm"] = stats
        out["explanation_status"] = "success"
    except Exception as exc:
        out["explanation_status"] = "failed"
        out["explanation_error"] = f"Explanation unavailable ({type(exc).__name__}). The detector result and safety steps above are complete."
    return out


def analyze_audio_file(
    audio_path: str | Path,
    *,
    language: str = "en",
    explain: bool = True,
    asr_engine=None,
    explainer=None,
    model_dir: str | Path | None = None,
) -> dict:
    """Full end-to-end Call Guard run on an audio file."""
    t0 = time.perf_counter()
    engine = asr_engine if asr_engine is not None else asr.WhisperExecuTorchASR(model_dir=model_dir)
    asr_res = engine.transcribe_file(audio_path, language=language)

    t_det = time.perf_counter()
    res = mark_incomplete(classify_call(asr_res["text"]), asr_res)
    det_ms = round((time.perf_counter() - t_det) * 1000, 2)

    if explain:
        res = explain_call(asr_res["text"], res, explainer=explainer)
    else:
        res["explanation_status"] = "skipped"

    total_ms = round((time.perf_counter() - t0) * 1000, 1)
    rss_mb = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 1)
    res.update({
        "audio_file": str(audio_path),
        "transcript": asr_res["text"],
        "asr": asr_res,
        "detector_ms": det_ms,
        "total_latency_ms": total_ms,
        "peak_rss_mb": rss_mb,
        "limitation": LIMITATION_NOTE,
    })
    return res


def speak_local(script: str) -> tuple[bool, str]:
    """Read the STOP warning aloud via an installed offline Linux TTS command, if available."""
    if not script.strip():
        return False, "empty speech script"
    for cmd in (["espeak-ng", script], ["espeak", script], ["spd-say", "--wait", script]):
        if shutil.which(cmd[0]):
            try:
                proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=30)
                if proc.returncode == 0:
                    return True, f"spoken via {cmd[0]}"
            except (OSError, subprocess.SubprocessError) as exc:
                return False, f"{cmd[0]} failed: {exc}"
    return False, "no offline Linux TTS engine found (install espeak-ng or use Android TextToSpeech)"


def record_mic_with_consent(seconds: float, out_wav: str | Path, *, consent: bool = False) -> Path:
    """Record mono 16 kHz PCM WAV from the local microphone only with explicit user consent."""
    if not consent:
        raise ValueError(
            "Explicit consent is required to record microphone audio (pass --consent). "
            "Call Guard never taps phone calls silently; place the call on speakerphone only with consent."
        )
    if not 1.0 <= seconds <= 120.0:
        raise ValueError("--record duration must be between 1 and 120 seconds")
    dst = Path(out_wav)
    dur = str(int(round(seconds)))
    if shutil.which("arecord"):
        cmd = ["arecord", "-q", "-f", "S16_LE", "-r", "16000", "-c", "1", "-d", dur, str(dst)]
    elif shutil.which("ffmpeg"):
        cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
               "-f", "alsa", "-i", "default", "-t", dur, "-ac", "1", "-ar", "16000", str(dst)]
    else:
        raise asr.AudioDecodeError("no local recorder found (install alsa-utils `arecord` or `ffmpeg`)")
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=int(seconds) + 15)
    if proc.returncode != 0 or not dst.is_file():
        err = proc.stderr.decode("utf-8", "replace").strip()[:200]
        raise asr.AudioDecodeError(f"microphone recording failed: {err or 'no audio captured'}")
    return dst


def demo_manifest(audio_dir: Path | None = None) -> list[dict]:
    """Return synthetic TTS call fixtures for `--demo`."""
    root = audio_dir or DEMO_DIR
    manifest_path = root / "manifest.json"
    if manifest_path.is_file():
        rows = json.loads(manifest_path.read_text(encoding="utf-8"))
        for row in rows:
            row["path"] = str(root / row["file"])
        return rows
    wavs = sorted(root.glob("*.wav"))
    return [{"id": p.stem, "file": p.name, "path": str(p), "expected": "any", "language": "en"} for p in wavs]


def run_demo(
    *,
    audio_dir: Path | None = None,
    language: str = "en",
    explain: bool = True,
    model_dir: str | Path | None = None,
    out_path: str | Path | None = None,
    speak: bool = False,
) -> tuple[list[dict], int]:
    """Run Call Guard across all synthetic TTS demo audio fixtures."""
    items = demo_manifest(audio_dir)
    if not items:
        raise asr.AudioDecodeError(f"no demo audio fixtures found in {audio_dir or DEMO_DIR}")

    engine = asr.WhisperExecuTorchASR(model_dir=model_dir)
    explainer = None
    if explain:
        from . import llm
        explainer = llm.Explainer()

    results = []
    failures = 0
    for item in items:
        lang = item.get("language", language) if language == "auto" else language
        res = analyze_audio_file(
            item["path"],
            language=lang,
            explain=explain,
            asr_engine=engine,
            explainer=explainer,
        )
        res["id"] = item["id"]
        res["expected"] = item.get("expected", "any")
        res["expected_match"] = (
            res["expected"] == "any" or res["verdict"] == res["expected"]
        )
        if not res["expected_match"] or (explain and res.get("explanation_status") != "success"):
            failures += 1
        if speak:
            ok, note = speak_local(res["speech_script"])
            res["tts"] = {"spoken": ok, "note": note}
        results.append(res)
        print(
            f"[{item['id']}] verdict={res['verdict']} (expected={res['expected']}) "
            f"score={res['score']} asr={res['asr']['total_ms']}ms "
            f"(rtfx={res['asr']['rtfx']}x) det={res['detector_ms']}ms "
            f"total={res['total_latency_ms']}ms rss={res['peak_rss_mb']}MB"
        )
        print(f"  transcript: {res['transcript']}")
        print(f"  evidence: {res['evidence']}")
        if res.get("explanation"):
            print(f"  llama STOP/advice: {res['explanation']}")
        elif res.get("explanation_error"):
            print(f"  explanation_error: {res['explanation_error']}")

    if out_path:
        Path(out_path).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"demo written to {out_path}")
    return results, (1 if failures else 0)


@contextlib.contextmanager
def _native_stdout_to_stderr():
    """Send fd 1 to stderr while models run: the ExecuTorch LLM runner prints tokens and stats to
    stdout, which would corrupt the JSON this CLI prints there."""
    def _flush_all():
        sys.stdout.flush()
        try:  # the runner's C stdio buffer, or it is written to the restored stdout at exit
            import ctypes
            ctypes.CDLL(None).fflush(None)
        except (OSError, AttributeError):
            pass

    _flush_all()
    saved = os.dup(1)
    try:
        os.dup2(2, 1)
        yield
    finally:
        _flush_all()
        os.dup2(saved, 1)
        os.close(saved)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="callguard",
        description=(
            "Prahari Call Guard (Preview): offline scam-call & WhatsApp voice-note triage on Arm "
            "using ExecuTorch Whisper Tiny INT8 + Indian digital-arrest rules + ExecuTorch Llama 3.2 1B."
        ),
    )
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--demo", action="store_true", help="run synthetic TTS English scam/legit demo calls")
    src.add_argument("--file", help="analyze a local WhatsApp voice note (.ogg/.opus/.m4a) or .wav audio file")
    src.add_argument("--transcript", help="classify a call transcript directly (skips ASR)")
    src.add_argument("--record", type=float, metavar="SECONDS", help="record local microphone audio with --consent")
    src.add_argument("--setup-model", action="store_true", help="download & SHA-256 verify Arm Whisper Tiny INT8 PTE")
    ap.add_argument("--consent", action="store_true", help="confirm explicit user consent for --record speakerphone capture")
    ap.add_argument("--lang", choices=("en", "hi", "auto"), default="en", help="Whisper transcription language (default: en)")
    ap.add_argument("--model-dir", default=None, help="directory containing Whisper .pte and tokenizer.json")
    ap.add_argument("--audio-dir", default=None, help="override demo audio fixture directory")
    ap.add_argument("--no-explain", action="store_true", help="skip Llama 3.2 1B explanation (ASR + detector only)")
    ap.add_argument("--speak", action="store_true", help="read STOP warning aloud via offline Linux TTS if installed")
    ap.add_argument("--out", default=None, help="write JSON output to path")
    a = ap.parse_args(argv)

    if str(os.environ.get("PRAHARI_CALL_GUARD", "")).strip().lower() in ("0", "false", "off", "no"):
        print("callguard: disabled by PRAHARI_CALL_GUARD=0", file=sys.stderr)
        return 2

    try:
        if a.setup_model:
            info = asr.download_model(a.model_dir)
            print(json.dumps(info, indent=2))
            return 0

        explain = not a.no_explain

        if a.demo:
            _, code = run_demo(
                audio_dir=Path(a.audio_dir) if a.audio_dir else None,
                language=a.lang,
                explain=explain,
                model_dir=a.model_dir,
                out_path=a.out,
                speak=a.speak,
            )
            return code

        if a.transcript is not None:
            with _native_stdout_to_stderr():
                t0 = time.perf_counter()
                res = classify_call(a.transcript)
                res["detector_ms"] = round((time.perf_counter() - t0) * 1000, 2)
                res["transcript"] = callrules.normalize_transcript(a.transcript)
                res["limitation"] = LIMITATION_NOTE
                if explain:
                    res = explain_call(res["transcript"], res)
                else:
                    res["explanation_status"] = "skipped"
                if a.speak:
                    ok, note = speak_local(res["speech_script"])
                    res["tts"] = {"spoken": ok, "note": note}
            payload = json.dumps(res, ensure_ascii=False, indent=2)
            if a.out:
                Path(a.out).write_text(payload, encoding="utf-8")
            print(payload)
            return 0

        with _native_stdout_to_stderr():
            if a.record is not None:
                with tempfile.TemporaryDirectory(prefix="prahari-callguard-") as tmp:
                    wav_path = record_mic_with_consent(a.record, Path(tmp) / "speakerphone.wav", consent=a.consent)
                    res = analyze_audio_file(wav_path, language=a.lang, explain=explain, model_dir=a.model_dir)
                    res["audio_file"] = "<consented-mic-recording>"
            else:
                res = analyze_audio_file(a.file, language=a.lang, explain=explain, model_dir=a.model_dir)

            if a.speak:
                ok, note = speak_local(res["speech_script"])
                res["tts"] = {"spoken": ok, "note": note}
        payload = json.dumps(res, ensure_ascii=False, indent=2)
        if a.out:
            Path(a.out).write_text(payload, encoding="utf-8")
        print(payload)
        return 0
    except (asr.AsrError, ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"callguard: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
