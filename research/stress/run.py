#!/usr/bin/env python3
"""Score the candidate detector on the blinded paraphrase suites in this directory.

The JSONL rows are plain {id, label, text}. Run from the repo root:
    .venv/bin/python research/stress/run.py [path/to/candidate]
Default candidate is candidates/gen2.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAND = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "candidates" / "gen2"
sys.path.insert(0, str(CAND))
from triage import detect  # noqa: E402

SUITES = ("protective.jsonl", "hi_mix.jsonl", "mixed.jsonl")
for name in SUITES:
    rows = [json.loads(l) for l in open(Path(__file__).parent / name, encoding="utf-8") if l.strip()]
    res = detect.predict_text([r["text"] for r in rows])
    tp = fp = tn = fn = 0
    wrong = []
    for r, (lab, _, _) in zip(rows, res):
        want, got = bool(r["label"]), lab == 1
        if want and got:
            tp += 1
        elif want:
            fn += 1
            wrong.append(r["id"])
        elif got:
            fp += 1
            wrong.append(r["id"])
        else:
            tn += 1
    print(f"{name:20s} F1={2 * tp / max(1, 2 * tp + fp + fn):.4f} "
          f"recall={tp}/{tp + fn} false_pos={fp}/{fp + tn} wrong={wrong}")
