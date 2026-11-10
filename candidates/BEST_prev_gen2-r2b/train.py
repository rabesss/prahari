#!/usr/bin/env python3
"""Train the classical detectors from the visible data (../../data/train). Writes artifacts/*.joblib.

Usage (from the candidate dir):  ../../.venv/bin/python train.py
"""
import json
import sys
from pathlib import Path

import joblib
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.pipeline import make_pipeline, make_union

HERE = Path(__file__).resolve().parent
DATA = HERE.parents[1] / "data"
ART = HERE / "artifacts"
sys.path.insert(0, str(HERE))
from triage.detect import FLOW_CAT, flow_matrix  # noqa: E402


def load(split, name):
    with open(DATA / split / f"{name}.jsonl", encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def text_model():
    return make_pipeline(
        make_union(TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=2, sublinear_tf=True, max_features=150000),
                   TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=2, sublinear_tf=True, lowercase=True)),
        LogisticRegression(C=8, max_iter=3000, class_weight="balanced"))


def main():
    ART.mkdir(exist_ok=True)
    tr, dv = load("train", "sms"), load("dev", "sms")
    m = text_model().fit([r["text"] for r in tr], [r["label"] for r in tr])
    print("sms dev F1", round(f1_score([r["label"] for r in dv], m.predict([r["text"] for r in dv])), 4))
    if (DATA / "dev" / "indic.jsonl").exists():
        ind = load("dev", "indic")
        print("indic dev F1", round(f1_score([r["label"] for r in ind], m.predict([r["text"] for r in ind])), 4))
    joblib.dump(m, ART / "sms.joblib", compress=3)

    tr, dv = load("train", "url"), load("dev", "url")
    u = make_pipeline(TfidfVectorizer(analyzer="char", ngram_range=(3, 5), min_df=3, sublinear_tf=True, max_features=200000),
                      LogisticRegression(C=4, max_iter=3000))
    u.fit([r["url"].lower() for r in tr], [r["label"] for r in tr])
    print("url dev F1", round(f1_score([r["label"] for r in dv], u.predict([r["url"].lower() for r in dv])), 4))
    joblib.dump(u, ART / "url.joblib", compress=3)

    tr, dv = load("train", "flow"), load("dev", "flow")
    Xtr = flow_matrix([r["features"] for r in tr])
    cats = {c: list(Xtr[c].cat.categories) for c in FLOW_CAT}
    cols = list(Xtr.columns)
    g = HistGradientBoostingClassifier(max_iter=200, categorical_features="from_dtype", random_state=0)
    g.fit(Xtr, [r["label"] for r in tr])
    Xdv = flow_matrix([r["features"] for r in dv], cats)[cols]
    print("flow dev F1", round(f1_score([r["label"] for r in dv], g.predict(Xdv)), 4))
    joblib.dump({"model": g, "cats": cats, "columns": cols}, ART / "flow.joblib", compress=3)


if __name__ == "__main__":
    main()
