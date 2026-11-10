#!/usr/bin/env python3
"""Proxy evaluator for the Bharat AI-SoC PS3 entry. Called by bin/eval; see research/BRIEF.md for the formula.

Last stdout line is a JSON summary. Per-item details that would reveal hidden test content are written only to
the controller-private dir (/var/tmp/arm-bharat-ai-soc-eval/private/), never under research/evals/.
"""
import argparse
import datetime as dt
import fcntl
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
DATA = Path("/var/tmp/arm-bharat-ai-soc-data")
HIDDEN = DATA / "hidden"
EVROOT = Path("/var/tmp/arm-bharat-ai-soc-eval")
LOCK = EVROOT / "eval.lock"
W = json.loads((PROJ / "eval" / "weights.json").read_text())
REGISTRY = PROJ / "models" / "registry.json"
PY = PROJ / ".venv" / "bin" / "python"

GLOBAL_FORBIDDEN = [r"social security", r"\bssn\b", r"\birs\b", r"zip code", r"medicare", r"\b911\b", r"\bfbi\b",
                    r"\bftc\b", r"as an ai", r"i cannot help", r"i can't help"]
UNSAFE_ACTIONS = [r"click (on )?the link", r"call the number (in|given in) the message", r"share (the |your )?otp",
                  r"reply with", r"\bpay (the|a) (fee|amount)", r"install (the|this) app", r"scan the qr"]
HELPLINE_OK = ["1930", "cybercrime.gov.in", "sancharsaathi.gov.in", "cert-in.org.in", "sachet.rbi.org.in"]
DOMAIN_RE = re.compile(r"(?:https?://)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/\S*)?", re.I)
NUM_RE = re.compile(r"\+?\d[\d\s-]{4,}\d")
REPORT_SECTIONS = ["problem", "architecture", "models", "datasets", "results", "performance", "limitations", "responsible"]


def clip(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def logscale(v, good, bad):
    """1 at v<=good, 0 at v>=bad, log-linear between."""
    if v is None or v <= 0:
        return 0.0
    return clip((math.log(bad) - math.log(v)) / (math.log(bad) - math.log(good)))


def read_jsonl(p):
    try:
        with open(p, encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]
    except (OSError, json.JSONDecodeError):
        return None


def write_jsonl(p, rows):
    with open(p, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def tree_pids(root):
    pids, frontier = {root}, [root]
    while frontier:
        p = frontier.pop()
        try:
            for c in Path(f"/proc/{p}/task/{p}/children").read_text().split():
                c = int(c)
                if c not in pids:
                    pids.add(c)
                    frontier.append(c)
        except OSError:
            pass
    return pids


def run_proc(cmd, env, timeout, cwd, log, watch_pte=None, vis_log=None):
    """Run cmd, sampling peak RSS (VmHWM) of its process tree and whether watch_pte is mapped/open.
    With vis_log, the full output (which can echo hidden inputs) stays in the private `log`; vis_log gets a status
    line plus, on failure, only traceback/error lines."""
    t0 = time.time()
    start = log.stat().st_size if log.exists() else 0
    with open(log, "ab") as lf:
        p = subprocess.Popen(cmd, env=env, cwd=cwd, stdout=lf, stderr=subprocess.STDOUT, start_new_session=True)
        peak_kb, pte_seen, timed_out = 0, False, False
        while p.poll() is None:
            if time.time() - t0 > timeout:
                timed_out = True
                os.killpg(p.pid, signal.SIGKILL)
                break
            for pid in tree_pids(p.pid):
                try:
                    for line in Path(f"/proc/{pid}/status").read_text().splitlines():
                        if line.startswith("VmHWM:"):
                            peak_kb = max(peak_kb, int(line.split()[1]))
                    if watch_pte and not pte_seen:
                        if watch_pte in Path(f"/proc/{pid}/maps").read_text():
                            pte_seen = True
                        else:
                            for fd in Path(f"/proc/{pid}/fd").iterdir():
                                try:
                                    if os.readlink(fd) == watch_pte:
                                        pte_seen = True
                                        break
                                except OSError:
                                    pass
                except OSError:
                    pass
            time.sleep(0.25)
        p.wait()
    res = {"rc": p.returncode, "wall_s": round(time.time() - t0, 3), "peak_rss_mb": round(peak_kb / 1024, 1),
           "pte_seen": pte_seen, "timed_out": timed_out}
    if vis_log is not None:
        with open(vis_log, "a") as vf:
            vf.write(f"== {Path(cmd[0]).name} {' '.join(c for c in cmd[1:3] if c.startswith('--') or len(c) < 8)} "
                     f"rc={res['rc']} timeout={timed_out} wall_s={res['wall_s']} peak_rss_mb={res['peak_rss_mb']}\n")
            if res["rc"] != 0 or timed_out:
                with open(log, "rb") as lf:
                    lf.seek(start)
                    lines = lf.read().decode("utf-8", "replace").splitlines()
                keep = [l for l in lines if re.match(r"(Traceback|  File |\w*(Error|Exception)\b)", l)]
                vf.write("\n".join(l[:160] for l in keep[-25:]) + "\n")
    return res


def norm_label(v):
    if v in (0, 1) and not isinstance(v, bool):
        return v
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("0", "1"):
            return int(s)
        if s == "uncertain":
            return "uncertain"
    return None


def det_metrics(gold, preds):
    tp = fp = tn = fn = 0.0
    bad = 0
    for i, y in gold.items():
        p = norm_label(preds.get(i))
        if p is None:
            bad += 1
            w = 1.0 - y
        else:
            w = 0.5 if p == "uncertain" else float(p)
        if y == 1:
            tp, fn = tp + w, fn + 1 - w
        else:
            fp, tn = fp + w, tn + 1 - w
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    fpr = fp / (fp + tn) if fp + tn else 0.0
    score = f1 * (1 - min(0.5, max(0.0, fpr - 0.01) * 5))
    return {"f1": round(f1, 4), "precision": round(prec, 4), "recall": round(rec, 4), "fpr": round(fpr, 4),
            "invalid": bad, "n": len(gold), "score": round(score, 4)}


NEG_RE = re.compile(r"\b(do not|don't|dont|never|not|avoid|no need to|without)\b")


def unsafe_advice(action):
    """True if an action recommends something unsafe; a negation earlier in the same clause makes it protective."""
    for u in UNSAFE_ACTIONS:
        for m in re.finditer(u, action):
            clause = re.split(r"[.;:!?]|\bbut\b", action[:m.start()])[-1]
            if not NEG_RE.search(clause):
                return True
    return False


# Required concepts: an explanation passes "mention" if it names any required concept by its key phrase or a close
# synonym. Matching is on normalised text (lowercase, punctuation and hyphens -> spaces).
CONCEPTS = {
    "kyc": ["kyc", "know your customer"], "link": ["link", "url"], "upi pin": ["upi pin"],
    "collect request": ["collect request", "collect", "request money", "money request"],
    "threat": ["threat", "threaten", "intimidat", "arrest", "blackmail"],
    "payment": ["payment", "pay money", "transfer money", "send money", "transfer"],
    "deposit": ["deposit", "upfront payment", "pay first", "pay upfront"],
    "job scam": ["job scam", "task scam", "fake job", "job offer"], "task scam": ["task scam", "job scam", "fake job"],
    "otp": ["otp", "one time password", "verification code"], "fee": ["fee", "charge"],
    "share": ["share", "forward", "reveal"], "apk": ["apk", "install an app", "install the app", "app file"],
    "permissions": ["permission"], "official app": ["official app", "bank app", "bank s app", "official number"],
    "pin": ["pin"], "do not share": ["do not share", "don t share", "never share", "not share"],
    "official domain": ["official domain", "official website", "official site", "official government website",
                        "genuine website", "real website", "legitimate website"],
    "no fee": ["no fee", "no charge", "free of charge", "not ask for money", "does not ask for money",
               "doesn t ask for money", "no payment"],
    "lookalike domain": ["lookalike", "look alike", "imitat", "mimic", "spoof", "fake website", "fake site",
                         "fake link", "similar to"],
    "unofficial domain": ["unofficial", "not official", "not the official", "fake website", "fake site", "fake link"],
    "refund": ["refund"], "tracking": ["track"], "orders": ["order"], "reward": ["reward", "prize", "cashback"],
    "failed logins": ["failed login", "login attempt", "failed password", "failed attempt"],
    "brute force": ["brute force", "password guessing", "guessing password", "guess your password"],
    "port scan": ["port scan", "scanning ports", "scans ports", "many ports", "different ports"], "scan": ["scan"],
    "beaconing": ["beacon", "calling home", "call home", "command and control"],
    "periodic": ["periodic", "regular interval", "fixed interval", r"re:every \d+ (?:second|sec|minute|min)"],
    "normal update": ["normal update", "software update", "routine update", "regular update"],
    "expected": ["expected", "normal", "routine"], "release fee": ["release fee", "fee"],
    "injected instruction": ["inject", "hidden instruction", "embedded instruction", "instruction"],
    "cvv": ["cvv", "card details", "card number"], "sim": ["sim"], "customs fee": ["customs"],
    "id details": ["id details", "id proof", "identity", "aadhaar", "pan"],
}
NOUN = r"(?:network|event|text|message|sms|link|url|domain|website|site|flow|traffic|activity|request|offer|email|connection|sender|app|call|alert)"
SUBJ = r"\b(?:it|which|(?:this|that|the)(?:\s+" + NOUN + r"){0,2})"
CLAIM_RE = re.compile(SUBJ + r"\s+(?P<verb>is|are|seems|appears|looks)\s+(?:to be\s+)?(?P<neg>not\s+)?"
                      r"(?:(?:a|an|very|likely|clearly|probably|highly|most likely|definitely|completely)\s+){0,3}"
                      r"(?P<w>scam|fraud|fraudulent|phishing|suspicious|malicious|fake|dangerous|unsafe|"
                      r"safe|legitimate|genuine|harmless|normal|benign|routine|official|real)\b(?!-)")
MAL_CLAIM = {"scam", "fraud", "fraudulent", "phishing", "suspicious", "malicious", "fake", "dangerous", "unsafe"}
CONTRAST_RE = re.compile(r"\b(?:but|however|although|though|yet|except|while)\b")


def nz(text):
    return " " + re.sub(r"[^a-z0-9\u0900-\u097f]+", " ", text.lower()).strip() + " "


def mentions(item, low):
    t = nz(low)
    for m in item.get("required_mentions", []):
        for pat in CONCEPTS.get(m.lower(), [m.lower()]):
            rx = pat[3:] if pat.startswith("re:") else r"\b" + re.escape(nz(pat).strip())
            if re.search(rx, t):
                return True
    return False


def consistent(y, low):
    """Flags an explanation that asserts the opposite of the truth about the input.
    Counted: '<subject> is/are [not] <verdict word>' for both directions, and 'looks/seems/appears <scam word>'.
    Not counted: appearance of benign-ness ('it looks legitimate'), a benign word followed by a contrast in the same
    sentence ('it is official-looking, but ...'), and any wording outside the pattern. One contradiction scores 0
    on this check only (weight E.consistency); it does not zero the whole explanation."""
    for sent in re.split(r"(?<=[.!?;])\s+", low):
        for m in CLAIM_RE.finditer(sent):
            mal_word = m.group("w") in MAL_CLAIM
            if not mal_word and (m.group("verb") not in ("is", "are") or CONTRAST_RE.search(sent[m.end():])):
                continue
            says_mal = mal_word != bool(m.group("neg"))
            if says_mal != (y == 1):
                return 0.0
    return 1.0


def explain_checks(item, out):
    w = W["E"]
    r = {k: 0.0 for k in w}
    if not isinstance(out, dict) or not isinstance(out.get("explanation"), str) or not isinstance(out.get("actions"), list) \
            or out.get("verdict") not in ("malicious", "benign", "uncertain"):
        return 0.0, r, False
    expl = out["explanation"]
    low = expl.lower()
    acts = " ".join(str(a) for a in out["actions"]).lower()
    y = item["label"]
    v = out["verdict"]
    r["verdict"] = 0.3 if v == "uncertain" else float((v == "malicious") == (y == 1))
    r["mention"] = float(mentions(item, low))
    r["consistency"] = consistent(y, low)
    forb = [re.escape(f.lower()) for f in item.get("forbidden", [])] + GLOBAL_FORBIDDEN
    r["forbidden"] = float(not any(re.search(f, low + " " + acts) for f in forb))
    src = item["input"].lower()
    src_digits = re.sub(r"\D", "", src)
    fab = 0
    for m in DOMAIN_RE.findall(low):
        d = re.sub(r"^https?://", "", m).rstrip(".,;:)").split("/")[0]
        if not d or "." not in d or not re.search(r"[a-z]", d.rsplit(".", 1)[-1]):
            continue
        if d in src or any(h in d for h in HELPLINE_OK):
            continue
        fab += 1
    for m in NUM_RE.findall(low):
        dg = re.sub(r"\D", "", m)
        if len(dg) >= 5 and dg not in src_digits:
            fab += 1
    r["fabrication"] = float(fab == 0)
    n_acts = len(out["actions"])
    unsafe = any(unsafe_advice(str(a).lower()) for a in out["actions"])
    if y == 1:
        protective = re.search(r"\b(do not|don't|never|block|report|ignore|delete|avoid)\b", acts)
        r["actions"] = float(n_acts >= 1 and not unsafe and bool(protective))
    else:
        r["actions"] = float(n_acts >= 1 and not unsafe)
    words = len(expl.split())
    r["length"] = 1.0 if 15 <= words <= 90 else 0.5 if 8 <= words <= 130 else 0.0
    total = sum(w[k] * r[k] for k in w)
    return total, r, True


def llm_plausible(out):
    s = out.get("llm") if isinstance(out, dict) else None
    if not isinstance(s, dict) or s.get("backend") != "executorch":
        return False
    g, d = s.get("generated_tokens") or 0, s.get("decode_tps") or 0
    words = len(str(out.get("explanation", "")).split())
    return g >= 5 and 1.0 <= d <= 300 and g >= 0.6 * words


def docs_score(cand):
    parts = []
    readme = cand / "README.md"
    parts.append(float(readme.exists() and len(readme.read_text(errors="ignore").split()) >= 120))
    rep = cand / "REPORT.md"
    txt = rep.read_text(errors="ignore") if rep.exists() else ""
    secs = re.split(r"^##\s+", txt, flags=re.M)[1:]
    found = 0
    for want in REPORT_SECTIONS:
        body = next((s for s in secs if s.lower().startswith(want)), None)
        if body and "todo" not in body.lower() and len(body.split()) >= 40:
            found += 1
    parts.append(found / len(REPORT_SECTIONS))
    data = cand / "DATA.md"
    dt_ = data.read_text(errors="ignore").lower() if data.exists() else ""
    parts.append(float("licen" in dt_ and "llama" in dt_))
    return round(0.25 * parts[0] + 0.5 * parts[1] + 0.25 * parts[2], 4)


def dir_size_gb(p):
    tot = 0
    for root, dirs, files in os.walk(p):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", ".pytest_cache")]
        for f in files:
            try:
                tot += os.lstat(os.path.join(root, f)).st_size
            except OSError:
                pass
    return tot / 1e9


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("--repeats", type=int, default=1, help="repeat the explain stage N times (latency noise)")
    ap.add_argument("--label", default=None)
    ap.add_argument("--quick", action="store_true", help="8 explain items, 1 repeat, not promotable")
    a = ap.parse_args()

    cand = Path(a.candidate).resolve()
    label = re.sub(r"[^A-Za-z0-9_.-]", "_", a.label or cand.name)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    art = PROJ / "research" / "evals" / f"{stamp}-{label}"
    priv = EVROOT / "private" / f"{stamp}-{label}"
    work = EVROOT / "work" / f"{stamp}-{label}"
    for d in (art, priv, work):
        d.mkdir(parents=True, exist_ok=True)
    failures, infra = [], []
    summary = {"label": label, "candidate": str(cand), "stamp": stamp, "artifacts": str(art.relative_to(PROJ)),
               "quick": a.quick}

    def finish(score, scores, extra=None):
        summary.update({"score": round(score, 2), "scores": scores, "failures": failures, "infra_errors": infra})
        summary["promotable"] = (not a.quick) and not failures and not infra
        if extra:
            summary.update(extra)
        (art / "summary.json").write_text(json.dumps(summary, indent=1))
        with open(PROJ / "research" / "evals" / "ledger.jsonl", "a") as f:
            f.write(json.dumps(summary) + "\n")
        with open(PROJ / "research" / "LOG.md", "a") as f:
            f.write(f"- {stamp} `{label}` score={summary['score']} D={scores.get('D')} E={scores.get('E')} "
                    f"P={scores.get('P')} C={scores.get('C')} fail={len(failures)} quick={a.quick}\n")
        shutil.rmtree(work, ignore_errors=True)
        print(json.dumps(summary))
        return 0

    if not (cand / "bin" / "predict").exists() or not (cand / "bin" / "explain").exists():
        failures.append("missing bin/predict or bin/explain")
        return finish(0.0, {})

    # queue: one eval at a time (2 vCPU box; keeps latency numbers honest)
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    lf = open(LOCK, "w")
    tq = time.time()
    fcntl.flock(lf, fcntl.LOCK_EX)
    summary["queued_s"] = round(time.time() - tq, 1)

    env = {k: v for k, v in os.environ.items() if not k.startswith(("BOXD", "SAIL", "OPENAI", "ANTHROPIC", "GH_", "GITHUB"))}
    env.update({
        "PYTHONPATH": str(PROJ / "eval" / "guard"),
        "HC_GUARD_LOG": str(art / "guard.log"),
        "HC_GUARD_DENY_PATHS": f"{HIDDEN}:{DATA / 'indic'}:{EVROOT / 'private'}",
        "HC_MODEL_REGISTRY": str(REGISTRY),
        "HC_PY": str(PY),
        "http_proxy": "http://127.0.0.1:9", "https_proxy": "http://127.0.0.1:9",
        "HTTP_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9", "no_proxy": "127.0.0.1,localhost",
        "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "OMP_NUM_THREADS": env.get("OMP_NUM_THREADS", "2"),
    })
    (art / "guard.log").touch()
    log = art / "run.log"
    scores, details = {}, {}

    # ---------------- D: detection ----------------
    D = {}
    timings = {}
    for task, src, field, ptask in (("sms", "sms_test", "text", "sms"), ("url", "url_test", "url", "url"),
                                     ("indic", "indic_test", "text", "sms"), ("flow", "flow_test", "features", "flow")):
        gold_rows = read_jsonl(HIDDEN / f"{src}.jsonl")
        if not gold_rows:
            infra.append(f"hidden set {src} missing")
            continue
        inp, outp = work / f"{task}.in.jsonl", work / f"{task}.out.jsonl"
        write_jsonl(inp, [{"id": r["id"], field: r[field]} for r in gold_rows])
        res = run_proc([str(cand / "bin" / "predict"), "--task", ptask, "--in", str(inp), "--out", str(outp)],
                       env, 900, cand, priv / "proc.log", vis_log=log)
        timings[task] = res
        preds = {r.get("id"): r.get("label") for r in (read_jsonl(outp) or []) if isinstance(r, dict)}
        if res["rc"] != 0 or res["timed_out"]:
            failures.append(f"predict {task} rc={res['rc']} timeout={res['timed_out']}")
        gold = {r["id"]: r["label"] for r in gold_rows}
        D[task] = det_metrics(gold, preds)
        D[task]["items_per_s"] = round(len(gold) / max(res["wall_s"], 1e-3), 1)
        if D[task]["invalid"] > 0:
            failures.append(f"predict {task}: {D[task]['invalid']} missing/invalid labels")
        if task == "indic":  # breakdowns by group (aggregates only)
            groups = {}
            for r in gold_rows:
                for key in (f"lang:{r.get('lang')}", f"hard:{bool(r.get('hard'))}"):
                    groups.setdefault(key, {})[r["id"]] = r["label"]
            D["indic_breakdown"] = {k: {"n": len(g), "acc": round(sum(
                1.0 if norm_label(preds.get(i)) == y else 0.5 if norm_label(preds.get(i)) == "uncertain" else 0.0
                for i, y in g.items()) / len(g), 3)} for k, g in sorted(groups.items())}
    d_score = sum(W["D"][t] * D[t]["score"] for t in W["D"] if t in D)
    scores["D"] = round(d_score, 4)
    details["detection"] = D

    # ---------------- E: explanation ----------------
    items = read_jsonl(HIDDEN / "explain_set.jsonl") or []
    if not items:
        infra.append("hidden explain_set missing")
    if a.quick:
        items = items[::max(1, len(items) // 8)][:8]
    try:
        cfg = json.loads((cand / "config.json").read_text())
        reg = json.loads(REGISTRY.read_text())
        model = reg[cfg["model"]]
    except (OSError, KeyError, json.JSONDecodeError) as e:
        failures.append(f"config/model registry error: {e}")
        cfg, model = {}, {"pte": "", "family": ""}
    inp = work / "explain.in.jsonl"
    write_jsonl(inp, [{"id": r["id"], "kind": r["kind"], "input": r["input"]} for r in items])
    runs = []
    reps = 1 if a.quick else max(1, a.repeats)
    for k in range(reps):
        outp = work / f"explain.out.{k}.jsonl"
        res = run_proc([str(cand / "bin" / "explain"), "--in", str(inp), "--out", str(outp)],
                       env, 2400, cand, priv / "proc.log", watch_pte=model.get("pte"), vis_log=log)
        res["outputs"] = {r.get("id"): r for r in (read_jsonl(outp) or []) if isinstance(r, dict)}
        runs.append(res)
        if res["rc"] != 0 or res["timed_out"]:
            failures.append(f"explain run {k} rc={res['rc']} timeout={res['timed_out']}")
    outs = runs[0]["outputs"] if runs else {}
    per_item, by_kind, check_tot = [], {}, {k: 0.0 for k in W["E"]}
    e_sum, valid, plausible = 0.0, 0, 0
    for it in items:
        o = outs.get(it["id"])
        tot, r, ok = explain_checks(it, o)
        e_sum += tot
        valid += ok
        plausible += bool(ok and llm_plausible(o))
        for k in check_tot:
            check_tot[k] += r[k]
        by_kind.setdefault(it["kind"], []).append(tot)
        per_item.append({"id": it["id"], "kind": it["kind"], "score": round(tot, 3), "checks": r,
                         "output": o})
    n = max(1, len(items))
    scores["E"] = round(e_sum / n, 4)
    details["explanation"] = {"n": len(items), "valid": valid, "llm_plausible": plausible,
                              "check_rates": {k: round(v / n, 3) for k, v in check_tot.items()},
                              "by_kind": {k: round(sum(v) / len(v), 3) for k, v in by_kind.items()}}
    write_jsonl(priv / "explain_items.jsonl", per_item)
    if valid < len(items):
        failures.append(f"explain: {len(items) - valid} missing/invalid outputs")

    # ---------------- P: performance ----------------
    walls = sorted(r["wall_s"] for r in runs) or [None]
    med_wall = walls[len(walls) // 2]
    lat = med_wall / n if med_wall else None
    rss_gb = max((r["peak_rss_mb"] for r in runs), default=0) / 1024
    det_ms = 1000 * timings["url"]["wall_s"] / max(1, D.get("url", {}).get("n", 1)) if "url" in timings else None
    pte_gb = os.path.getsize(model["pte"]) / 1e9 if model.get("pte") and os.path.exists(model["pte"]) else 0
    size_gb = pte_gb + dir_size_gb(cand)
    P = {"explain_s_per_item": round(lat, 2) if lat else None, "explain_wall_s": walls,
         "peak_rss_gb": round(rss_gb, 3), "detector_ms_per_item": round(det_ms, 3) if det_ms else None,
         "size_gb": round(size_gb, 3)}
    p_parts = {"explain_latency": logscale(lat, 3.0, 15.0),
               "peak_rss": clip((3.0 - rss_gb) / 2.0) if rss_gb > 0 else 0.0,
               "detector_latency": logscale(det_ms, 1.0, 20.0),
               "size": clip((2.0 - size_gb) / 1.2)}
    P["parts"] = {k: round(v, 3) for k, v in p_parts.items()}
    scores["P"] = round(sum(W["P"][k] * p_parts[k] for k in W["P"]), 4)
    details["performance"] = P
    llm_stats = [o.get("llm", {}) for o in outs.values() if isinstance(o, dict)]
    if llm_stats:
        def med(key):
            v = sorted(s.get(key) for s in llm_stats if isinstance(s.get(key), (int, float)))
            return v[len(v) // 2] if v else None
        P["llm_median"] = {k: med(k) for k in ("prompt_tokens", "generated_tokens", "prefill_tps", "decode_tps")}

    # ---------------- C: compliance ----------------
    guard_lines = (art / "guard.log").read_text().splitlines()
    net_viol = [l for l in guard_lines if "NET blocked" in l]
    file_viol = [l for l in guard_lines if "FILE blocked" in l]
    if file_viol:
        failures.append(f"candidate tried to read hidden eval data ({len(file_viol)} attempts)")
    tests = run_proc([str(PY), "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "tests"], env, 600, cand, art / "tests.log") \
        if (cand / "tests").is_dir() else {"rc": 1}
    app = run_proc([str(cand / "bin" / "app"), "--selftest"], env, 300, cand, art / "app.log") \
        if (cand / "bin" / "app").exists() else {"rc": 1}
    gate = {"llama_family": model.get("family") == "llama",
            "executorch_pte_loaded": all(r["pte_seen"] for r in runs) if runs else False,
            "llm_stats_plausible": plausible >= 0.9 * len(items) if items else False}
    gate["pass"] = all(gate.values())
    c_parts = {"offline": float(not net_viol and not file_viol), "tests": float(tests["rc"] == 0),
               "app": float(app["rc"] == 0), "docs": docs_score(cand)}
    scores["C"] = round(sum(W["C"][k] * c_parts[k] for k in W["C"]), 4)
    details["compliance"] = {"gate": gate, "parts": c_parts, "net_violations": len(net_viol),
                             "file_violations": len(file_viol)}
    if not gate["pass"]:
        failures.append(f"compliance gate failed: {gate}")
    if net_viol:
        failures.append(f"network access attempted ({len(net_viol)} attempts)")
    if tests["rc"] != 0:
        failures.append("pytest failed (see tests.log)")
    if app["rc"] != 0:
        failures.append("bin/app --selftest failed (see app.log)")

    total = 100 * sum(W["top"][k] * scores[k] for k in W["top"])
    if not gate["pass"]:
        total = min(total, W["gate_cap"])
    (art / "details.json").write_text(json.dumps(details, indent=1))
    return finish(total, scores, {"headline": {
        "sms_f1": D.get("sms", {}).get("f1"), "url_f1": D.get("url", {}).get("f1"),
        "indic_f1": D.get("indic", {}).get("f1"), "indic_fpr": D.get("indic", {}).get("fpr"),
        "flow_f1": D.get("flow", {}).get("f1"), "explain_s_per_item": P["explain_s_per_item"],
        "peak_rss_gb": P["peak_rss_gb"], "decode_tps": (P.get("llm_median") or {}).get("decode_tps"),
        "model": cfg.get("model")}})


if __name__ == "__main__":
    sys.exit(main())
