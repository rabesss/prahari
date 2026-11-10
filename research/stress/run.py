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
    tp = fp = tn = fn = un_pos = un_ben = 0
    wrong = []
    for r, (lab, _, _) in zip(rows, res):
        want = bool(r["label"])
        if want:
            if lab == 1:
                tp += 1
            else:
                fn += 1
                if lab == "uncertain":
                    un_pos += 1
                wrong.append(r["id"])
        else:
            if lab == 0:
                tn += 1
            elif lab == 1:
                fp += 1
                wrong.append(r["id"])
            else:
                # README: "uncertain" is a wrong answer on benign rows too, but it is not a
                # false alarm; keep it out of fp and in the benign denominator.
                un_ben += 1
                wrong.append(r["id"])
    benign = fp + tn + un_ben
    print(f"{name:20s} F1={2 * tp / max(1, 2 * tp + fp + fn + un_pos):.4f} "
          f"recall={tp}/{tp + fn + un_pos} false_pos={fp}/{benign} "
          f"uncertain={un_pos + un_ben} wrong={wrong}")
