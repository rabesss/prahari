#!/usr/bin/env python3
"""Human-read check for the Llama explainer: one line + commentary per hand-written case.

    ../../.venv/bin/python tests/read_explain.py [--only sms,flow] [--limit N]

Cases in tests/explain_cases.jsonl are written by hand (not copied from any training or hidden
set) and carry the verdict and concepts a human reader should expect. Output is printed for
reading, and the aggregate check rates use the proxy scorer's own check functions
(../../eval/run_eval.py) with our required_mentions, so a prompt change can be compared
before spending an eval run. This is a local proxy only; hidden E is the authority.
"""
import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

CAND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CAND))

from triage import detect  # noqa: E402
from triage.llm import Explainer, actions_for  # noqa: E402

VERDICT = {1: "malicious", 0: "benign", "uncertain": "uncertain"}
_spec = importlib.util.spec_from_file_location("run_eval", CAND.parents[1] / "eval" / "run_eval.py")
_scorer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_scorer)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default=str(CAND.parents[0] / "BEST" / "tests" / "explain_cases.jsonl"))
    ap.add_argument("--only", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="/var/tmp/kavach-explain-read.jsonl")
    a = ap.parse_args()
    rows = [json.loads(l) for l in Path(a.cases).read_text(encoding="utf-8").splitlines() if l.strip()]
    if a.only:
        want = {s.strip() for s in a.only.split(",")}
        rows = [r for r in rows if r["kind"] in want]
    if a.limit:
        rows = rows[: a.limit]
    ex = Explainer()
    tot = {k: 0.0 for k in _scorer.W["E"]}
    good = 0
    wall = 0.0
    ptok = gtok = 0
    out = []
    for r in rows:
        lab, score, ev = detect.classify_any(r["kind"], r["input"])
        t0 = time.time()
        text, stats = ex.generate(ex.prompt(r["kind"], r["input"], lab, ev))
        dt = time.time() - t0
        wall += dt
        ptok += stats.get("prompt_tokens") or 0
        gtok += stats.get("generated_tokens") or 0
        o = {"id": r["id"], "verdict": VERDICT[lab], "score": round(score, 4),
             "explanation": text, "actions": actions_for(r["kind"], lab),
             "evidence_used": ev, "llm": stats}
        item = {"label": r["label"], "required_mentions": r.get("required_mentions", []),
                "forbidden": r.get("forbidden", []), "input": r["input"]}
        total, checks, ok = _scorer.explain_checks(item, o)
        good += bool(ok)
        for k in tot:
            tot[k] += checks[k]
        out.append({"case": r["id"], "expected": r["label"], "total": round(total, 3), **o,
                    "checks": checks})
        mark = "OK " if (o["verdict"] == VERDICT[r["label"]] and total > 0.75) else "!! "
        print(f"{mark}{r['id']:<18} {r['kind']:<9} expect={VERDICT[r['label']]:<9} got={o['verdict']:<9} "
              f"score={total:.2f} {dt:4.1f}s words={len(text.split()):2d} "
              f"ptok={stats.get('prompt_tokens')} gtok={stats.get('generated_tokens')}")
        print(f"   {text}")
        if r.get("note"):
            print(f"   note: {r['note']}")
    n = max(1, len(rows))
    print(f"\n{len(rows)} cases, {wall:.1f}s total, {wall / n:.2f}s/item, "
          f"{ptok / n:.0f} prompt tokens, {gtok / n:.0f} generated, valid {good}/{len(rows)}")
    print("check rates: " + ", ".join(f"{k}={tot[k] / n:.3f}" for k in tot))
    Path(a.out).write_text("\n".join(json.dumps(o, ensure_ascii=False) for o in out) + "\n", encoding="utf-8")
    print(f"outputs: {a.out}")


if __name__ == "__main__":
    main()
