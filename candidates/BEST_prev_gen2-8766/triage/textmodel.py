"""The Indic-context text model: character/word n-grams plus mechanism features.

Trained on the visible Indian set, the seed set and the English SMS corpus. Character n-grams
(features on character sequences, not words) let a word the model has never seen still match on
shared spelling, which matters for Hinglish and for Hindi written in Devanagari; the mechanism
vector tells the model what a message asks the reader to do, independent of wording. Domain and
case-reference numbers are normalised away so the model cannot learn the generator's scaffolding.
"""
import re

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from . import mech

REF_RE = re.compile(r"\b(?:ref|reference|case|ticket|संदर्भ|सन्दर्भ)\s*[:#-]?\s*[a-z]{0,3}[- ]?\d{1,4}"
                    r"(?:[-/]\d{1,4})?\b", re.I)
MECH_NAMES = ["secret", "pay_to_receive", "pay_unverified", "collect", "remote", "crypto", "authority",
              "threat", "job_upfront", "prize_claim", "safe_account", "fee", "official_channel", "receipt",
              "otp_note", "protective", "notice", "promo", "official_host"]


def normalize(text):
    s = mech.clean(text).lower()
    s = REF_RE.sub(" ", s)
    s = mech.URL_RE.sub(" url ", s)
    return re.sub(r"\s+", " ", s).strip()


def numbers(text):
    a = mech.analyze(text)
    v = [1.0 if a[k] else 0.0 for k in MECH_NAMES]
    v.append(min(3.0, len(a["risky"])))
    if text:
        n = sum(1 for c in text if "\u0900" <= c <= "\u097F")
        letters = sum(1 for c in text if c.isalpha())
        v.append(n / max(1, letters))
        v.append(min(1.0, np.log1p(sum(c.isdigit() for c in text)) / 4.0))
    else:
        v += [0.0, 0.0]
    return v


def fit(texts, labels, sample_weight=None, C=8.0, max_features=120000):
    nt = [normalize(t) for t in texts]
    char = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=1, sublinear_tf=True,
                           max_features=max_features)
    word = TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=1, sublinear_tf=True,
                           max_features=max_features)
    parts = [char.fit_transform(nt), word.fit_transform(nt)]
    m = np.array([numbers(t) for t in texts], dtype=float)
    mean, scale = m.mean(0), m.std(0)
    scale[scale == 0] = 1.0
    parts.append(sparse.csr_matrix((m - mean) / scale))
    lr = LogisticRegression(C=C, max_iter=4000, class_weight="balanced")
    lr.fit(sparse.hstack(parts).tocsr(), labels, sample_weight=sample_weight)
    return {"char": char, "word": word, "lr": lr, "mean": mean, "scale": scale}


def prob(bundle, texts):
    nt = [normalize(t) for t in texts]
    parts = [bundle["char"].transform(nt), bundle["word"].transform(nt)]
    m = np.array([numbers(t) for t in texts], dtype=float)
    parts.append(sparse.csr_matrix((m - bundle["mean"]) / bundle["scale"]))
    return bundle["lr"].predict_proba(sparse.hstack(parts).tocsr())[:, 1]
