import json
import re
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'candidates/BEST'), str(ROOT/'android/python')]
# Chaquopy installs only NumPy: block the desktop-only packages so an import of
# any of them fails here as it would on the phone.
import intake
assert intake.detect_mode('http://amaz0n-refund-help.top/claim') == 1
assert intake.detect_mode('  https://www.irctc.co.in/nget/train-search  ') == 1
assert intake.detect_mode('upi://pay?pa=refund@ybl&am=5000') == 1
assert intake.detect_mode('upi://collect?pa=9876543210@ibl&am=5000') == 1
assert intake.detect_mode('upi://mandate?pa=verify@okaxis&am=15000&recur=MONTHLY') == 1
assert intake.detect_mode('phonepe://pay?pa=q123456@ybl&pn=Shop&mc=5411') == 1
assert intake.detect_mode('pa=sharma@okicici&pn=Sharma&mc=5411&cu=INR') == 1
assert intake.detect_mode('www.example.com/path') == 1
assert intake.detect_mode('Dear customer your SBI KYC is expiring, update at http://sbi-kyc.in-verify.top or the account will be blocked') == 0
assert intake.detect_mode('Aapka bijli connection aaj raat 9:30 kat jayega. Turant 98XXXXXX12 par call karein ya http://uppcl-bill-pay.top kholein.') == 0
assert intake.detect_mode('see https://example.com please') == 0
assert intake.detect_mode('tcp connections to 200 different ports on 10.0.0.5 within 10 seconds, all rejected') == 2
assert intake.detect_mode('{"num_failed_logins": 4, "serror_rate": 1}') == 2
assert intake.detect_mode('') == 0
assert intake.detect_mode('{not json}') == 0
assert intake.clean_share('hi\x00there\x7f') == 'hithere'
assert intake.clean_share('a\r\nb\tc') == 'a\nb\tc'
assert intake.clean_share('  \x1bkeep  ') == 'keep'
assert '\n' in intake.clean_share('line\nnext')
print('share-text mode detection passed')

hi = json.loads((ROOT / 'android/python/strings_hi.json').read_text(encoding='utf-8'))
assert set(hi) >= {'ui', 'evidence', 'skip', 'new', 'templates'}
assert isinstance(hi['ui'], dict) and hi['ui']['Check on this phone']
assert isinstance(hi['evidence'], dict) and any('{host}' in k for k in hi['evidence'])
assert isinstance(hi['templates'], list) and hi['templates']
assert isinstance(hi['skip'], list) and hi['skip']
for key, item in hi['new'].items():
    assert 'en' in item and 'hi' in item and item['hi'].strip(), key
print('hindi string table shape passed')

def _calls(name, src):
    """Argument text of each call to name(, ignoring longer identifiers."""
    out = []
    token = name + '('
    i = 0
    while True:
        j = src.find(token, i)
        if j < 0:
            break
        if j > 0 and (src[j - 1].isalnum() or src[j - 1] == '_'):
            i = j + len(token)
            continue
        k = j + len(token)
        depth = 1
        buf = []
        while k < len(src) and depth:
            c = src[k]
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    break
            if depth:
                buf.append(c)
            k += 1
        out.append(''.join(buf))
        i = k + 1
    return out

def _lits(blob):
    return re.findall(r'"((?:\\.|[^"\\])*)"', blob)

def _split_args(blob):
    """Top-level arguments of a call, respecting strings and nested brackets."""
    out, buf, depth, quote, esc = [], [], 0, False, False
    for ch in blob:
        if quote:
            buf.append(ch)
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                quote = False
            continue
        if ch == '"':
            quote = True
        elif ch in '([{':
            depth += 1
        elif ch in ')]}':
            depth -= 1
        elif ch == ',' and depth == 0:
            out.append(''.join(buf)); buf = []
            continue
        buf.append(ch)
    out.append(''.join(buf))
    return out

def _arg_lit(blob, nth):
    """The string literal that is argument nth itself, or None."""
    args = _split_args(blob)
    if nth >= len(args):
        return None
    m = re.fullmatch(r'\s*"((?:\\.|[^"\\])*)"\s*', args[nth])
    return m.group(1) if m else None

assert _arg_lit('this, "Offline", 12', 1) == 'Offline'
assert _arg_lit('"Check", f(a, "x")', 0) == 'Check'
assert _arg_lit('f(a, "x"), "Label"', 1) == 'Label'

_SLOT = {
    'n': r'(\d+)', 'count': r'(\d+)', 'tld': r'([A-Za-z0-9]+)',
    'host': r"([^\s']+)", 'reg': r"([^\s']+)", 'ip': r"([^\s']+)",
    'brand': r"([^']+)", 'b': r"([^']+)", 'what': r'(link|text|message)',
}

def _compile_slots(english):
    names = []
    pat = ['^']
    i = 0
    while i < len(english):
        if english[i] == '{':
            end = english.find('}', i + 1)
            if end < 0:
                return None
            name = english[i + 1:end]
            names.append(name)
            pat.append(_SLOT.get(name, r'(.+?)'))
            i = end + 1
        else:
            pat.append(re.escape(english[i]))
            i += 1
    pat.append('$')
    return re.compile(''.join(pat)), names

_TEMPLATES = []
for item in hi['templates']:
    compiled = _compile_slots(item['en'])
    assert compiled, item
    _TEMPLATES.append((compiled[0], compiled[1], item['hi'], len(item['en'])))
for english, hindi_line in hi['evidence'].items():
    if '{' not in english:
        continue
    compiled = _compile_slots(english)
    if compiled:
        _TEMPLATES.append((compiled[0], compiled[1], hindi_line, len(english)))
_TEMPLATES.sort(key=lambda row: -row[3])

def hindi_line(english):
    """Same order as L10n.t: exact ui, exact evidence, then templates."""
    if english in hi['skip']:
        return english
    if english in hi['ui']:
        return hi['ui'][english]
    if english in hi['evidence']:
        return hi['evidence'][english]
    for regex, names, hindi_text, _length in _TEMPLATES:
        match = regex.match(english)
        if not match:
            continue
        out = hindi_text
        for index, name in enumerate(names):
            out = out.replace('{' + name + '}', match.group(index + 1))
        return out
    return None

_kt = (ROOT / 'android/app/src/main/java/in/prahari/app/MainActivity.kt').read_text(encoding='utf-8')
_used = set()
for _fn, _nth in (
    ('txt', 0), ('toast', 0), ('button', 0), ('heading', 0), ('bar', 0), ('root', 0),
    ('iconButton', 1), ('iconText', 1), ('asButton', 1), ('a11yText', 1), ('bottom', 1),
):
    for _args in _calls(_fn, _kt):
        _lit = _arg_lit(_args, _nth)
        if _lit is not None:
            _used.add(_lit)
for _args in _calls('t', _kt):
    _found = _lits(_args)
    if _found:
        _used.add(_found[0])
_new_keys = set()
for _args in _calls('n', _kt):
    _found = _lits(_args)
    if _found:
        _new_keys.add(_found[0])

_KEEP = {'Prahari', 'EN', 'Llama 3.2', 'OK'}
_missing = []
for _key in sorted(_used):
    if not _key or _key in hi['skip'] or _key in _KEEP or _key in hi['new']:
        continue
    if '$' in _key or '\\' in _key:
        continue
    if not re.search(r'[A-Za-z]', _key):
        continue
    if hindi_line(_key) in (None, '', _key):
        _missing.append(_key)
for _key in sorted(_new_keys):
    _item = hi['new'].get(_key)
    if not _item or not str(_item.get('hi', '')).strip():
        _missing.append('new:' + _key)
assert not _missing, 'Hindi missing for app strings:\n' + '\n'.join(_missing)

_samples = [
    "the domain amaz0n-refund-help.top imitates 'amazon' on .top",
    "the domain pay.sbi-secure.top imitates 'sbi' and uses .top, a throwaway registry",
    "the domain amaz0n-refund-help.top swaps letters for digits to imitate a brand",
    "the domain amaz0n-refund-help.top is unusually long or hyphenated",
    "the domain bit.ly is a URL shortener that hides its destination",
    "12 failed logins",
    "3 failed login attempts on the connection",
    "traffic to 200 different ports on 10.0.0.5",
    "traffic to 200 different ports",
    "official domain www.irctc.co.in",
    "lookalike domain sbi-kyc.top",
    "risky .top lookalike domain sbi-kyc.top",
    "URL shortener bit.ly",
]
for _sample in _samples:
    _got = hindi_line(_sample)
    assert _got and _got != _sample, _sample
    assert 'The domain' not in _got and 'this phone' not in _got.lower()
    # The host or count from the English line is kept, not translated away.
    _token = re.search(r"[\w.-]*\d[\w.-]*|[a-z0-9.-]+\.[a-z]{2,}", _sample)
    if _token and _token.group(0) not in ('12',):
        assert _token.group(0) in _got, (_sample, _got)
print('every app string has Hindi, including evidence templates')

def device_words(text):
    """Mirror of MainActivity.onDevice for an x86/x86_64 ABI. arm64 does not call this."""
    return (text
            .replace("this phone's", "this emulator's")
            .replace('this phone', 'this emulator')
            .replace('इसी फ़ोन', 'इसी एम्युलेटर')
            .replace('इस फ़ोन', 'इस एम्युलेटर'))

_phone_bits = ('this phone', 'इस फ़ोन', 'इसी फ़ोन')
_hi_values = list(hi['ui'].values()) + list(hi['evidence'].values())
_hi_values += [item['hi'] for item in hi['new'].values()]
_hi_values += [item['hi'] for item in hi['templates']]
for _value in _hi_values:
    if any(bit in _value for bit in ('इस फ़ोन', 'इसी फ़ोन')):
        _shown = device_words(_value)
        assert 'इस फ़ोन' not in _shown and 'इसी फ़ोन' not in _shown, _value
for _key in list(hi['ui']) + [item['en'] for item in hi['new'].values()]:
    if 'this phone' in _key:
        assert 'this phone' not in device_words(_key), _key
print('emulator wording drops this phone and इस फ़ोन')

import qrdec
_HI = """
111111100101001111111
100000100001001000001
101110101110101011101
101110101100001011101
101110100110001011101
100000100001101000001
111111101010101111111
000000000111100000000
000110110010100001100
001000011010010010110
101001101000001011110
101011001000000001100
001111110011000001111
000000001101000101000
111111101010011110010
100000100000110111011
101110101011011101101
101110101011110011100
101110100011011000111
100000100101100010110
111111100001001001110
""".split()
assert qrdec.decode_modules([[c == '1' for c in row] for row in _HI]) == 'HI'
_n = len(_HI)
_scale, _quiet = 4, 4
_side = (_n + _quiet * 2) * _scale
_gray = [255] * (_side * _side)
for _r, _row in enumerate(_HI):
    for _c, _bit in enumerate(_row):
        if _bit != '1':
            continue
        for _dy in range(_scale):
            for _dx in range(_scale):
                _y = (_r + _quiet) * _scale + _dy
                _x = (_c + _quiet) * _scale + _dx
                _gray[_y * _side + _x] = 0
assert qrdec.decode_gray(bytes(_gray), _side, _side) == 'HI'
assert qrdec.decode_modules([[False] * 21 for _ in range(21)]) is None
print('qr decoder fixture passed')

for blocked in ('joblib', 'sklearn', 'scipy', 'pandas', 'torch', 'executorch'):
    sys.modules[blocked] = None
import mobile
mobile.portable.ROOT = ROOT / 'android/build/generated/python/models'  # exported by CI first
class Fake:
    def __init__(self, replies): self.replies = iter(replies); self.prompts=[]
    def generate(self, prompt):
        self.prompts.append(prompt)
        return json.dumps({'text':next(self.replies),'stats':{'first_token_ms': 9}})
runner = Fake(["I'm sorry, I cannot help.", 'This message is DANGEROUS. It asks for an OTP.'])
e = mobile.BridgeExplainer(runner)
p = e.prompt('sms', 'Share your OTP at https://example.com', 1, ['asks for an OTP'])
text, stats = e.generate(p)
assert len(runner.prompts) == 2 and stats['retried'] and 'OTP' in text
assert 'https://example[.]com' in p and 'Verdict: DANGEROUS' in p
runner = Fake(["I cannot help.", "I cannot help.", "This message is DANGEROUS. It asks for an OTP."])
e = mobile.BridgeExplainer(runner)
text, stats = e.generate(p)
assert len(runner.prompts) == 3 and stats['evidence_only'] and 'Share your OTP' not in runner.prompts[-1]
print('fake bridge: prompt, retry and evidence-only fallback passed')

android_fake = Fake(['This is a test.'])
_, stats = mobile.BridgeExplainer(android_fake)._run('prompt')
assert stats['first_token_ms'] == 9
print('Android bridge TTFT field is the callback duration')

# Hindi lines are a parallel list. A missing English step stays blank, not a guess.
hi = mobile._actions_hi([
    'Do not click the link or reply to the message.',
    'This step is not in the table.',
])
assert hi == ['लिंक पर क्लिक न करें और मैसेज का जवाब न दें।', '']
assert mobile._actions_hi([mobile.llm.DEBIT_STEP])[0].startswith('पेमेंट आपका नहीं')

# Link evidence: brand imitation or a digit swap leads; everything else keeps detector order.
link_ev = [
    'the domain ends in .top, common for throwaway scam sites',
    'the domain amaz0n-refund-help.top is unusually long or hyphenated',
    'the domain amaz0n-refund-help.top swaps letters for digits to imitate a brand',
    'the link does not use HTTPS',
]
led = mobile._promote_link_signals(link_ev)
assert led[0] == link_ev[2] and led[1:] == [link_ev[0], link_ev[1], link_ev[3]]
brand = [
    'the link does not use HTTPS',
    "the domain pay.sbi-secure.top uses the name 'sbi' but is not that company's official site",
]
assert mobile._promote_link_signals(brand)[0] == brand[1]
assert mobile._promote_link_signals(['no HTTPS']) == ['no HTTPS']

# NO RISK evidence is the benign reading, never the overruled threat phrase.
from triage import mech
bank = ('SBI: Rs 2,450 debited via UPI. OTP 482910 kisi se share mat karein. '
        'If not you, block card in YONO app.')
raw = mech.evidence(mech.analyze(bank))
cleared = mobile.llm.benign_evidence('sms', bank, raw, 0)
assert cleared and not any('threaten' in line or 'block the account' in line for line in cleared)
assert mobile.llm.benign_evidence('sms', bank, ['threatens to block'], 1) == ['threatens to block']

# Report buttons follow the Hindi table's rules. Suspicious and network events have no pair.
chakshu = mobile._report_buttons('sms', 1, 'a fake KYC or account check', ['Do not open the link.'])
assert chakshu['primary']['id'] == 'report_chakshu' and chakshu['secondary']['id'] == 'lost_money_1930'
assert chakshu['primary']['en'] == 'Report on Sanchar Saathi Chakshu'
look = mobile._report_buttons('url', 1, 'a phishing link on a lookalike domain', ['Do not open the link.'])
assert look['primary']['id'] == 'report_chakshu' and look['secondary']['id'] == 'lost_money_1930'
debit = mobile._report_buttons('sms', 0, '', [mobile.llm.DEBIT_STEP])
assert debit['primary']['id'] == 'lost_money_1930' and debit['secondary']['id'] == 'report_cybercrime'
assert debit['primary']['hi'] == 'पैसे चले गए? 1930 पर कॉल करें'
sex = mobile._report_buttons('sms', 1, 'sextortion or blackmail', ['Do not pay; paying leads to more demands.'])
ext = mobile._report_buttons('sms', 1, 'an extortion threat', ['Do not pay; paying leads to more demands.'])
assert sex['primary']['id'] == ext['primary']['id'] == 'report_cybercrime'
assert sex['secondary']['id'] == 'lost_money_1930'
assert mobile._report_buttons('sms', 'uncertain', 'OTP or PIN theft', [mobile.llm.DEBIT_STEP]) is None
assert mobile._report_buttons('flow', 1, 'a port scan', ['Block the source address at the firewall or router.']) is None
assert mobile._report_buttons('sms', 0, '', ['Verify in the official app; never share your OTP or PIN.']) is None
print('hindi steps, link order, benign evidence and report buttons passed')

kyc = ('Dear customer your SBI KYC is expiring, update at http://sbi-kyc.in-verify.top '
       'or the account will be blocked')
tail = mobile.llm.advice_for('sms', 1, kyc)[0]
assert tail and mobile.ends_with_replacement('This message is DANGEROUS. ' + tail, 'sms', 1, kyc)
assert mobile.ends_with_replacement(
    'This message is DANGEROUS. Do not click the link or reply to the message.',
    'sms', 1, kyc)
assert not mobile.ends_with_replacement(
    'This message is DANGEROUS. It asks for an OTP and a password.',
    'sms', 1, kyc)
assert not mobile.ends_with_replacement('', 'sms', 1, kyc)
print('replacement-sentence flag passed')

kyc_q = mobile.quote_span('threatens to block the account or service', kyc)
assert 'account will be blocked' in kyc_q and 'http' not in kyc_q
link = 'http://amaz0n-refund-help.top/claim?id=8812'
link_q = mobile.quote_span('the domain amaz0n-refund-help.top swaps letters for digits to imitate a brand', link)
assert 'amaz0n' in link_q and 'http://' not in link_q and '[.]' in link_q and '8812' not in link_q
debit_q = mobile.quote_span('looks like a bank debit or OTP alert; scammers copy these', bank)
assert '482910' not in debit_q and '•' in debit_q
assert mobile.quote_span('reads like a routine bill reminder', 'hello there friend') == ''
assert mobile.quote_span('points to the official app or channel',
    'Your electricity bill of Rs 1,240 is due on 15 Dec. Pay through the mahadiscom app; no link is attached.') == ''
print('evidence quote spans passed')

# End to end through the shipped detector, with only NumPy available.
class Echo:
    def generate(self, prompt):
        word = prompt.rsplit('Verdict: ', 1)[-1].split('\n')[0]
        reply = {'DANGEROUS': 'This item is DANGEROUS. It points to an unofficial site.', 'NO RISK FOUND': 'No risk found for this item.'}
        return json.dumps({'text': reply.get(word, 'This item is SUSPICIOUS.'), 'stats': {}})
for kind, text in [('sms', 'Dear customer your SBI KYC is expiring, update at http://sbi-kyc.in-verify.top or the account will be blocked'),
                   ('url', 'http://sbi-kyc.in-verify.top/login'),
                   ('url', 'upi://pay?pa=cashback.refund99@ybl&pn=Amazon%20Refund%20Desk&am=4999&cu=INR&tn=Scan%20and%20enter%20UPI%20PIN%20to%20receive%20refund'),
                   ('url', 'upi://pay?pa=sharma.kirana@okicici&pn=Sharma%20Kirana%20Store&mc=5411&cu=INR&tn=Grocery%20bill'),
                   ('flow', 'many connections to different ports from one host in a few seconds')]:
    out = json.loads(mobile.check(kind, text, Echo()))
    assert out['verdict'] in ('DANGEROUS', 'SUSPICIOUS', 'NO RISK FOUND — still verify'), out
    # The Hindi summary is built from the detector result with only NumPy and package data.
    assert out.get('summary_hi') and any('\u0900' <= c <= '\u097F' for c in out['summary_hi']), out
    assert out.get('summary_hi_label'), out
    print(kind, out['verdict'], out['evidence'][:2])

# UPI QR verdicts, parsed summary, quotes, Hindi actions and report buttons with only NumPy installed.
upi_scam = json.loads(mobile.check(
    'url',
    'upi://pay?pa=cashback.refund99@ybl&pn=Amazon%20Refund%20Desk&am=4999&cu=INR&tn=Scan%20and%20enter%20UPI%20PIN%20to%20receive%20refund',
    Echo(),
))
assert upi_scam['verdict'] == 'DANGEROUS' and upi_scam['level'] == 'danger'
assert upi_scam['upi']['payee_vpa'] == 'cashback.refund99@ybl'
assert upi_scam['upi']['direction'] == 'sends_money'
assert upi_scam['report_buttons']['primary']['id'] == 'report_chakshu'
assert all(upi_scam['actions_hi']), upi_scam['actions_hi']
assert any(upi_scam['evidence_quotes']), upi_scam['evidence_quotes']

upi_merch = json.loads(mobile.check(
    'url',
    'upi://pay?pa=sharma.kirana@okicici&pn=Sharma%20Kirana%20Store&mc=5411&cu=INR&tn=Grocery%20bill',
    Echo(),
))
assert upi_merch['verdict'] == 'NO RISK FOUND — still verify' and upi_merch['level'] == 'clear'
assert upi_merch['upi']['is_merchant'] is True and upi_merch['upi']['merchant_code'] == '5411'
assert all(upi_merch['actions_hi']), upi_merch['actions_hi']

upi_p2p = json.loads(mobile.check(
    'url',
    'upi://pay?pa=priya.verma@okhdfcbank&pn=Priya%20Verma&am=450&cu=INR&tn=Dinner%20split',
    Echo(),
))
assert upi_p2p['verdict'] == 'NO RISK FOUND — still verify' and upi_p2p['upi']['is_merchant'] is False

upi_unknown = json.loads(mobile.check(
    'url',
    'upi://pay?pa=shop1@quickpayxyz&pn=Local%20Shop&am=500&cu=INR',
    Echo(),
))
assert upi_unknown['verdict'] == 'SUSPICIOUS' and upi_unknown['level'] == 'warn'
assert all(upi_unknown['actions_hi']), upi_unknown['actions_hi']
print('mobile.check runs with only NumPy installed (including UPI QR payloads)')

# Report card: present for SCAM and SUSPICIOUS, absent for NO RISK, network and a plain debit alert;
# a failure building it never fails the verdict.
kyc_text = 'Dear customer your SBI KYC is expiring, update at http://sbi-kyc.in-verify.top or the account will be blocked'
kyc = json.loads(mobile.verdict('sms', kyc_text, 'whatsapp'))
assert kyc['level'] == 'danger' and kyc['report_card']['category'] == 'kyc_payment', kyc.get('report_card')
assert 'Medium: WhatsApp' in kyc['report_card']['report_en']
assert 'hxxp://in-verify[.]top' in kyc['report_card']['family_en']
assert json.loads(mobile.verdict('sms', kyc_text))['report_card']['category'] == 'kyc_payment'
assert 'Medium: SMS or WhatsApp message' in json.loads(mobile.verdict('sms', kyc_text, 'bogus'))['report_card']['report_en']
assert 'report_card' not in upi_merch and 'report_card' in upi_scam and 'report_card' in upi_unknown
assert 'report_card' not in json.loads(mobile.verdict('flow', 'many connections to different ports from one host in a few seconds'))
debit = json.loads(mobile.verdict('sms', 'SBI: Rs 2,450 debited via UPI. OTP 482910 kisi se share mat karein. If not you, block card in YONO app.'))
assert 'report_card' not in debit, debit.get('report_card')
_card = mobile.report_card.card
mobile.report_card.card = lambda *a, **k: 1 / 0
broken = json.loads(mobile.verdict('sms', kyc_text))
mobile.report_card.card = _card
assert broken['level'] == kyc['level'] and broken['evidence'] == kyc['evidence'] and 'report_card' not in broken
# The report card never changes the verdict fields.
same = {k: v for k, v in kyc.items() if k not in ('report_card', 'report_card_raised', 'detector_ms')}
assert same == {k: v for k, v in broken.items() if k != 'detector_ms'}
print('report card through mobile.verdict passed')

# Remote-app banner flag: set for money-desk scams, absent for clear and network results, never fatal.
assert kyc.get('remote_app_check') is True
assert json.loads(mobile.verdict('sms', 'Install AnyDesk so our support executive can process your refund')).get('remote_app_check') is True
assert 'remote_app_check' not in upi_merch
assert 'remote_app_check' not in json.loads(mobile.verdict('flow', 'many connections to different ports from one host in a few seconds'))
_needs = mobile.remote_apps.needs_check
mobile.remote_apps.needs_check = lambda *a, **k: 1 / 0
broken_ra = json.loads(mobile.verdict('sms', kyc_text))
mobile.remote_apps.needs_check = _needs
assert broken_ra['level'] == kyc['level'] and 'remote_app_check' not in broken_ra
print('remote app flag through mobile.verdict passed')
