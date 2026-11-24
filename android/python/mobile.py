"""Android adapter. The reference triage package is copied unchanged at build time."""
import json
import re
import sys
import time
import types
from pathlib import Path
import numpy as np
import portable

# detect imports joblib at module level, but Android never loads pickles: the
# detectors below use exported portable parameters. Chaquopy ships no joblib,
# so register an inert stub that fails loudly if anything tries to unpickle.
def _no_pickles(*a, **k): raise RuntimeError('joblib.load is not available on Android')
sys.modules['joblib'] = types.SimpleNamespace(load=_no_pickles)

# detect imports textmodel; Android uses the import-free inference equivalent.
from triage import mech
textmodel = types.ModuleType('triage.textmodel')
textmodel.prob = lambda bundle, texts: np.array([portable.probability('indic', t) for t in texts])
sys.modules['triage.textmodel'] = textmodel
from triage import detect, explain_hi, llm, sender, upi
detect.textmodel = textmodel

class Linear:
    def __init__(self, name): self.name = name
    def predict_proba(self, texts):
        p = np.array([portable.probability(self.name, t) for t in texts])
        return np.stack((1-p, p), axis=1)
detect._model = lambda name: Linear(name)
detect.indic_model = lambda: None

class BridgeExplainer(llm.Explainer):
    def __init__(self, runner):
        self.runner = runner
    def _run(self, prompt):
        data = json.loads(str(self.runner.generate(prompt)))
        text = llm.tidy(re.sub(r'<\|[^|]*\|>', '', data['text']).strip())
        return text, data['stats']

VERDICT = {0: 'NO RISK FOUND — still verify', 1: 'DANGEROUS', 'uncertain': 'SUSPICIOUS'}
_last = {}

# Sextortion and extortion are non-financial: cybercrime.gov.in is the primary report.
# A completed debit is not a scam_type() phrase (verdict 0 returns ""); DEBIT_STEP marks it.
_CYBER_PRIMARY = ('sextortion or blackmail', 'an extortion threat')
_MONEY_TAKEN = frozenset()
# Brand imitation or a digit-for-letter swap leads a link result; the rest stay in detector order.
_LINK_LEAD = re.compile(
    r"imitat|lookalike|letters for digits|digit-for-letter|not that company.s official site",
    re.I)


def _load_hindi():
    """Hindi step lines and button labels, read once.

    android/python is on sys.path under Chaquopy, so the JSON sits beside this file.
    importlib.resources is the fallback when the loader does not expose __file__ as a real path.
    """
    path = Path(__file__).resolve().parent / 'hindi_steps.json'
    if path.is_file():
        return json.loads(path.read_text(encoding='utf-8'))
    import importlib.resources as resources
    return json.loads(resources.files('mobile').joinpath('hindi_steps.json').read_text(encoding='utf-8'))


_HINDI = _load_hindi()


def _actions_hi(actions):
    table = _HINDI.get('steps') or {}
    return [table.get(step, '') for step in (actions or [])]


def _promote_link_signals(ev):
    lead, rest = [], []
    for line in ev or []:
        (lead if _LINK_LEAD.search(str(line)) else rest).append(line)
    return lead + rest


def _button(key):
    label = _HINDI['buttons'][key]
    return {'id': key, 'en': label['en'], 'hi': label['hi']}


def _report_buttons(kind, lab, scam, actions):
    """Primary then secondary report buttons, or None when the screen has no pair.

    Suspicious keeps a single 1930 row, and a network event has no report buttons.
    Before any loss, Chakshu is primary and 1930 is secondary. When money was already
    taken (that scam type, or DEBIT_STEP in the steps), 1930 is primary and
    cybercrime.gov.in is secondary. Sextortion and extortion lead with cybercrime.gov.in.
    """
    if kind == 'flow' or lab == 'uncertain':
        return None
    debit = llm.DEBIT_STEP in (actions or [])
    if lab != 1 and not debit:
        return None
    # A completed loss outranks the sextortion channel: 1930 is the golden-hour line.
    if debit or scam in _MONEY_TAKEN:
        primary, secondary = 'lost_money_1930', 'report_cybercrime'
    elif scam in _CYBER_PRIMARY:
        primary, secondary = 'report_cybercrime', 'lost_money_1930'
    else:
        primary, secondary = 'report_chakshu', 'lost_money_1930'
    return {'primary': _button(primary), 'secondary': _button(secondary)}


def _flow_json(text):
    f = json.loads(text); p = portable.flow_probability(f); ev = []
    if f.get('num_failed_logins', 0) > 0: ev.append(f"{int(f['num_failed_logins'])} failed login attempts on the connection"); p = max(p, .9)
    if f.get('wrong_fragment', 0) > 0: ev.append('malformed packet fragments, typical of a teardrop or ping-of-death flood'); p = max(p, .9)
    if f.get('land', 0) > 0: ev.append('source and destination are the same host and port'); p = max(p, .9)
    if f.get('serror_rate', 0) > .5: ev.append('most connections were half-open (SYN errors)')
    if f.get('dst_host_diff_srv_rate', 0) > .5: ev.append('the host contacted many different services')
    if f.get('root_shell', 0) > 0: ev.append('a root shell was obtained')
    return (1 if p >= .1 else 0), p, ev


_QUOTE_STOP = {
    'about', 'after', 'also', 'anyone', 'asks', 'been', 'before', 'check', 'common', 'customer',
    'details', 'domain', 'found', 'from', 'have', 'into', 'link', 'looks', 'message', 'mobile',
    'never', 'number', 'official', 'only', 'other', 'personal', 'phone', 'please', 'reads',
    'report', 'says', 'sender', 'share', 'sites', 'that', 'their', 'there', 'these', 'this',
    'those', 'through', 'update', 'using', 'verify', 'what', 'when', 'where', 'which', 'while',
    'will', 'with', 'your',
}
_QUOTE_SHORT = ('otp', 'kyc', 'pin', 'cvv', 'upi', 'pan', 'atm')


def _stem(word):
    w = word.lower()
    for suf in ('ing', 'ed', 'es', 's'):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[:-len(suf)]
    return w


def _defang(span):
    def one(match):
        url = match.group(0)
        url = re.sub(r'(?i)^https?', 'hxxp', url)
        return url.replace('.', '[.]')
    return re.sub(r'(?i)https?://\S+|www\.\S+', one, span)


def _mask_codes(span):
    """Mask OTP-like 4–8 digit runs. Longer numbers are masked as a block."""
    span = re.sub(r'(?<!\d)(\d{10,})(?!\d)', lambda m: '•' * len(m.group(1)), span)
    return re.sub(r'(?<!\d)(\d{4,8})(?!\d)', lambda m: '•' * len(m.group(1)), span)


def _clip(span, limit=48):
    span = span.strip()
    if len(span) <= limit:
        return span
    return span[:limit - 1].rstrip() + '…'


def _upi_quote(evidence, parsed, limit=48):
    """Quote the exact parsed UPI field an evidence line refers to, or ''."""
    low = str(evidence or '').lower()
    if not parsed:
        return ''
    if any(w in low for w in ('upi id', 'handle', 'vpa', 'pa)')) and parsed.get('pa'):
        return _clip(f"pa={parsed['pa']}", limit)
    if any(w in low for w in ('payee name', 'poses as', 'claimed organisation', 'claiming')) and parsed.get('pn'):
        return _clip(f"pn={parsed['pn']}", limit)
    if any(w in low for w in ('merchant code', 'merchant category', 'mcc', 'p2p code')) and parsed.get('mc'):
        return _clip(f"mc={parsed['mc']}", limit)
    if any(w in low for w in ('amount', 'pre-fills', 'minimum payment', 'debit')) and parsed.get('am'):
        return _clip(f"am={parsed['am']}", limit)
    if 'currency' in low and parsed.get('cu'):
        return _clip(f"cu={parsed['cu']}", limit)
    if 'reference link' in low and parsed.get('url'):
        return _clip(_defang(parsed['url']), limit)
    if any(w in low for w in ('note', 'refund', 'cashback', 'pin', 'kyc', 'urgent', 'customs', 'fee', 'inject')) and parsed.get('tn'):
        return _clip(_defang(parsed['tn']), limit)
    if 'autopay' in low or 'mandate' in low or 'collect' in low:
        return _clip(f"{parsed.get('scheme', 'upi')}://{parsed.get('action', 'pay')}", limit)
    return ''


def quote_span(evidence, text, limit=48):
    """Short span of the user's text that an evidence line refers to, or ''.

    Hosts and numbers have to occur in the message. A keyword quote needs two
    content-word hits, or one long hit, inside 48 characters. Nothing is invented.
    """
    ev = str(evidence or '')
    src = str(text or '')
    if not ev.strip() or not src.strip():
        return ''
    if upi.is_upi_payload(src):
        return _upi_quote(ev, upi.parse_upi(src), limit)
    low_ev = ev.lower()
    low = src.lower()
    urls = list(re.finditer(r'(?i)https?://[^\s<>"\']+|www\.[^\s<>"\']+', src))
    hosts = re.findall(r'(?i)\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b', ev)
    for match in urls:
        host_m = re.search(r'(?i)(?:https?://)?([^/\s:?#]+)', match.group(0))
        host = (host_m.group(1) if host_m else '').lower().strip('.')
        if host and (host in low_ev or any(h.lower() in host or host in h.lower() for h in hosts)):
            return _clip(_mask_codes(_defang(match.group(0))), limit)
    if len(urls) == 1 and hosts:
        return _clip(_mask_codes(_defang(urls[0].group(0))), limit)

    hits = []
    stems = []
    for word in re.findall(r'[A-Za-z\u0900-\u097F]{4,}', ev):
        stem = _stem(word)
        if stem in _QUOTE_STOP or word.lower() in _QUOTE_STOP or len(stem) < 4:
            continue
        stems.append(stem)
    for word in re.findall(r'(?i)\b(?:otp|kyc|pin|cvv|upi|pan|atm)\b', ev):
        stems.append(word.lower())
    for stem in dict.fromkeys(stems):
        for match in re.finditer(re.escape(stem), low):
            if match.start() and low[match.start() - 1].isalpha():
                continue
            hits.append((match.start(), match.end(), 3 if len(stem) >= 7 or stem in _QUOTE_SHORT else 1))
    if re.search(r'(?i)otp|pin|cvv|password|number|call|mobile|phone', ev):
        for match in re.finditer(r'(?<!\d)(\d{4,})(?!\d)', src):
            hits.append((match.start(), match.end(), 3))
    for number in re.findall(r'\d{4,}', ev):
        at = src.find(number)
        if at >= 0:
            hits.append((at, at + len(number), 3))
    if not hits:
        return ''
    hits.sort()
    best = None
    best_score = 0
    for i, (start, end, score) in enumerate(hits):
        window_end = end
        total = score
        for start2, end2, score2 in hits[i + 1:]:
            if end2 - start > limit:
                break
            window_end = max(window_end, end2)
            total += score2
        strong = total >= 2 or score >= 3
        if strong and total > best_score:
            best_score = total
            best = (start, window_end)
    if not best:
        return ''
    start, end = best
    while start > 0 and not src[start - 1].isspace() and end - (start - 1) <= limit:
        start -= 1
    while end < len(src) and not src[end].isspace() and (end + 1) - start <= limit:
        end += 1
    span = src[start:end].strip(' \t\r\n.,;:\'"')
    span = _clip(_mask_codes(_defang(span)), limit)
    return span if len(span) >= 3 else ''


def verdict(kind, text, sender_id=''):
    """Stage 1, no Llama: verdict, scam type, evidence and vetted actions in milliseconds.

    sender_id is the optional sender typed on the check screen. It can only raise a text message
    to SUSPICIOUS (sender.py); with none the output is exactly what it was without the field."""
    t0 = time.perf_counter()
    is_upi = kind == 'upi' or (kind in ('url', 'sms') and upi.is_upi_payload(text))
    upi_info = None
    if is_upi:
        analysis = upi.analyze_upi(text)
        lab, score, ev = analysis['label'], analysis['score'], analysis['evidence']
        if analysis['is_upi']:
            upi_info = analysis['summary']
    elif kind == 'flow' and text.strip().startswith('{'):
        lab, score, ev = _flow_json(text)
    else:
        lab, score, ev = detect.classify_any(kind, text)
    why = None if is_upi else sender.reason(kind, text, sender_id)
    lab, score, _ = sender.apply(lab, score, ev, why)
    if kind == 'url' and not is_upi:
        ev = _promote_link_signals(ev)
    # A cleared item, or a debit alert to confirm, must not show the threat phrase the detector
    # overruled or set aside.
    if lab in (0, 'uncertain'):
        ev = llm.benign_evidence('upi' if is_upi else kind, text, ev, lab)
    if why:
        ev = [sender.SENDER_LINE] + [line for line in ev if line != sender.SENDER_LINE]
    ms = (time.perf_counter() - t0) * 1000
    eff_kind = 'upi' if is_upi else kind
    actions = llm.actions_for(eff_kind, lab, text)
    scam = llm.scam_type(eff_kind, text, lab)
    try:
        summary_hi = explain_hi.summary_hi(eff_kind, text, lab, ev)
    except Exception:
        summary_hi = ''  # the Hindi summary is an aid; the verdict never depends on it
    if summary_hi and why:
        summary_hi = f'{summary_hi} {sender.SENDER_LINE_HI}।'
    _last.clear(); _last.update(kind=eff_kind, text=text, lab=lab, ev=ev, why=why, sender=sender_id if why else None)
    out = {'verdict': VERDICT[lab], 'level': {1: 'danger', 'uncertain': 'warn', 0: 'clear'}[lab],
           'score': score, 'scam_type': scam, 'evidence': ev,
           'evidence_quotes': ['' if line == sender.SENDER_LINE else quote_span(line, text) for line in ev],
           'actions': actions, 'actions_hi': _actions_hi(actions),
           'buttons': _HINDI['buttons'], 'detector_ms': ms}
    if summary_hi:
        out['summary_hi'] = summary_hi
        out['summary_hi_label'] = explain_hi.label_hi()
    if upi_info:
        out['upi'] = upi_info
    if why:
        out['sender_raised'] = why
    report = _report_buttons(eff_kind, lab, scam, actions)
    if report:
        out['report_buttons'] = report
    return json.dumps(out, ensure_ascii=False)


def _replacement_pool(kind, lab, text):
    """Vetted sentences that replace a generated line, from advice_for and ACTIONS."""
    pool = []
    seen = set()

    def add(sentence):
        line = (sentence or '').strip()
        if line and line not in seen:
            seen.add(line)
            pool.append(line)

    try:
        add(llm.advice_for(kind, lab, text)[0])
    except Exception:
        pass
    table = llm.FLOW_ACTIONS if kind == 'flow' else llm.ACTIONS
    for acts in table.values():
        if acts:
            add(acts[0])
    for tail, _acts in llm.TYPE_ADVICE.values():
        add(tail)
    for fact in llm.ALL_FACTS:
        add(fact)
    return pool


def ends_with_replacement(explanation, kind, lab, text):
    """True when the explanation ends on a vetted sentence substituted for model text."""
    body = (explanation or '').strip()
    if not body:
        return False
    return any(body.endswith(sent) for sent in _replacement_pool(kind, lab, text))


def explain(runner):
    """Stage 2: the on-device Llama explanation for the item from the last verdict() call."""
    ex = BridgeExplainer(runner)
    extra = {'sender_reason': _last['why'], 'sender_id': _last['sender']} if _last.get('why') else {}
    text, stats = ex.generate(ex.prompt(_last['kind'], _last['text'], _last['lab'], _last['ev'], **extra))
    # The explainer reports replacement explicitly; suffix matching is the fallback for old stats.
    replaced = stats.get('replaced')
    if replaced is None:
        replaced = ends_with_replacement(text, _last['kind'], _last['lab'], _last['text'])
    return json.dumps({'explanation': text, 'llm': stats, 'replaced': replaced}, ensure_ascii=False)


def check(kind, text, runner, sender_id=''):
    """Both stages in one call (tests and the command line)."""
    out = json.loads(verdict(kind, text, sender_id))
    out.update(json.loads(explain(runner)))
    return json.dumps(out, ensure_ascii=False)
