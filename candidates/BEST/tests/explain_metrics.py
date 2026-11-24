#!/usr/bin/env python3
"""Per-item explanation metrics for a development set (not a test; needs the model).

    $HC_PY tests/explain_metrics.py --cases CASES.jsonl --out OUT.jsonl [--cand DIR]

CASES rows: {id, kind, input, label (0/1), required_mentions?}. For each item the explainer's
output is scored with the proxy scorer's own functions (../../eval): every E component, the
grounding check, llm_plausible, word count, generated tokens and whether the 40-token cap was hit,
plus the honesty validator's report. --cand runs another candidate directory (e.g. a copy of main)
so before/after use the same harness. Use only development data, never an audit or hidden set.
"""
import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--cases", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--cand", default=str(Path(__file__).resolve().parents[1]))
ap.add_argument("--repo", default=str(Path(__file__).resolve().parents[3]))
a = ap.parse_args()
sys.path.insert(0, a.cand)
from triage import detect, llm  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(Path(path).parent))
    spec.loader.exec_module(mod)
    return mod


scorer = _load("run_eval", Path(a.repo) / "eval" / "run_eval.py")
proxy = _load("proxy_v3", Path(a.repo) / "eval" / "proxy_v3.py")
VERDICT = {1: "malicious", 0: "benign", "uncertain": "uncertain"}
rows = [json.loads(l) for l in Path(a.cases).read_text(encoding="utf-8").splitlines() if l.strip()]
ex = llm.Explainer()
cap = int(ex.cfg.get("max_new_tokens", 40))
out = []
for r in rows:
    lab, score, ev = detect.classify_any(r["kind"], r["input"])
    t0 = time.time()
    try:
        text, stats = ex.generate(ex.prompt(r["kind"], r["input"], lab, ev))
    except ValueError as e:
        text, stats = "", {"error": str(e)}
    wall = (time.time() - t0) * 1000
    o = {"id": r["id"], "verdict": VERDICT[lab], "explanation": text,
         "actions": llm.actions_for(r["kind"], lab, r["input"]), "evidence_used": ev, "llm": stats}
    item = {"label": r["label"], "required_mentions": r.get("required_mentions", []),
            "forbidden": r.get("forbidden", []), "input": r["input"]}
    total, checks, valid = scorer.explain_checks(item, o)
    o.update(kind=r["kind"], input=r["input"], label=r["label"], wall_ms=round(wall, 1),
             e_total=round(total, 4), checks=checks, grounded=bool(proxy.grounding(r["input"], text)),
             plausible=bool(scorer.llm_plausible(o)), words=len(text.split()),
             cap_hit=(stats.get("generated_tokens") or 0) >= cap)
    out.append(o)
    print(f"{r['id']:<14} {o['verdict']:<9} E={total:.2f} g={int(o['grounded'])} p={int(o['plausible'])} "
          f"w={o['words']:2d} gt={stats.get('generated_tokens')} {wall:5.0f}ms "
          f"{(stats.get('validator') or {}).get('dropped', '')}\n   {text}", flush=True)
Path(a.out).write_text("\n".join(json.dumps(o, ensure_ascii=False) for o in out) + "\n", encoding="utf-8")
n = max(1, len(out))
print(f"\n{len(out)} items  E={sum(o['e_total'] for o in out) / n:.3f}  grounded={sum(o['grounded'] for o in out)}"
      f"  plausible={sum(o['plausible'] for o in out)}  cap_hit={sum(o['cap_hit'] for o in out)}"
      f"  mean_wall_ms={sum(o['wall_ms'] for o in out) / n:.0f}")
