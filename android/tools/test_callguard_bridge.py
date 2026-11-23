"""Call Guard (preview) Android bridge test: callguard_mobile runs with NumPy only, as on the phone."""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'candidates/BEST'), str(ROOT / 'android/python')]
# Chaquopy installs only NumPy: block the desktop-only packages so an import of any of them fails.
for blocked in ('joblib', 'sklearn', 'scipy', 'pandas', 'torch', 'executorch', 'tokenizers'):
    sys.modules[blocked] = None
import mobile
mobile.portable.ROOT = ROOT / 'android/build/generated/python/models'  # exported by CI first
import callguard_mobile as cg

scam = json.loads(cg.verdict_call(
    'This is Inspector Sharma from Mumbai Cyber Crime and CBI. An arrest warrant is issued in your name. '
    'Do not disconnect this call, stay on video call alone and transfer 50,000 rupees to the RBI safe account.'))
assert scam['stop_warning'] is True and scam['level'] == 'danger', scam
assert scam['is_digital_arrest'] is True
assert any('1930' in a for a in scam['actions']) and all(scam['actions_hi'])
assert scam['speech_script'].startswith('STOP')

legit = json.loads(cg.verdict_call(
    'Hello, this is a routine security reminder from State Bank of India. Never share your OTP, UPI PIN, or '
    'password on any phone call. If you did not authorize a card transaction, block your card directly inside '
    'the official YONO app or visit your home branch.'))
assert legit['stop_warning'] is False and legit['level'] == 'clear', legit

cut = json.loads(cg.verdict_call(
    'Hi, this is Priya from City Dental Clinic confirming your appointment tomorrow.', truncated=True))
assert cut['level'] == 'warn' and any('first 2 minutes' in e for e in cut['evidence']), cut

empty = json.loads(cg.verdict_call('   '))
assert empty['level'] == 'warn' and empty['stop_warning'] is False

# Mel features: 1 second of 8 kHz PCM -> Whisper (1, 80, 3000) float32 bytes.
mel = cg.mel_spectrogram_flat(bytes(16000), 8000)
assert len(mel) == 80 * 3000 * 4

# Pure-Python token decoding (no `tokenizers` wheel on the phone).
with tempfile.TemporaryDirectory() as tmp:
    tok = Path(tmp) / 'tokenizer.json'
    tok.write_text(json.dumps({
        'model': {'vocab': {'Hello': 0, 'Ġworld': 1}},
        'added_tokens': [{'id': 50257, 'content': '<|endoftext|>', 'special': True}],
    }), encoding='utf-8')
    assert cg.decode_whisper_tokens(str(tok), '[0, 1, 50257]') == 'Hello world'
print('call guard bridge passed')
