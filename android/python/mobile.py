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

def check(kind, text, runner):
    t0 = time.perf_counter()
    if kind == 'flow' and text.strip().startswith('{'):
        f = json.loads(text); p = portable.flow_probability(f); ev = []
        if f.get('num_failed_logins', 0) > 0: ev.append('failed login attempts recorded on the connection'); p = max(p, .9)
        if f.get('wrong_fragment', 0) > 0: ev.append('malformed packet fragments, typical of a teardrop or pod flood'); p = max(p, .9)
        if f.get('land', 0) > 0: ev.append('source and destination are the same host and port'); p = max(p, .9)
        if f.get('serror_rate', 0) > .5: ev.append('most connections were half-open (SYN errors)')
        if f.get('num_failed_logins', 0) > 0: ev.append(f"{int(f['num_failed_logins'])} failed logins")
        if f.get('dst_host_diff_srv_rate', 0) > .5: ev.append('the host contacted many different services')
        if f.get('root_shell', 0) > 0: ev.append('a root shell was obtained')
        lab, score = (1 if p >= .1 else 0), p
    else: lab, score, ev = detect.classify_any(kind, text)
    detector_ms = (time.perf_counter()-t0)*1000
    ex = BridgeExplainer(runner)
    explanation, stats = ex.generate(ex.prompt(kind, text, lab, ev))
    return json.dumps({'verdict': {0:'NO RISK FOUND — still verify',1:'DANGEROUS','uncertain':'SUSPICIOUS'}[lab], 'score':score, 'evidence':ev, 'explanation':explanation, 'actions':llm.actions_for(kind, lab), 'detector_ms':detector_ms, 'llm':stats}, ensure_ascii=False)
