"""Android Chaquopy adapter for Call Guard (Preview).

Runs with NumPy only (no torch, executorch, or tokenizers wheels). Uses:
  - `triage.asr` pure-NumPy mel spectrogram + pure-Python Whisper BPE token decoder
  - `triage.callrules` Indian 'digital arrest' call-script rules
  - `mobile.detect` + `mobile.llm` (the existing exported portable detectors and Llama bridge)
"""
import json
import time
from pathlib import Path

import numpy as np

import mobile
from triage import asr, callguard, callrules, llm

_CALL_HI_STEPS = {
    callguard.DIGITAL_ARREST_ACTIONS[0]:
        "रुकें और तुरंत फ़ोन काटें; असली पुलिस, CBI, कस्टम या RBI कभी 'डिजिटल अरेस्ट' या वीडियो कॉल पर पूछताछ नहीं करते।",
    callguard.DIGITAL_ARREST_ACTIONS[1]:
        "किसी भी 'सेफ़' या 'वेरिफिकेशन' खाते में पैसे कभी न भेजें और अकेले न रहें — तुरंत परिवार को बताएं।",
    callguard.DIGITAL_ARREST_ACTIONS[2]:
        "कॉल करने वाले नंबर की रिपोर्ट Sanchar Saathi Chakshu (sancharsaathi.gov.in) पर करें, cybercrime.gov.in पर शिकायत दर्ज करें, या पैसे जाने पर तुरंत 1930 पर कॉल करें।",
    callguard.CALL_SCAM_ACTIONS[0]:
        "रुकें और अभी फ़ोन काटें; कॉल पर OTP, UPI PIN, CVV या बैंक जानकारी कभी न बताएं।",
    callguard.CALL_SCAM_ACTIONS[1]:
        "किसी भी दावे की जांच खुद आधिकारिक ऐप या बैंक कार्ड के पीछे लिखे नंबर से करें।",
    callguard.CALL_SCAM_ACTIONS[2]:
        "ठगी कॉल की रिपोर्ट Sanchar Saathi Chakshu (sancharsaathi.gov.in) पर करें, या पैसे चले गए हों तो तुरंत 1930 पर कॉल करें।",
    callguard.CALL_SUSPICIOUS_ACTIONS[0]:
        "रुकें और कोई कदम उठाने से पहले फ़ोन काटें; पैसे न भेजें और कोई कोड न बताएं।",
    callguard.CALL_SUSPICIOUS_ACTIONS[1]:
        "इस दावे की जांच संस्था के आधिकारिक ऐप या हेल्पलाइन से अलग से करें।",
    callguard.CALL_SUSPICIOUS_ACTIONS[2]:
        "संदिग्ध कॉल की रिपोर्ट Sanchar Saathi Chakshu (sancharsaathi.gov.in) पर करें, या पैसे जाने पर 1930 पर कॉल करें।",
    callguard.CALL_BENIGN_ACTIONS[0]:
        "कोई ठगी स्क्रिप्ट नहीं मिली, लेकिन कॉलर बैंक या अधिकारी की नकल कर सकते हैं — कॉल पर OTP या PIN कभी न बताएं।",
    callguard.CALL_BENIGN_ACTIONS[1]:
        "अगर कभी किसी फ़्रॉड कॉल में पैसे चले जाएं, तो तुरंत 1930 डायल करें।",
}

_tok_cache = {}
_last_call = {}


def mel_spectrogram_flat(pcm16_bytes, sample_rate):
    """Convert mono signed 16-bit PCM bytes to Whisper (1, 80, 3000) float32 little-endian bytes."""
    raw = bytes(pcm16_bytes)
    if not raw:
        return np.zeros((1, asr.N_MELS, asr.N_FRAMES), dtype='<f4').tobytes()
    usable = (len(raw) // 2) * 2
    wav = np.frombuffer(raw[:usable], dtype='<i2').astype(np.float32) / 32768.0
    wav16 = asr.resample_to_16k(wav, int(sample_rate))
    mel = asr.log_mel_spectrogram(wav16)
    return np.ascontiguousarray(mel, dtype='<f4').tobytes()


def decode_whisper_tokens(tokenizer_path, token_ids_json):
    """Decode Whisper token IDs using PureWhisperTokenizer (zero external dependencies)."""
    key = str(Path(tokenizer_path))
    tok = _tok_cache.get(key)
    if tok is None:
        tok = asr.PureWhisperTokenizer(key)
        _tok_cache[key] = tok
    ids = json.loads(token_ids_json) if isinstance(token_ids_json, str) else list(token_ids_json)
    return tok.decode([int(i) for i in ids], skip_special_tokens=True)


def _call_actions_hi(actions):
    base = mobile._HINDI.get('steps') or {}
    return [_CALL_HI_STEPS.get(step) or base.get(step, '') for step in (actions or [])]


def verdict_call(transcript, truncated=False):
    """Stage 1 for Call Guard: existing detector + Indian digital-arrest rules (no Llama).

    `truncated`: the audio was cut before transcription; a cut call is never cleared."""
    t0 = time.perf_counter()
    text = callrules.normalize_transcript(transcript)
    call_a = callrules.analyze_call(text)

    if not text:
        lab = 'uncertain'
        score = 0.5
        ev = ['speech-to-text produced no transcript; replay or check carefully']
        scam = 'empty or unintelligible audio'
        actions = list(callguard.CALL_SUSPICIOUS_ACTIONS)
        is_da = False
    else:
        det_lab, det_score, det_ev = mobile.detect.classify_any('sms', text)
        lab, score, ev = callguard.fuse(text, call_a, det_lab, det_score, det_ev)

        scam = call_a['scam_type'] or llm.scam_type('sms', text, lab)
        actions = callguard.actions_for_call(lab, call_a, text)
        is_da = bool(call_a['is_digital_arrest'])

    if truncated:
        marked = callguard.mark_incomplete({'label': lab, 'evidence': ev, 'score': score},
                                           {'complete': False, 'truncated': True})
        if marked['label'] != lab:
            actions = list(callguard.CALL_SUSPICIOUS_ACTIONS)
        lab, ev, score = marked['label'], marked['evidence'], marked['score']

    ms = (time.perf_counter() - t0) * 1000.0
    speech_script = callguard.build_speech_script(lab, is_da, ev, actions)
    _last_call.clear()
    _last_call.update(text=text, lab=lab, ev=ev, is_da=is_da)

    out = {
        'verdict': 'STOP — DANGEROUS CALL' if lab == 1 else mobile.VERDICT[lab],
        'level': {1: 'danger', 'uncertain': 'warn', 0: 'clear'}[lab],
        'score': round(float(score), 4),
        'scam_type': scam,
        'evidence': ev,
        'evidence_quotes': [mobile.quote_span(line, text) for line in ev],
        'actions': actions,
        'actions_hi': _call_actions_hi(actions),
        'buttons': mobile._HINDI['buttons'],
        'detector_ms': ms,
        'stop_warning': lab == 1,
        'is_digital_arrest': is_da,
        'speech_script': speech_script,
        'transcript': text,
    }
    report = mobile._report_buttons('sms', lab, scam, actions)
    if report:
        out['report_buttons'] = report
    return json.dumps(out, ensure_ascii=False)


def explain_call(runner):
    """Stage 2 for Call Guard: on-device Llama 3.2 1B STOP warning through ExecuTorch."""
    ex = mobile.BridgeExplainer(runner)
    prompt = callguard.build_call_prompt(
        _last_call.get('text', ''),
        _last_call.get('lab', 'uncertain'),
        _last_call.get('ev', []),
        bool(_last_call.get('is_da', False)),
    )
    text, stats = ex.generate(prompt)
    # The Call Guard tails are its own vetted sentences, not the SMS pool.
    call_tails = (callguard.DIGITAL_ARREST_ACTIONS[0], callguard.CALL_SCAM_ACTIONS[0],
                  callguard.CALL_SUSPICIOUS_ACTIONS[0])
    body = (text or '').strip()
    replaced = any(body.endswith(t) for t in call_tails) or mobile.ends_with_replacement(
        text, 'sms', _last_call.get('lab', 'uncertain'), _last_call.get('text', '')
    )
    return json.dumps({'explanation': text, 'llm': stats, 'replaced': replaced}, ensure_ascii=False)
