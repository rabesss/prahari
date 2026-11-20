#!/usr/bin/env python3
"""Leave-one-category-out on the visible Indian set.

For each observed category, train on the other categories plus the SMS corpus and test the held-out
category. Fixed mechanism rules remain active. Uncertain predictions are reported separately and
mapped to benign for the historical pooled binary F1; this is not a category-average score. Run from the repo root:  .venv/bin/python research/stress/loco.py
"""
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAND = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "candidates" / "gen2"
sys.path.insert(0, str(CAND))

from sklearn.metrics import f1_score  # noqa: E402
from triage import mech, textmodel  # noqa: E402


def load(rel):
    with open(ROOT / "data" / rel, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    rows = load("train/indic.jsonl") + load("train/indic_seed.jsonl") + load("dev/indic.jsonl")
    sms = load("train/sms.jsonl")
    cats = sorted({r["category"] for r in rows if r.get("category")})
    truth, pred = [], []
    uncertain = 0
    for c in cats:
        tr = [r for r in rows if r.get("category") != c]
        te = [r for r in rows if r.get("category") == c]
        m = textmodel.fit([r["text"] for r in tr] + [r["text"] for r in sms],
                          [r["label"] for r in tr] + [r["label"] for r in sms])
        ps = textmodel.prob(m, [r["text"] for r in te])
        tp = fp = tn = fn = 0
        for r, p in zip(te, ps):
            decision = mech.decide(float(p), mech.analyze(r["text"]))[0]
            uncertain += decision == "uncertain"
            lab = 1 if decision == 1 else 0
            truth.append(r["label"])
            pred.append(lab)
            if r["label"] and lab:
                tp += 1
            elif r["label"]:
                fn += 1
            elif lab:
                fp += 1
            else:
                tn += 1
        print(f"{c:22s} recall={tp}/{tp + fn}  false_pos={fp}/{fp + tn}")
    print("pooled binary F1", round(f1_score(truth, pred), 4), "uncertain", uncertain)


if __name__ == "__main__":
    main()
