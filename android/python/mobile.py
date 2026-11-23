"""Android adapter. The reference triage package is copied unchanged at build time."""
import json
import re
import sys
import time
import types
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
    ms = (time.perf_counter() - t0) * 1000
    _last.clear(); _last.update(kind=kind, text=text, lab=lab, ev=ev)
    return json.dumps({'verdict': VERDICT[lab], 'level': {1: 'danger', 'uncertain': 'warn', 0: 'clear'}[lab],
                       'score': score, 'scam_type': llm.scam_type(kind, text, lab), 'evidence': ev,
                       'actions': llm.actions_for(kind, lab, text), 'detector_ms': ms}, ensure_ascii=False)


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
