"""Compare real reference artifacts and portable models on visible examples."""
import ast
import json
import sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'candidates/BEST'), str(ROOT/'android/python')]
from triage import detect, textmodel
import portable
portable.ROOT = Path(sys.argv[1])

def rows(name):
    return [json.loads(x)['input'] for x in (ROOT/'bench/fixtures'/f'{name}.jsonl').read_text().splitlines() if x.strip()]
sms, urls, flows = rows('sms'), rows('url'), rows('flow')
# Include the literal input strings from the visible test module, including Unicode cases.
tree = ast.parse((ROOT/'candidates/BEST/tests/test_basic.py').read_text())
for n in ast.walk(tree):
    if isinstance(n, ast.Constant) and isinstance(n.value, str) and len(n.value) > 20:
        (urls if n.value.startswith(('http://', 'https://')) else sms).append(n.value)

for name, samples in [('sms', sms), ('url', urls), ('indic', sms)]:
    if name == 'indic': ref = textmodel.prob(detect.indic_model(), samples)
    else: ref = detect._model(name).predict_proba([x.lower() for x in samples] if name == 'url' else samples)[:, 1]
    actual = [portable.probability(name, x) for x in samples]
    np.testing.assert_allclose(actual, ref, rtol=0, atol=1e-6, err_msg=name)
    print(name, len(samples), 'maximum probability error', max(abs(a-b) for a,b in zip(actual, ref)))
ref_raw = detect._model('flow')['model'].predict_proba(detect.flow_matrix(flows, detect._model('flow')['cats'])[detect._model('flow')['columns']])[:,1]
actual_raw = [portable.flow_probability(f) for f in flows]
np.testing.assert_allclose(actual_raw, ref_raw, rtol=0, atol=1e-6, err_msg='flow')
print('flow', len(flows), 'maximum probability error', max(abs(a-b) for a,b in zip(actual_raw, ref_raw)))
ref_sms = detect.predict_text(sms); ref_url = detect.predict_url(urls); ref_flow = detect.predict_flow(flows)
import mobile
for name, samples, expected in [('sms',sms,ref_sms),('url',urls,ref_url)]:
    actual = detect.predict_text(samples) if name=='sms' else detect.predict_url(samples)
    for i,(a,b) in enumerate(zip(actual,expected)):
        assert a[0] == b[0], (name,i,a,b)
        assert abs(a[1]-b[1]) <= 1e-6, (name,i,a,b)
# Exercise the Android feature-record path, which must pass its verdict to the explainer.
class Fake:
    def generate(self, prompt):
        self.prompt = prompt
        return json.dumps({'text':'This network event is DANGEROUS.','stats':{}})
for f, expected in zip(flows, ref_flow):
    fake=Fake(); got=json.loads(mobile.check('flow',json.dumps(f),fake))
    assert got['verdict'] == {0:'SAFE',1:'DANGEROUS','uncertain':'SUSPICIOUS'}[expected[0]]
    assert abs(got['score']-expected[1]) <= 1e-6
    assert ('Verdict: ' + got['verdict']) in fake.prompt
print('all fixture verdicts and scores match')
