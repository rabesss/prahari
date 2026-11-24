#!/usr/bin/env python3
"""Validation gate: score the detector on every holdout set, then run the test suites.

    bin/validate [--candidate DIR] [--json OUT] [--baseline BEFORE.json] [--no-tests]
                 [--only NAME,...] [--errors NAME,...] [--sealed]

Sets (uncertain counts as an error: a false alarm on genuine, a miss on a scam):
- committed: fp_val_v1 (blind validation), india_dev_v2, the stress suites and r4_injection;
- local, not committed (paths from the env vars below, SHA-256 checked, skipped when absent):
  v3_test (India v3 held-back split), v4_tune, v4_test (v4 held-back split, integrator copy);
- sealed final holdout only with --sealed (protocol: scored once per frozen candidate, never
  tuned on; aggregates only).

Per-item errors are printed only for sets named in --errors, and never for held-back or sealed
sets. With --baseline, the gate fails when recall drops on any set or FPR rises on any set
compared with the stored run (the rule from research/fpfix/README.md and the holdout protocol).

Env: HC_PY (interpreter), PRAHARI_V3_DIR (default /var/tmp/prahari-devv3),
PRAHARI_V4_DIR (default /var/tmp/prahari-devv4), PRAHARI_V4_TEST
(default $PRAHARI_V4_DIR/controller-only/v4_test.jsonl), PRAHARI_SEALED
(default /var/tmp/prahari-final-holdout/india_final_holdout_v1_1.jsonl).
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V3 = Path(os.environ.get("PRAHARI_V3_DIR", "/var/tmp/prahari-devv3"))
V4 = Path(os.environ.get("PRAHARI_V4_DIR", "/var/tmp/prahari-devv4"))
V4_TEST = Path(os.environ.get("PRAHARI_V4_TEST", V4 / "controller-only" / "v4_test.jsonl"))
SEALED = Path(os.environ.get("PRAHARI_SEALED",
                             "/var/tmp/prahari-final-holdout/india_final_holdout_v1_1.jsonl"))
STRESS = ROOT / "research" / "stress"

# name, path, how to score, role, expected SHA-256 (None: committed file, git tracks it)
# how: "routed" = sms rows via predict_text, injection rows via classify_any("injection")
#      (eval/india_v2_runner.py); "sms" = predict_text on every row; "injection" = classify_any.
# role: visible / tune / blind / heldback / sealed. Errors print only for visible, tune and blind.
SETS = [
    ("fp_val_v1", ROOT / "research/fpfix/fp_val_v1/fp_val_v1.jsonl", "routed", "blind",
     "62bdc7bb3ba0ff85adb91fd9a833944a4bda2e42e968463d1c39e0cd56d106f5"),
    ("india_dev_v2", ROOT / "bench/dev/india_dev_v2.jsonl", "routed", "visible", None),
    ("v3_test", V3 / "v3_test.jsonl", "sms", "heldback",
     "f2ede552fb03bd95548975500ab91b3cef2dd8d0152272c63204432347692f1a"),
    ("v3_tune", V3 / "v3_tune.jsonl", "sms", "tune",
     "af8d5b0bfafc00f5c6f295ada865510304f49094aec37912d474488f69c0bb69"),
    ("v4_tune", V4 / "v4_tune.jsonl", "sms", "tune",
     "a45e6beeadda1860a719e6c05af944584437016713ccbfe8a5f56920318543b7"),
    ("v4_test", V4_TEST, "sms", "heldback",
     "a1e7cef790f9556b1785412a53a7bc0214e5d0f30bfe8913747bb4e47f068efc"),
    ("stress_protective", STRESS / "protective.jsonl", "sms", "visible", None),
    ("stress_hi_mix", STRESS / "hi_mix.jsonl", "sms", "visible", None),
    ("stress_mixed", STRESS / "mixed.jsonl", "sms", "visible", None),
    ("stress_r3_mech", STRESS / "r3_mech.jsonl", "sms", "visible", None),
    ("stress_r4_sms", STRESS / "r4_sms.jsonl", "sms", "visible", None),
    ("r4_injection", STRESS / "r4_injection.jsonl", "injection", "visible", None),
]
SEALED_SET = ("sealed_v1_1", SEALED, "routed", "sealed",
              "b206052bc857f97e81b56caa9a53af45768ecc917e5973a060bdd7ad73a1b648")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            r["y"] = 1 if r["label"] in (1, "1", "malicious") else 0
            rows.append(r)
    return rows


def metrics(pairs):
    tp = sum(1 for y, p in pairs if y == 1 and p == 1)
    fn = sum(1 for y, p in pairs if y == 1 and p != 1)
    fp = sum(1 for y, p in pairs if y == 0 and p != 0)
    tn = sum(1 for y, p in pairs if y == 0 and p == 0)
    unc = sum(1 for _, p in pairs if p == "uncertain")
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else None
    f1 = 2 * prec * rec / (prec + rec) if rec and prec + rec else (0.0 if rec is not None else None)
    fpr = fp / (fp + tn) if fp + tn else None
    r4 = lambda v: None if v is None else round(v, 4)  # noqa: E731
    return dict(n=len(pairs), tp=tp, fp=fp, tn=tn, fn=fn, uncertain=unc,
                fpr=r4(fpr), recall=r4(rec), f1=r4(f1))


def predict(rows, how):
    from triage.detect import classify_any, predict_text
    out = [None] * len(rows)
    sms_idx = [i for i, r in enumerate(rows)
               if how == "sms" or (how == "routed" and r.get("route", "sms") == "sms")]
    if sms_idx:
        for i, res in zip(sms_idx, predict_text([rows[i]["text"] for i in sms_idx]), strict=True):
            out[i] = res
    for i, r in enumerate(rows):
        if out[i] is None:
            out[i] = classify_any("injection", r["text"])
    return out


def score_sets(cand, sets, errors_for):
    sys.path.insert(0, str(cand))
    results = {}
    for name, path, how, role, want in sets:
        if not path.exists():
            results[name] = {"status": "missing", "role": role}
            continue
        if want and sha256(path) != want:
            results[name] = {"status": "sha256 mismatch", "role": role}
            continue
        rows = load(path)
        preds = predict(rows, how)
        res = {"status": "ok", "role": role, **metrics([(r["y"], p[0]) for r, p in zip(rows, preds)])}
        routes = {r.get("route") for r in rows if r.get("route")}
        if how == "routed" and len(routes) > 1:
            res["by_route"] = {rt: metrics([(r["y"], p[0]) for r, p in zip(rows, preds)
                                            if r.get("route") == rt]) for rt in sorted(routes)}
        results[name] = res
        if name in errors_for:
            if role in ("heldback", "sealed"):
                print(f"  (errors withheld for {role} set {name})")
                continue
            for r, (lab, s, ev) in zip(rows, preds):
                if (r["y"] == 1 and lab != 1) or (r["y"] == 0 and lab != 0):
                    kind = "FP" if r["y"] == 0 else "FN"
                    print(f"  {name} {kind} {r.get('id', '?')} {r.get('category', '')} pred={lab} "
                          f"s={float(s):.2f} ev={list(ev)[:2]}\n     {r['text'][:220]}")
    return results


def fmt(v):
    return "  -  " if v is None else f"{v:.3f}"


def print_table(results, base=None):
    print(f"{'set':<18} {'role':<8} {'n':>4} {'FPR':>6} {'recall':>6} {'F1':>6}  TP/FP/TN/FN unc"
          + ("   | before FPR/recall/F1" if base else ""))
    for name, r in results.items():
        if r["status"] != "ok":
            print(f"{name:<18} {r['role']:<8} {r['status']}")
            continue
        line = (f"{name:<18} {r['role']:<8} {r['n']:>4} {fmt(r['fpr']):>6} {fmt(r['recall']):>6} "
                f"{fmt(r['f1']):>6}  {r['tp']}/{r['fp']}/{r['tn']}/{r['fn']} {r['uncertain']}")
        b = (base or {}).get(name)
        if b and b.get("status") == "ok":
            line += f"   | {fmt(b['fpr'])}/{fmt(b['recall'])}/{fmt(b['f1'])}"
        print(line)
        for rt, m in r.get("by_route", {}).items():
            print(f"  route={rt:<10} {'':<6} {m['n']:>4} {fmt(m['fpr']):>6} {fmt(m['recall']):>6} "
                  f"{fmt(m['f1']):>6}  {m['tp']}/{m['fp']}/{m['tn']}/{m['fn']} {m['uncertain']}")


def regressions(results, base):
    bad = []
    for name, r in results.items():
        b = base.get(name)
        if r.get("status") != "ok" or not b or b.get("status") != "ok":
            continue
        if r["recall"] is not None and b["recall"] is not None and r["recall"] < b["recall"]:
            bad.append(f"{name}: recall {b['recall']} -> {r['recall']}")
        if r["fpr"] is not None and b["fpr"] is not None and r["fpr"] > b["fpr"]:
            bad.append(f"{name}: FPR {b['fpr']} -> {r['fpr']}")
    return bad


TESTS = [
    ["-m", "pytest", "-q", "candidates/BEST/tests"],
    ["bench/gate.py"],
    ["bench/stress.py"],
    ["eval/test_scorer.py"],
    ["-m", "pytest", "-q", "eval/test_conventional.py", "eval/test_india_challenge.py",
     "eval/test_proxy_v3.py", "eval/test_compare_v3.py", "eval/test_validate.py"],
    ["-m", "pytest", "-q", "bench/tests"],
]


# The bench gates time the predictor with GNU time; without it they cannot run here (CI has it).
NEEDS_TIME = {"bench/gate.py", "bench/stress.py", "bench/tests"}


def run_tests(py):
    failed = []
    for args in TESTS:
        if not Path("/usr/bin/time").exists() and NEEDS_TIME & set(args):
            print(f"SKIP  {' '.join(args)}  (needs /usr/bin/time; CI runs it)")
            continue
        p = subprocess.run([py, *args], cwd=ROOT, capture_output=True, text=True)
        tail = (p.stdout + p.stderr).strip().splitlines()[-1:] or [""]
        print(f"{'PASS' if p.returncode == 0 else 'FAIL'}  {' '.join(args)}  {tail[0][:120]}")
        if p.returncode:
            failed.append(" ".join(args))
            print((p.stdout + p.stderr)[-3000:])
    return failed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--candidate", default=str(ROOT / "candidates" / "BEST"))
    ap.add_argument("--json", type=Path, help="write the set results here (outside the repository)")
    ap.add_argument("--baseline", type=Path, help="a --json file from an earlier run to compare with")
    ap.add_argument("--no-tests", action="store_true")
    ap.add_argument("--only", default="", help="comma-separated set names")
    ap.add_argument("--errors", default="", help="print per-item errors for these sets")
    ap.add_argument("--sealed", action="store_true",
                    help="also score the sealed final holdout (once per frozen candidate)")
    a = ap.parse_args(argv)
    sets = list(SETS) + ([SEALED_SET] if a.sealed else [])
    if a.only:
        want = {s.strip() for s in a.only.split(",")}
        sets = [s for s in sets if s[0] in want]
    if a.sealed:
        print("NOTE: sealed holdout scored; record this use in research/LOG.md. No tuning on it.")
    cand = Path(a.candidate).resolve()
    results = score_sets(cand, sets, {s.strip() for s in a.errors.split(",") if s.strip()})
    base = json.loads(a.baseline.read_text())["sets"] if a.baseline else None
    print_table(results, base)
    rc = 0
    if a.json:
        if a.json.resolve().is_relative_to(ROOT):
            sys.exit("--json must be outside the repository")
        a.json.parent.mkdir(parents=True, exist_ok=True)
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True).stdout.strip()
        a.json.write_text(json.dumps({"head": head, "candidate": cand.name, "sets": results},
                                     indent=1) + "\n")
    if base:
        bad = regressions(results, base)
        for b in bad:
            print("REGRESSION", b)
        rc |= bool(bad)
    if not a.no_tests:
        rc |= bool(run_tests(os.environ.get("HC_PY", sys.executable)))
    missing = [n for n, r in results.items() if r["status"] != "ok"]
    if missing:
        print("not scored:", ", ".join(missing))
    print("GATE", "FAIL" if rc else "PASS")
    return 1 if rc else 0


if __name__ == "__main__":
    sys.exit(main())
