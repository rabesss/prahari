"""Portable BEST inference. The exported files are generated in CI from trusted joblibs."""
import json
import math
import re
from collections import Counter
from pathlib import Path
import numpy as np
from triage import mech

ROOT = Path(__file__).parent / 'models'
_cache = {}
def model(name):
    if name not in _cache:
        _cache[name] = json.loads((ROOT / (name + '.json')).read_text())
    return _cache[name]

REF_RE = re.compile(r'\b(?:ref|reference|case|ticket|संदर्भ|सन्दर्भ)\s*[:#-]?\s*[a-z]{0,3}[- ]?\d{1,4}(?:[-/]\d{1,4})?\b', re.I)
MECH_NAMES = ['secret','pay_to_receive','pay_unverified','collect','remote','crypto','authority','threat','job_upfront','prize_claim','safe_account','fee','official_channel','receipt','otp_note','protective','notice','promo','official_host']
def normalize(text):
    s = REF_RE.sub(' ', mech.clean(text).lower())
    return re.sub(r'\s+', ' ', mech.URL_RE.sub(' url ', s)).strip()
def numbers(text):
    a = mech.analyze(text)
    v = [float(bool(a[k])) for k in MECH_NAMES] + [min(3., len(a['risky']))]
    if text:
        v += [sum('\u0900' <= c <= '\u097f' for c in text) / max(1, sum(c.isalpha() for c in text)), min(1., np.log1p(sum(c.isdigit() for c in text)) / 4.)]
    else: v += [0., 0.]
    return v

def grams(text, part):
    text = text.lower(); lo, hi = part['ngram_range']; mode = part['analyzer']
    if mode == 'word':
        words = re.findall(r'(?u)\b\w\w+\b', text)
        for n in range(lo, min(hi, len(words)) + 1):
            for i in range(len(words)-n+1): yield ' '.join(words[i:i+n])
    elif mode == 'char':
        text = re.sub(r'\s\s+', ' ', text)
        for n in range(lo, min(hi, len(text)) + 1):
            for i in range(len(text)-n+1): yield text[i:i+n]
    else:
        text = re.sub(r'\s\s+', ' ', text)
        for word in text.split():
            word = ' ' + word + ' '
            for n in range(lo, hi+1):
                offset = 0
                yield word[:n]
                while offset + n < len(word):
                    offset += 1
                    yield word[offset:offset+n]
                if offset == 0: break

def part_score(text, part):
    counts = Counter(grams(text, part)); vocab = part['vocab']; values = []
    for term, count in counts.items():
        if term in vocab:
            idf, weight = vocab[term]; values.append(((1. + math.log(count)) * idf, weight))
    norm = math.sqrt(sum(v*v for v,_ in values))
    return sum(v*w for v,w in values) / norm if norm else 0.
def sigmoid(x):
    return 1. / (1. + math.exp(-x)) if x >= 0 else math.exp(x) / (1. + math.exp(x))
def probability(name, text):
    m = model(name); t = normalize(text) if name == 'indic' else text
    val = m['intercept'] + sum(part_score(t, p) for p in m['parts'])
    if name == 'indic':
        val += float(np.dot((np.asarray(numbers(text)) - np.asarray(m['mean'])) / np.asarray(m['scale']), np.asarray(m['tail'])))
    return sigmoid(val)

def flow_probability(row):
    m = model('flow'); x = []
    for col in m['columns']:
        value = row.get(col)
        if col in m['cats']:
            try: value = m['cats'][col].index(value)
            except ValueError: value = float('nan')
        elif value is None: value = float('nan')
        x.append(float(value))
    val = m['baseline']
    for tree in m['trees']:
        idx = 0
        while True:
            value, feat, threshold, missing_left, left, right, leaf, categorical, bitset = tree['nodes'][idx]
            if leaf: val += value; break
            v = x[feat]
            if math.isnan(v): go_left = missing_left
            elif categorical:
                code = int(v); bits = tree['bitsets'][bitset]
                go_left = code >= 0 and code < 256 and bool(bits[code >> 5] & (1 << (code & 31)))
            else: go_left = v <= threshold
            idx = left if go_left else right
    return sigmoid(val)
