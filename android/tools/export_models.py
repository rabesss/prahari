"""Convert the trusted BEST joblib files to portable inference data; run with sklearn 1.9.1."""
import json
import sys
from pathlib import Path
import joblib
import sklearn

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(sys.argv[1])
assert sklearn.__version__ == '1.9.1', sklearn.__version__
OUT.mkdir(parents=True, exist_ok=True)

def vector(v, weights):
    assert v.lowercase and v.sublinear_tf and v.norm == 'l2' and v.strip_accents is None
    assert v.analyzer in ('word', 'char', 'char_wb')
    assert v.token_pattern == r'(?u)\b\w\w+\b' and v.stop_words is None
    return {'analyzer': v.analyzer, 'ngram_range': v.ngram_range,
            'vocab': {term: [float(v.idf_[idx]), float(weights[idx])] for term, idx in v.vocabulary_.items()}}

def linear(vs, lr):
    weights = lr.coef_[0]; offset = 0; parts = []
    for v in vs:
        n = len(v.vocabulary_); parts.append(vector(v, weights[offset:offset+n])); offset += n
    return {'parts': parts, 'intercept': float(lr.intercept_[0]), 'tail': weights[offset:].tolist()}

art = ROOT / 'candidates/BEST/artifacts'
for name in ('sms', 'url', 'indic', 'flow'):
    obj = joblib.load(art / (name + '.joblib'))
    if name == 'indic':
        out = linear([obj['char'], obj['word']], obj['lr'])
        out.update(mean=obj['mean'].tolist(), scale=obj['scale'].tolist())
    elif name == 'flow':
        m = obj['model']; cats = list(obj['cats']); encoder = m._preprocessor.named_transformers_['encoder']
        columns = cats + [c for c in obj['columns'] if c not in cats]
        trees = []
        for iteration in m._predictors:
            assert len(iteration) == 1
            p = iteration[0]
            nodes = [[float(n['value']), int(n['feature_idx']), float(n['num_threshold']), int(n['missing_go_to_left']), int(n['left']), int(n['right']), int(n['is_leaf']), int(n['is_categorical']), int(n['bitset_idx'])] for n in p.nodes]
            trees.append({'nodes': nodes, 'bitsets': p.raw_left_cat_bitsets.tolist()})
        out = {'columns': columns, 'cats': dict(zip(cats, [c.tolist() for c in encoder.categories_])),
               'baseline': float(m._baseline_prediction[0, 0]), 'trees': trees}
    else:
        v = obj.steps[0][1]; vs = [x[1] for x in v.transformer_list] if name == 'sms' else [v]
        out = linear(vs, obj.steps[-1][1])
    (OUT / (name + '.json')).write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':'), allow_nan=False))
