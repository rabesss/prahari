"""Offline app-file (.apk) check. Rules decide the verdict; Llama only phrases the evidence.

MainActivity (ApkInspector.kt) copies a shared or picked .apk to the app cache, reads its metadata
with PackageManager.getPackageArchiveInfo, deletes the copy and passes the facts here as JSON.
Nothing in this module or on the Kotlin side installs, opens or runs the app.

The verdict uses six permission groups that Android banking trojans and screen-control scams rely
on, whether the app's name claims a bank, UPI app or government office, and whether a signing
certificate could be read. It is advisory: a clean result means none of these signs were found,
not that the app is safe. This module never touches the message, link or network detectors.
"""
import json
import re
import time
from pathlib import Path

from triage import explain_hi, llm

# Permission -> signal group. BIND_ACCESSIBILITY_SERVICE and BIND_DEVICE_ADMIN are declared as the
# android:permission of a service or receiver, so ApkInspector.kt adds component permissions too.
PERMS = {
    'android.permission.READ_SMS': 'sms',
    'android.permission.RECEIVE_SMS': 'sms',
    'android.permission.BIND_ACCESSIBILITY_SERVICE': 'accessibility',
    'android.permission.BIND_DEVICE_ADMIN': 'admin',
    'android.permission.SYSTEM_ALERT_WINDOW': 'overlay',
    'android.permission.REQUEST_INSTALL_PACKAGES': 'installer',
    'android.permission.READ_CALL_LOG': 'calls',
}
ORDER = ('sms', 'accessibility', 'admin', 'overlay', 'installer', 'calls')
# Groups that let an app read or drive the screen: with SMS access they complete an OTP theft.
TAKEOVER = {'accessibility', 'overlay', 'admin'}

# Evidence lines (noun phrases that follow "This app file is DANGEROUS: ") with their Hindi.
EVIDENCE = {
    'sms': ('asks to read your SMS, where bank OTP codes arrive',
            'आपके SMS पढ़ने की अनुमति माँगता है, जहाँ बैंक के OTP आते हैं'),
    'accessibility': ('asks for Accessibility access, which can read your screen and tap for you',
                      'Accessibility अनुमति माँगता है, जिससे यह आपकी स्क्रीन पढ़ सकता है और आपकी जगह टैप कर सकता है'),
    'admin': ('asks to be a device admin, which can lock the phone and block removal',
              'डिवाइस एडमिन बनना चाहता है, जिससे यह फ़ोन लॉक कर सकता है और खुद को हटने से रोक सकता है'),
    'overlay': ('can draw over other apps, a trick used for fake login screens',
                'दूसरे ऐप के ऊपर दिख सकता है, जिससे नकली लॉगिन स्क्रीन बनाई जाती है'),
    'installer': ('can ask to install other apps',
                  'दूसरे ऐप इंस्टॉल करने की अनुमति माँगता है'),
    'calls': ('asks to read your call history',
              'आपकी कॉल हिस्ट्री पढ़ने की अनुमति माँगता है'),
    'unsigned': ('Android could not read a signing certificate from this file',
                 'Android इस फ़ाइल से साइनिंग सर्टिफ़िकेट नहीं पढ़ पाया'),
    'debug': ('signed with a test (debug) certificate, which Play Store apps do not use',
              'टेस्ट (debug) सर्टिफ़िकेट से साइन है, जो Play Store के ऐप में नहीं होता'),
    'none': ('none of the high-risk permissions Prahari looks for',
             'इसमें वे जोखिम वाली अनुमतियाँ नहीं हैं जिन्हें प्रहरी देखता है'),
    'signed': ('a signing certificate was read; Prahari does not check who it belongs to',
               'साइनिंग सर्टिफ़िकेट मिला; यह किसका है, प्रहरी इसकी जाँच नहीं करता'),
}
CLAIM_EN = 'named like {brand}; real bank and government apps come from Play Store'
CLAIM_HI = 'नाम {brand} जैसा है; असली बैंक और सरकारी ऐप Play Store से आते हैं'

# One vetted fact per lead signal: the sentence Llama is asked to build on.
FACTS = {
    'claim': 'Fake bank and government apps are often shared as files on WhatsApp.',
    'sms': 'An app that reads SMS can steal the OTPs your bank sends.',
    'accessibility': 'Accessibility access lets an app see your screen and tap for you.',
    'admin': 'Device admin access can stop you from removing the app.',
    'overlay': 'Apps that draw over others can show fake login screens.',
    'installer': 'This permission lets an app add more apps from outside Play Store.',
    'calls': 'Call history shows whom you talk to and when.',
    'unsigned': 'Without a readable signature, the maker of an app cannot be checked.',
    'debug': 'Apps on Play Store are never signed with a debug certificate.',
    'none': 'Installing apps from Play Store adds a safety check.',
}

# Plain words for the prompt snippet. Only these, never raw permission strings from the file.
PLAIN = {
    'sms': 'read SMS, where bank OTP codes arrive',
    'accessibility': 'Accessibility access',
    'admin': 'device admin',
    'overlay': 'draw over other apps',
    'installer': 'install other apps',
    'calls': 'read call history',
}

# Vetted steps per verdict, (English, Hindi). Written by hand; no translation service.
STEPS = {
    1: [
        ('Do not install this app. Delete the file.', 'यह ऐप इंस्टॉल न करें। फ़ाइल डिलीट कर दें।'),
        ('If you already installed it, turn on airplane mode and uninstall it.',
         'अगर इंस्टॉल कर लिया है, तो एयरप्लेन मोड चालू करें और ऐप हटा दें।'),
        ('Then call your bank from the number on your card and change your UPI PIN.',
         'फिर कार्ड पर लिखे नंबर से बैंक को कॉल करें और UPI PIN बदलें।'),
        ('Lost money? Call 1930 or report at cybercrime.gov.in.',
         'पैसे गए? 1930 पर कॉल करें या cybercrime.gov.in पर शिकायत करें।'),
    ],
    'uncertain': [
        ('Do not install it from this file.', 'इस फ़ाइल से इंस्टॉल न करें।'),
        ('Get the app from Play Store by searching its official name.',
         'Play Store में असली नाम खोजकर ऐप लें।'),
        ('If a caller or message told you to install it, stop and hang up.',
         'अगर किसी कॉल या मैसेज ने इसे इंस्टॉल करने को कहा, तो रुकें और कॉल काट दें।'),
    ],
    0: [
        ('Install apps from Play Store when you can.', 'जहाँ हो सके, ऐप Play Store से ही इंस्टॉल करें।'),
        ('Never allow SMS or Accessibility access to an app you are unsure about.',
         'जिस ऐप पर भरोसा न हो, उसे SMS या Accessibility की अनुमति कभी न दें।'),
    ],
}

# Types say what the file shows, not what the code does: Prahari never reads the app's code.
SCAM = {
    'claim': ('an app file named like a bank or government app', 'बैंक या सरकारी ऐप जैसे नाम वाली ऐप फ़ाइल'),
    'high': ('a high-risk app file', 'बहुत जोखिम वाली ऐप फ़ाइल'),
    'check': ('an app file to check', 'जाँचने लायक ऐप फ़ाइल'),
}

SUMMARY_HI = {
    1: 'यह ऐप फ़ाइल खतरनाक है: {ev}। इसे इंस्टॉल न करें।',
    'uncertain': 'इस ऐप फ़ाइल की जाँच ज़रूरी है: {ev}। इसे इस फ़ाइल से इंस्टॉल न करें।',
    0: 'इस ऐप फ़ाइल में बड़े जोखिम के संकेत नहीं मिले। फिर भी ऐप Play Store से लेना ज़्यादा सुरक्षित है।',
}

VERDICT = {0: 'NO RISK FOUND — still verify', 1: 'DANGEROUS', 'uncertain': 'SUSPICIOUS'}
LEVEL = {1: 'danger', 'uncertain': 'warn', 0: 'clear'}
SCORE = {1: 0.9, 'uncertain': 0.5, 0: 0.05}

# Bank, UPI and government names. A prefix entry also matches a run-on token ("sbirewards",
# "pmkisanyojana"); the others need a whole word, since "axis", "bob" or "rto" are common inside
# other words. Matched against the label, package and file name after splitting on dots,
# underscores, dashes and camelCase.
_BRANDS = [
    ('SBI', r'\bsbi|\bstate bank\b'), ('YONO', r'\byono'), ('HDFC', r'\bhdfc'), ('ICICI', r'\bicici'),
    ('Axis Bank', r'\baxis ?bank\b'), ('Kotak', r'\bkotak\b'), ('PNB', r'\bpnb\b|\bpunjab national\b'),
    ('Canara Bank', r'\bcanara\b'), ('Bank of Baroda', r'\bbank of baroda\b|\bbob ?world\b|\bbaroda\b'),
    ('Union Bank', r'\bunion bank\b'), ('IDBI', r'\bidbi\b'), ('IndusInd', r'\bindusind'),
    ('Paytm', r'\bpaytm'), ('PhonePe', r'\bphonepe'), ('Google Pay', r'\bgoogle ?pay\b|\bgpay\b'),
    ('BHIM', r'\bbhim\b'), ('NPCI', r'\bnpci\b'), ('UPI', r'\bupi\b'),
    ('RBI', r'\brbi\b|\breserve bank\b'), ('Aadhaar', r'\baadhaa?r|\buidai|आधार'),
    ('Income Tax', r'\bincome ?tax\b|आयकर'), ('GST', r'\bgst\b'), ('EPFO', r'\bepfo'),
    ('PM Kisan', r'\bpm ?kisan|किसान'), ('RTO', r'\brto\b|\bparivahan|\be ?challan|\bchallan\b|चालान'),
    ('DigiLocker', r'\bdigilocker'), ('UMANG', r'\bumang\b'), ('India Post', r'\bindia ?post\b'),
    ('Customs', r'\bcustoms\b'), ('TRAI', r'\btrai\b'), ('CBI', r'\bcbi\b'),
    ('Police', r'\bpolice\b|\bcyber ?crime\b|पुलिस'), ('Electricity board', r'\belectricity\b|\bbijli\b|बिजली'),
    ('Government', r'\bgovt\b|\bgovernment\b|\bsarkar|सरकार'),
    ('Bank', r'\bbank\b|\bkyc\b|बैंक'),
]
BRANDS = [(name, re.compile(pat, re.I)) for name, pat in _BRANDS]

_CONTROL = re.compile(r'[\x00-\x1f\x7f-\x9f​-‏‪-‮⁦-⁩﻿]')
_PERM = re.compile(r'^[A-Za-z0-9_.]{1,200}$')
_PKG = re.compile(r'^[A-Za-z0-9_.]{1,200}$')
_last = {}


def _load_buttons():
    path = Path(__file__).resolve().parent / 'hindi_steps.json'
    return json.loads(path.read_text(encoding='utf-8'))['buttons']


_BUTTONS = _load_buttons()


def _text(value, limit):
    """One line, no control or direction-override characters, at most limit characters."""
    s = _CONTROL.sub(' ', str(value or ''))
    s = re.sub(r'\s+', ' ', s).strip()
    return s[:limit]


def clean(facts):
    """The facts JSON from ApkInspector.kt with every field typed and bounded."""
    if isinstance(facts, str):
        facts = json.loads(facts)
    if not isinstance(facts, dict):
        raise ValueError('app facts must be a JSON object')
    pkg = _text(facts.get('package'), 200)
    perms = facts.get('permissions') or []
    if not isinstance(perms, list):
        perms = []
    perms = sorted({p for p in (str(x) for x in perms[:2000]) if _PERM.match(p)})
    try:
        size = max(0, int(facts.get('size_bytes') or 0))
    except (TypeError, ValueError):
        size = 0
    return {
        'package': pkg if _PKG.match(pkg) else '',
        'label': _text(facts.get('label'), 80),
        'file_name': _text(facts.get('file_name'), 120),
        'version': _text(facts.get('version'), 40),
        'size_bytes': size,
        'permissions': perms,
        # 'present' only when a certificate was read; anything else is 'unknown', never 'unsigned':
        # a failed read is not proof that the file has no signature.
        'signing': 'present' if facts.get('signing') == 'present' else 'unknown',
        'debug_cert': facts.get('signing') == 'present' and bool(facts.get('debug_cert')),
    }


def _words(value):
    """Tokens for name matching: camelCase, dots, underscores and dashes become spaces."""
    s = re.sub(r'(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])', ' ', value or '')
    s = re.sub(r'(?i)\.apk$', '', s.strip())
    return re.sub(r'[._\-]+', ' ', s).lower()


def claimed_brand(f):
    """The bank, UPI or government name the app's label, package or file name claims, or ''."""
    for field in (f['label'], f['file_name'], f['package']):
        text = _words(field)
        if not text:
            continue
        for name, pattern in BRANDS:
            if pattern.search(text):
                return name
    return ''


def groups(f):
    found = {PERMS[p] for p in f['permissions'] if p in PERMS}
    return [g for g in ORDER if g in found]


def rule_verdict(f):
    """(label, signals, brand): label is 1, 'uncertain' or 0; signals in evidence order."""
    risky = groups(f)
    brand = claimed_brand(f)
    signals = (['claim'] if brand else []) + risky
    if f['signing'] != 'present':
        signals.append('unsigned')
    elif f['debug_cert']:
        signals.append('debug')
    have = set(risky)
    if (brand and have) or ('sms' in have and have & TAKEOVER) or {'accessibility', 'overlay'} <= have \
            or len(have) >= 3:
        lab = 1
    elif signals:
        lab = 'uncertain'
    else:
        lab = 0
    return lab, signals, brand


def _evidence(signals, brand, signed):
    if not signals:
        keys = ['none'] + (['signed'] if signed else [])
        return [EVIDENCE[k][0] for k in keys], [EVIDENCE[k][1] for k in keys]
    en, hi = [], []
    for key in signals:
        if key == 'claim':
            en.append(CLAIM_EN.format(brand=brand))
            hi.append(CLAIM_HI.format(brand=brand))
        else:
            en.append(EVIDENCE[key][0])
            hi.append(EVIDENCE[key][1])
    return en, hi


def _scam(lab, signals):
    if lab == 0:
        return '', ''
    if lab == 1:
        return SCAM['claim'] if 'claim' in signals else SCAM['high']
    return SCAM['check']


def verdict(facts_json):
    """Stage 1, no Llama: verdict, evidence and vetted steps for one app file."""
    t0 = time.perf_counter()
    f = clean(facts_json)
    lab, signals, brand = rule_verdict(f)
    ev, ev_hi = _evidence(signals, brand, f['signing'] == 'present')
    scam, scam_hi = _scam(lab, signals)
    steps = STEPS[lab]
    lead = signals[0] if signals else 'none'
    out = {
        'verdict': VERDICT[lab], 'level': LEVEL[lab], 'score': SCORE[lab],
        'scam_type': scam, 'scam_type_hi': scam_hi,
        'evidence': ev, 'evidence_hi': ev_hi, 'evidence_quotes': [''] * len(ev),
        'actions': [s[0] for s in steps], 'actions_hi': [s[1] for s in steps],
        'buttons': _BUTTONS,
        'summary_hi': SUMMARY_HI[lab].format(ev=ev_hi[0] if ev_hi else ''),
        'summary_hi_label': explain_hi.label_hi(),
        'apk': {'package': f['package'], 'label': f['label'], 'signals': signals},
        'detector_ms': (time.perf_counter() - t0) * 1000,
    }
    if lab == 1:
        out['report_buttons'] = {
            'primary': dict(id='report_cybercrime', **_BUTTONS['report_cybercrime']),
            'secondary': dict(id='lost_money_1930', **_BUTTONS['lost_money_1930']),
        }
    _last.clear()
    _last.update(lab=lab, ev=ev, signals=signals, brand=brand, fact=FACTS[lead if lead in FACTS else 'none'])
    return json.dumps(out, ensure_ascii=False)


def snippet(signals, brand):
    """What Llama sees: fixed words chosen by the rules only. The app's own label, package and file
    name are attacker-chosen text, so they never enter the prompt; the screen shows them as data."""
    risky = [PLAIN[g] for g in signals if g in PLAIN]
    sig = ('not readable' if 'unsigned' in signals else
           'test (debug) certificate' if 'debug' in signals else 'present')
    return '\n'.join([
        'Android app file (.apk) shared to this phone',
        'Name claims: ' + (f'{brand}, a bank or government name' if brand else 'no bank or government name'),
        'Asks for: ' + (', '.join(risky) if risky else 'none of the high-risk permissions'),
        f'Signature: {sig}',
    ])


def opening(lab, ev):
    head = {1: 'This app file is DANGEROUS', 0: 'No risk found for this app file'}.get(
        lab, 'This app file needs a check')
    return f'{head}: {ev[0]}' if ev else head


def prompt():
    """Llama 3 chat prompt for the last verdict, registered with llm's validator context."""
    lab, ev, fact = _last['lab'], _last['ev'], _last['fact']
    snip = snippet(_last['signals'], _last['brand'])
    first = opening(lab, ev)
    user = (f'App file:\n"""\n{snip}\n"""\n'
            f'Verdict: {llm.VERDICT_WORD[lab]}\n'
            f'Start your answer with exactly: "{first}." '
            f'Then write one more sentence, 6-12 words, that tells the reader why, using this fact: {fact}')
    built = ('<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n' + llm.SYSTEM +
             '<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n' + user +
             '<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n')
    if len(llm._TAILS) > 256:
        llm._TAILS.clear()
        llm._CTX.clear()
    # The replacement for unsafe advice ("install it to check") is the first vetted step.
    llm._TAILS[built] = STEPS[lab][0][0]
    # The validator checks generated claims against this text: the snippet plus the evidence.
    llm._CTX[built] = {'kind': 'apk', 'input': snip + '\n' + '\n'.join(ev), 'verdict': lab,
                       'fact': fact, 'evidence': list(ev)}
    return built


# Advice to install, allow or trust the app, or a claim that it is safe. The shared validator skips
# its compliance check on NO RISK results and has no app-file cues, so app files get this pass on
# every verdict: a clean result still means "verify", never "safe to install".
_UNSAFE = re.compile(r"\b(?:install\w*|download\w*|sideload\w*|allow\w*|grant\w*|enabl\w*|permit\w*|"
                     r"accept\w*|approv\w*|trust\w*|open\w*|run|launch\w*|update\w*|safe|safely|legit\w*|"
                     r"genuine|official|harmless|verified|real|clean)\b", re.I)
_NEG = re.compile(r"\b(?:not|never|no|don't|dont|do not|avoid|without|before|stop|refuse|isn't|aren't|cannot|can't)\b",
                  re.I)


def _unsafe(sentence):
    for clause in re.split(r"[,;:]|\b(?:and|but|so|then)\b", sentence, flags=re.I):
        for m in _UNSAFE.finditer(clause):
            if not _NEG.search(clause[:m.start()]):
                return True
    return False


def guard(text, first, fact, tail=''):
    """(text, dropped): generated sentences that urge installing or trusting the app removed.

    The opening (built from the rules' own evidence) and vetted sentences are kept. When a sentence
    is dropped and nothing generated is left, ValueError sends explain() to the fixed text."""
    vetted = {v.strip() for v in (fact, tail) if v}
    kept, dropped, generated = [], [], False
    for i, sent in enumerate(llm._split(text or '', first)):
        if i == 0 and first and sent.startswith(first):
            kept.append(sent)
            continue
        if sent.strip() in vetted:
            kept.append(sent)
        elif _unsafe(sent):
            dropped.append(sent)
        else:
            kept.append(sent)
            generated = True
    if dropped and not generated:
        raise ValueError('every generated app-file sentence was unsafe')
    if dropped and fact and fact not in kept:
        kept.append(fact)
    return ' '.join(k.strip() for k in kept).strip(), len(dropped)


def detector_text():
    """Fixed text without a model call: the opening plus the vetted fact."""
    return f"{opening(_last['lab'], _last['ev'])}. {_last['fact']}".strip()


def explain(runner):
    """Stage 2: Llama phrases the evidence; the detector's fixed text if every reply fails."""
    from mobile import BridgeExplainer, ExplainTimeout  # mobile imports the detectors; load lazily
    ex = BridgeExplainer(runner)
    built = prompt()
    try:
        text, stats = ex.generate(built)
        text, dropped = guard(text, opening(_last['lab'], _last['ev']), _last['fact'], llm._TAILS.get(built, ''))
        if dropped:
            stats['apk_guard_dropped'] = dropped
            stats['replaced'] = True
    except (ValueError, ExplainTimeout) as exc:
        stats = dict(ex.last_stats or {})
        reason = 'timeout' if isinstance(exc, ExplainTimeout) else 'checks_failed'
        stats['fallback'] = reason
        return json.dumps({'explanation': detector_text(), 'llm': stats, 'replaced': False,
                           'fallback': reason, 'source': 'detector_template'}, ensure_ascii=False)
    return json.dumps({'explanation': text, 'llm': stats, 'replaced': bool(stats.get('replaced'))},
                      ensure_ascii=False)


def vetted_explanation():
    """Stage 2 without Llama (NO RISK with flagged-only gating)."""
    return json.dumps({'explanation': detector_text(), 'llm': None, 'replaced': False,
                       'llama_skipped': True, 'source': 'detector_template'}, ensure_ascii=False)
