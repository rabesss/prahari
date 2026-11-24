"""Entry points for bin/predict (task, IN.jsonl -> OUT.jsonl labels) and bin/explain (IN.jsonl -> OUT.jsonl explanations)."""
import argparse
import json
import sys
import time

from . import detect

VERDICT = {1: "malicious", 0: "benign", "uncertain": "uncertain"}


def read_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def write_jsonl(p, rows):
    with open(p, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def cmd_predict(a):
    rows = read_jsonl(a.inp)
    if a.task == "sms":
        res = detect.predict_text([r["text"] for r in rows])
    elif a.task == "url":
        res = detect.predict_url([r["url"] for r in rows])
    elif a.task == "upi":
        res = detect.predict_upi([r.get("upi") or r.get("url") or r.get("input") or r.get("text", "") for r in rows])
    else:
        res = detect.predict_flow([r["features"] for r in rows])
    write_jsonl(a.out, [{"id": r["id"], "label": lab, "score": round(s, 4), "evidence": ev}
                        for r, (lab, s, ev) in zip(rows, res)])


def cmd_explain(a):
    from .explain_hi import summary_hi
    from .llm import Explainer, actions_for, scam_type
    rows = read_jsonl(a.inp)
    ex = Explainer()
    out = []
    for r in rows:
        t0 = time.time()
        kind, inp = r["kind"], r["input"]
        lab, score, ev = detect.classify_any(kind, inp)
        row = {"id": r["id"], "verdict": VERDICT[lab], "score": round(score, 4),
                    "category": scam_type(kind, inp, lab),
                    "actions": actions_for(kind, lab, inp), "evidence_used": ev}
        # Fixed-text Hindi summary from the detector result (not model text; see explain_hi.py).
        try:
            hi = summary_hi(kind, inp, lab, ev)
        except Exception:  # an aid only; a table problem must never stop the explain run
            hi = ""
        if hi:
            row["summary_hi"] = hi
        try:
            text, stats = ex.generate(ex.prompt(kind, inp, lab, ev))
            if not isinstance(text, str) or not text.strip():
                raise ValueError('empty explanation')
            row.update(explanation=text, llm=stats, explanation_status='success')
        except ValueError:
            row.update(explanation_status='failed', explanation_error='Explanation unavailable.')
        row['latency_ms'] = round((time.time() - t0) * 1000, 1)
        out.append(row)
        write_jsonl(a.out, out)  # incremental, so a timeout keeps partial results
    write_jsonl(a.out, out)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="triage")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("predict")
    p.add_argument("--task", choices=["sms", "url", "flow", "upi"], required=True)
    p.add_argument("--in", dest="inp", required=True)
    p.add_argument("--out", required=True)
    e = sub.add_parser("explain")
    e.add_argument("--in", dest="inp", required=True)
    e.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    {"predict": cmd_predict, "explain": cmd_explain}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
