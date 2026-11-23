"""Score the SMS detector (triage.detect.predict_text) on Indian dev / validation sets.

Usage: score.py CANDIDATE_DIR SET [SET ...] [--errors]
SET is NAME=PATH.jsonl; rows need text and label (0/1 or benign/malicious). Rows whose route is
not "sms" are skipped. "uncertain" counts as an error (a false alarm on ham, a miss on a scam).
Prints false-alarm rate, recall, precision and F1 per set and per category.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path


def load(path):
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if r.get("route", "sms") != "sms":
                continue
            r["y"] = 1 if r["label"] in (1, "1", "malicious") else 0
            rows.append(r)
    return rows


def metrics(pairs):
    tp = sum(1 for y, p in pairs if y == 1 and p == 1)
    fn = sum(1 for y, p in pairs if y == 1 and p != 1)
    fp = sum(1 for y, p in pairs if y == 0 and p != 0)
    tn = sum(1 for y, p in pairs if y == 0 and p == 0)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    fpr = fp / (fp + tn) if fp + tn else 0.0
    return dict(n=len(pairs), tp=tp, fp=fp, tn=tn, fn=fn, fpr=fpr, recall=rec, precision=prec, f1=f1)


def main(argv):
    cand = Path(argv[0]).resolve()
    show = "--errors" in argv
    sets = [a.split("=", 1) for a in argv[1:] if not a.startswith("--")]
    sys.path.insert(0, str(cand))
    from triage import detect
    for name, path in sets:
        rows = load(path)
        preds = detect.predict_text([r["text"] for r in rows])
        pairs = [(r["y"], p[0]) for r, p in zip(rows, preds)]
        m = metrics(pairs)
        print(f"{name:12s} n={m['n']:3d} FPR={m['fpr']:.3f} recall={m['recall']:.3f} "
              f"precision={m['precision']:.3f} F1={m['f1']:.3f}  (tp={m['tp']} fp={m['fp']} tn={m['tn']} fn={m['fn']})")
        if show:
            by = defaultdict(list)
            for r, p in zip(rows, preds):
                by[r.get("category", "?")].append((r["y"], p[0]))
            for cat, pr in sorted(by.items()):
                c = metrics(pr)
                print(f"    {cat:28s} n={c['n']:3d} fp={c['fp']} fn={c['fn']}")
            for r, (lab, s, ev) in zip(rows, preds):
                if (r["y"] == 1) != (lab == 1):
                    kind = "FP" if r["y"] == 0 else "FN"
                    print(f"  {kind} {r['id']} {r.get('category')} pred={lab} s={float(s):.2f} ev={ev[:2]}\n     {r['text'][:200]}")


if __name__ == "__main__":
    main(sys.argv[1:])
