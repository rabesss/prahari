"""Entry points for bin/predict and bin/explain (contract in the project AGENTS.md)."""
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
    else:
        res = detect.predict_flow([r["features"] for r in rows])
    write_jsonl(a.out, [{"id": r["id"], "label": lab, "score": round(s, 4), "evidence": ev}
                        for r, (lab, s, ev) in zip(rows, res)])


def cmd_explain(a):
    from .llm import Explainer, actions_for
    rows = read_jsonl(a.inp)
    ex = Explainer()
    out = []
    for r in rows:
        t0 = time.time()
        kind, inp = r["kind"], r["input"]
        lab, score, ev = detect.classify_any(kind, inp)
        text, stats = ex.generate(ex.prompt(kind, inp, lab, ev))
        out.append({"id": r["id"], "verdict": VERDICT[lab], "score": round(score, 4),
                    "explanation": text, "actions": actions_for(kind, lab), "evidence_used": ev,
                    "llm": stats, "latency_ms": round((time.time() - t0) * 1000, 1)})
        write_jsonl(a.out, out)  # incremental, so a timeout keeps partial results
    write_jsonl(a.out, out)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="triage")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("predict")
    p.add_argument("--task", choices=["sms", "url", "flow"], required=True)
    p.add_argument("--in", dest="inp", required=True)
    p.add_argument("--out", required=True)
    e = sub.add_parser("explain")
    e.add_argument("--in", dest="inp", required=True)
    e.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    {"predict": cmd_predict, "explain": cmd_explain}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
