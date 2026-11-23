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
from triage import detect, llm
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


def verdict(kind, text):
    """Stage 1, no Llama: verdict, scam type, evidence and vetted actions in milliseconds."""
    t0 = time.perf_counter()
    if kind == 'flow' and text.strip().startswith('{'):
        lab, score, ev = _flow_json(text)
    else:
        lab, score, ev = detect.classify_any(kind, text)
    if kind == 'url':
        ev = _promote_link_signals(ev)
    # A cleared item must not show the threat phrase the detector overruled.
    if lab == 0:
        ev = llm.benign_evidence(kind, text, ev, lab)
    ms = (time.perf_counter() - t0) * 1000
    actions = llm.actions_for(kind, lab, text)
    scam = llm.scam_type(kind, text, lab)
    _last.clear(); _last.update(kind=kind, text=text, lab=lab, ev=ev)
    out = {'verdict': VERDICT[lab], 'level': {1: 'danger', 'uncertain': 'warn', 0: 'clear'}[lab],
           'score': score, 'scam_type': scam, 'evidence': ev,
           'actions': actions, 'actions_hi': _actions_hi(actions),
           'buttons': _HINDI['buttons'], 'detector_ms': ms}
    report = _report_buttons(kind, lab, scam, actions)
    if report:
        out['report_buttons'] = report
    return json.dumps(out, ensure_ascii=False)


def explain(runner):
    """Stage 2: the on-device Llama explanation for the item from the last verdict() call."""
    ex = BridgeExplainer(runner)
    text, stats = ex.generate(ex.prompt(_last['kind'], _last['text'], _last['lab'], _last['ev']))
    return json.dumps({'explanation': text, 'llm': stats}, ensure_ascii=False)


def check(kind, text, runner):
    """Both stages in one call (tests and the command line)."""
    out = json.loads(verdict(kind, text))
    out.update(json.loads(explain(runner)))
    return json.dumps(out, ensure_ascii=False)
