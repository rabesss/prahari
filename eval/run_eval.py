#!/usr/bin/env python3
"""Proxy evaluator for the Bharat AI-SoC PS3 entry. Called by bin/eval; see research/BRIEF.md for the formula.

Last stdout line is a JSON summary. Per-item details that would reveal hidden test content are written only to
the controller-private dir (/var/tmp/arm-bharat-ai-soc-eval/private/), never under research/evals/.
"""
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import math
import os
import re
import resource
import tempfile
import threading
import uuid
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conventional import metrics as conventional_metrics
from consistency_v2 import consistent as consistent_v2
from india_challenge import load_bytes as load_india
from proxy_v3 import conservative, grounding, measurements_ok, mean, total as v3_total, tree_rss_kb

PROJ = Path(__file__).resolve().parents[1]
DATA = Path("/var/tmp/arm-bharat-ai-soc-data")
HIDDEN = DATA / "hidden"
INDIA_V2_SHA256 = "532e017843381b23879a92b7559f88bb8cf23dd650df98c00f68ae0224995fb0"
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


def host_snapshot():
    """Load averages and host-wide CPU steal over a short sample interval."""
    try:
        load = list(os.getloadavg())
        def cpu_ticks():
            fields = Path('/proc/stat').read_text().splitlines()[0].split()
            if fields[0] != 'cpu' or len(fields) < 9:
                raise ValueError('incomplete CPU counters')
            ticks = [int(x) for x in fields[1:9]]
            return sum(ticks), ticks[7]
        total0, steal0 = cpu_ticks()
        time.sleep(.1)
        total1, steal1 = cpu_ticks()
        if total1 <= total0 or steal1 < steal0:
            raise ValueError('invalid CPU counter delta')
        return {'load_average': load, 'cpu_steal_percent': 100 * (steal1 - steal0) / (total1 - total0)}
    except (OSError, ValueError, IndexError):
        return None


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


def tree_pids(root, proc=Path('/proc')):
    pids, frontier = {root}, [root]
    while frontier:
        p = frontier.pop()
        try:
            for thread in (proc / str(p) / "task").iterdir():
                try:
                    children = (thread / "children").read_text().split()
                except OSError:
                    continue
                for c in children:
                    c = int(c)
                    if c not in pids:
                        pids.add(c)
                        frontier.append(c)
        except OSError:
            pass
    return pids


def session_pids(sid):
    result = set()
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
            if int(stat[3]) == sid and stat[0] != 'Z':
                result.add(int(entry.name))
        except (OSError, ValueError, IndexError):
            pass
    return result


def scope_available(env):
    try:
        return subprocess.run(['systemd-run', '--user', '--scope', '--collect',
                               '-p', 'MemoryAccounting=yes', 'true'], env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def scope_members(cgroup):
    members = set()
    if cgroup is not None and cgroup.exists():
        for path in [cgroup / 'cgroup.procs', *cgroup.glob('**/cgroup.procs')]:
            try:
                members.update(int(x) for x in path.read_text().split())
            except (OSError, ValueError):
                pass
    return members


def survivors_after_kill(members, timeout=2.0):
    """Allow killed processes to exit, then fail if any members remain."""
    deadline = time.monotonic() + timeout
    while True:
        remaining = members()
        if not remaining or time.monotonic() >= deadline:
            return remaining
        time.sleep(.05)


def user_units(env):
    try:
        result = subprocess.run(['systemctl', '--user', 'list-units', '--all', '--plain', '--no-legend', '--no-pager'],
                                env=env, capture_output=True, text=True, timeout=10, check=True)
        return {line.split()[0] for line in result.stdout.splitlines() if line.split()}
    except (OSError, subprocess.SubprocessError):
        return None


def external_census(roots, exclusions):
    """Snapshot same-user entries; an incomplete census fails closed."""
    entries = {}
    excluded = [Path(p).resolve() for p in exclusions]
    def visit(path):
        if any(path == x or x in path.parents for x in excluded):
            return
        try:
            st = path.lstat()
            if st.st_uid == os.getuid():
                entries[str(path)] = (st.st_ino, st.st_mtime_ns, st.st_size, st.st_mode)
            if path.is_dir() and not path.is_symlink():
                for child in path.iterdir():
                    visit(child)
        except FileNotFoundError:
            pass
    for root in roots:
        root = Path(root)
        if root.is_dir():
            for child in root.iterdir():
                visit(child)
    return entries


def sweep_external(roots, prefix):
    # Only this run's unpredictable evaluator-owned prefix is eligible.
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for path in root.glob(prefix + '*'):
            if path.lstat().st_uid != os.getuid():
                continue
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)


STAGE_ENV_KEYS = frozenset(('PATH', 'LANG', 'LC_ALL', 'TZ', 'HOME', 'XDG_CACHE_HOME',
    'XDG_DATA_HOME', 'TMPDIR', 'PYTHONPATH', 'PYTHONDONTWRITEBYTECODE', 'HC_GUARD_LOG',
    'HC_GUARD_DENY_PATHS', 'HC_MODEL_REGISTRY', 'HC_PY', 'http_proxy', 'https_proxy',
    'HTTP_PROXY', 'HTTPS_PROXY', 'no_proxy', 'HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE',
    'OMP_NUM_THREADS', 'PRAHARI_EXTERNAL_PREFIX'))


def stage_environment(env):
    result = {k: v for k, v in env.items() if k in STAGE_ENV_KEYS}
    result['PATH'] = '/usr/local/bin:/usr/bin:/bin'
    return result


def cgroup_census():
    root = Path('/sys/fs/cgroup/user.slice') / f'user-{os.getuid()}.slice' / f'user@{os.getuid()}.service'
    if not root.is_dir():
        raise OSError('user cgroup unavailable')
    groups = {}
    for directory, _, files in os.walk(root, onerror=lambda e: (_ for _ in ()).throw(e)):
        path = Path(directory)
        if 'cgroup.procs' in files:
            groups[str(path)] = frozenset((path / 'cgroup.procs').read_text().split())
    return groups


def run_proc(cmd, env, timeout, cwd, log, watch_pte=None, vis_log=None, rss_method=None):
    """Run a stage in a scope or session, measure it, then kill and census it."""
    method = rss_method or env.get('PRAHARI_RSS_METHOD') or ('systemd_scope' if scope_available(env) else 'proc_fallback')
    t0 = time.monotonic()
    start = log.stat().st_size if log.exists() else 0
    unit = 'prahari-eval-' + uuid.uuid4().hex + '.scope'
    units_before = user_units(env)
    roots = ['/dev/shm', '/var/tmp'] + ([env['XDG_RUNTIME_DIR']] if env.get('XDG_RUNTIME_DIR') else [])
    prefix = env.get('PRAHARI_EXTERNAL_PREFIX', 'prahari-eval-' + uuid.uuid4().hex + '-')
    external_before = None
    cgroups_before = None
    if env.get('PRAHARI_ISOLATION_METHOD') == 'unavailable':
        try:
            sweep_external(roots, prefix)
            external_before = external_census(roots, [env['PRAHARI_SCRATCH'], env['PRAHARI_WORK'], log.parent, PROJ / 'research' / 'evals'])
            cgroups_before = cgroup_census()
        except OSError:
            pass
    scope = None
    peak_kb, legacy_hwm_kb, pte_seen, timed_out, stray = None, 0, False, False, False
    peak_file = None
    with open(log, 'ab') as lf:
        if method == 'systemd_scope':
            # systemd-run waits for the actual stage; its exit status is authoritative.
            stage_env = stage_environment(env)
            stage = ['/usr/bin/env', '-i', *[f'{k}={v}' for k, v in stage_env.items()]]
            if env.get('PRAHARI_ISOLATION_METHOD') == 'bwrap':
                stage += ['bwrap', '--die-with-parent', '--ro-bind', '/', '/',
                          '--tmpfs', '/tmp', '--tmpfs', '/dev/shm',
                          '--bind', env['PRAHARI_SCRATCH'], env['PRAHARI_SCRATCH'],
                          '--bind', env['PRAHARI_WORK'], env['PRAHARI_WORK'], '--']
            # A scope-owned keeper preserves memory.peak until the evaluator reads it.
            # The shell execs the stage, so systemd-run's waited status is the stage status.
            wrapper = 'sleep 3600 </dev/null >/dev/null 2>&1 & sleep .2; exec "$@"'
            launch = ['systemd-run', '--user', '--quiet', '--scope', '--collect', '--unit', unit,
                      '-p', 'MemoryAccounting=yes', '--', '/bin/sh', '-c', wrapper, 'stage', *stage, *cmd]
            child_env = env
        else:
            child_env = stage_environment(env)
            launch = cmd
            if env.get('PRAHARI_ISOLATION_METHOD') == 'bwrap':
                launch = ['bwrap', '--die-with-parent', '--ro-bind', '/', '/', '--tmpfs', '/tmp', '--tmpfs', '/dev/shm',
                          '--bind', env['PRAHARI_SCRATCH'], env['PRAHARI_SCRATCH'],
                          '--bind', env['PRAHARI_WORK'], env['PRAHARI_WORK'], '--', *cmd]
        p = subprocess.Popen(launch, env=child_env, cwd=cwd, stdout=lf, stderr=subprocess.STDOUT, start_new_session=True)
        cleanup_done = False
        try:
            while True:
                if method == 'systemd_scope' and scope is None:
                    q = subprocess.run(['systemctl', '--user', 'show', unit, '--property=ControlGroup', '--value'],
                                       env=env, capture_output=True, text=True)
                    cg = q.stdout.strip()
                    if q.returncode == 0 and cg.startswith('/'):
                        scope = Path('/sys/fs/cgroup') / cg.lstrip('/')
                        try:
                            peak_file = (scope / 'memory.peak').open()
                        except OSError:
                            pass
                pids = scope_members(scope) if method == 'systemd_scope' else session_pids(p.pid) | tree_pids(p.pid)
                rss = tree_rss_kb(pids)
                if rss is not None:
                    peak_kb = max(peak_kb or 0, rss)
                for pid in pids:
                    try:
                        status = Path(f'/proc/{pid}/status').read_text()
                        hwm = re.search(r'^VmHWM:\s+(\d+)\s+kB', status, re.M)
                        if hwm:
                            legacy_hwm_kb = max(legacy_hwm_kb, int(hwm.group(1)))
                        if watch_pte and not pte_seen:
                            if watch_pte in Path(f'/proc/{pid}/maps').read_text():
                                pte_seen = True
                            else:
                                for fd in Path(f'/proc/{pid}/fd').iterdir():
                                    try:
                                        if os.readlink(fd) == watch_pte:
                                            pte_seen = True
                                            break
                                    except OSError:
                                        pass
                    except OSError:
                        pass
                if p.poll() is not None:
                    break
                if time.monotonic() - t0 > timeout:
                    timed_out = True
                    break
                time.sleep(.1)
            wall_s = time.monotonic() - t0
            if method == 'systemd_scope':
                if timed_out:
                    subprocess.run(['systemctl', '--user', 'kill', '--kill-whom=all', '--signal=SIGKILL', unit],
                                   env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill(); p.wait()
                rc = p.returncode
                try:
                    if peak_file is not None:
                        peak_file.seek(0)
                        peak_kb = int(peak_file.read().strip()) / 1024
                    else:
                        peak_kb = None
                except (OSError, ValueError):
                    peak_kb = None
                subprocess.run(['systemctl', '--user', 'kill', '--kill-whom=all', '--signal=SIGKILL', unit],
                               env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                # A lingering member is a failure even if stopping the unit later would remove it.
                stray = bool(survivors_after_kill(lambda: scope_members(scope)))
                subprocess.run(['systemctl', '--user', 'stop', unit], env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                for pid in session_pids(p.pid):
                    try: os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                try: os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                p.wait()
                rc = p.returncode
                peak_kb = max(peak_kb or 0, legacy_hwm_kb, resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss) or None
                stray = bool(survivors_after_kill(lambda: session_pids(p.pid)))
            cleanup_done = True
        finally:
            if not cleanup_done:
                if method == 'systemd_scope':
                    subprocess.run(['systemctl', '--user', 'kill', '--kill-whom=all', '--signal=SIGKILL', unit],
                                   env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    for pid in session_pids(p.pid):
                        try: os.kill(pid, signal.SIGKILL)
                        except ProcessLookupError: pass
                if p.poll() is None:
                    try: os.killpg(p.pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                    p.wait()
            if peak_file is not None:
                peak_file.close()
    units_after = user_units(env)
    stray_unit = units_before is None or units_after is None or bool(units_after - units_before - {unit})
    persistent = False
    stray_cgroup = False
    if env.get('PRAHARI_ISOLATION_METHOD') == 'unavailable':
        try:
            external_after = external_census(roots, [env['PRAHARI_SCRATCH'], env['PRAHARI_WORK'], log.parent, PROJ / 'research' / 'evals'])
            persistent = external_before is None or any(external_before.get(k) != v for k, v in external_after.items())
            cgroups_after = cgroup_census()
            stray_cgroup = cgroups_before is None or any(
                unit not in path and (path not in cgroups_before or bool(pids - cgroups_before[path]))
                for path, pids in cgroups_after.items())
            sweep_external(roots, prefix)
        except OSError:
            persistent = True
            stray_cgroup = True
    res = {'stray_cgroup': stray_cgroup, 'persistent_state': persistent, 'stray_unit': stray_unit, 'rc': rc, 'wall_s': wall_s, 'peak_rss_mb': peak_kb / 1024 if peak_kb is not None else None,
           'legacy_peak_rss_mb': round(legacy_hwm_kb / 1024, 1), 'pte_seen': pte_seen,
           'timed_out': timed_out, 'stray_process': stray, 'rss_method': method}
    if vis_log is not None:
        with open(vis_log, 'a') as vf:
            vf.write(f"== {Path(cmd[0]).name} {' '.join(c for c in cmd[1:3] if c.startswith('--') or len(c) < 8)} "
                     f"rc={res['rc']} timeout={timed_out} wall_s={res['wall_s']} peak_rss_mb={res['peak_rss_mb']}\n")
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
    ap.add_argument("--repeats", type=int, default=1, help="run the full evaluator N times")
    ap.add_argument("--label", default=None)
    ap.add_argument("--quick", action="store_true", help="8 explain items, 1 repeat, not promotable")
    a = ap.parse_args()

    if a.repeats < 1:
        ap.error('--repeats must be positive')
    results = [run_once(a, k) for k in range(1 if a.quick else a.repeats)]
    if len(results) == 1:
        result = results[0]
    else:
        result = dict(results[-1])
        result['runs'] = results
        def average_tree(nodes):
            if all(isinstance(x, dict) for x in nodes):
                common = set.intersection(*(set(x) for x in nodes))
                return {k: average_tree([x[k] for x in nodes]) for k in common}
            if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in nodes):
                return mean(nodes)
            return nodes[-1]
        for key in ('detection', 'india', 'grounding_pass_rate', 'latency_s_per_item', 'peak_process_tree_rss_gb'):
            if all(key in r for r in results):
                result[key] = average_tree([r[key] for r in results])
        result['score'] = mean([r['score'] for r in results])
        result['proxy_v2_legacy'] = mean([r.get('proxy_v2_legacy', 0) for r in results])
        result['scores'] = {k: mean([r.get('scores', {}).get(k, 0) for r in results])
                            for k in ('D', 'I', 'E', 'P', 'C')}
        result['failures'] = [f'run {k+1}: {x}' for k, r in enumerate(results) for x in r['failures']]
        result['infra_errors'] = [f'run {k+1}: {x}' for k, r in enumerate(results) for x in r['infra_errors']]
        result['promotable'] = all(r['promotable'] for r in results)
        result['contended'] = any(r.get('contended') is not False for r in results)
    print(json.dumps(result))
    return 0 if not result['failures'] and not result['infra_errors'] else 1


def explanation_components(item, output):
    """Keep the frozen E checks independent from the diagnostic gold check."""
    score, checks, valid = explain_checks(item, output)
    grounded = float(grounding(item['input'], output['explanation'])) if valid else 0.0
    diagnostic = float(consistent_v2(item['label'], output['explanation'])) if valid else 0.0
    return score, checks, valid, grounded, diagnostic


def candidate_hash(root):
    """Hash names, types, executable bits and bytes, independent of checkout umask."""
    h = hashlib.sha256()
    def add(value):
        h.update(len(value).to_bytes(8, 'big')); h.update(value)
    def visit(path, rel):
        st = path.lstat()
        add(os.fsencode(rel))
        add(b'dir' if path.is_dir() and not path.is_symlink() else
            b'file-exec' if st.st_mode & 0o111 else b'file')
        if path.is_symlink():
            raise ValueError('candidate symlinks are unsupported')
        elif path.is_dir():
            for child in sorted(path.iterdir(), key=lambda x: os.fsencode(x.name)):
                visit(child, str(Path(rel) / child.name))
        elif path.is_file():
            add(str(st.st_size).encode())
            with path.open('rb') as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b''):
                    h.update(chunk)
        else:
            raise ValueError('candidate contains unsupported file type')
    visit(root, '.')
    return h.hexdigest()


def isolation_env(scratch):
    paths = {'HOME': 'home', 'XDG_CACHE_HOME': 'cache', 'XDG_DATA_HOME': 'data', 'TMPDIR': 'tmp'}
    for name in paths.values():
        (scratch / name).mkdir()
    return {key: str(scratch / name) for key, name in paths.items()}


def run_once(a, run_index):
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    EVROOT.mkdir(parents=True, exist_ok=True)
    queued = time.monotonic()
    with open(LOCK, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        queued = time.monotonic() - queued
        full_start = time.monotonic()
        original = Path(a.candidate).resolve()
        with tempfile.TemporaryDirectory(prefix='prahari-run-', dir=EVROOT) as scratch_name:
            scratch = Path(scratch_name)
            try:
                digest = candidate_hash(original)
                shutil.copytree(original, scratch / 'candidate', symlinks=True)
                if candidate_hash(scratch / 'candidate') != digest:
                    raise ValueError('scratch copy hash mismatch')
            except (OSError, ValueError) as exc:
                # The normal evaluator records a failed run for missing candidates.
                digest = None
                (scratch / 'candidate').mkdir(exist_ok=True)
            return _run_once(a, run_index, original, scratch, digest, queued, full_start)


def _run_once(a, run_index, original, scratch, digest, queued, full_start):
    host_start = host_snapshot()
    cand = scratch / "candidate"
    label = re.sub(r"[^A-Za-z0-9_.-]", "_", a.label or original.name)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    art = PROJ / "research" / "evals" / f"{stamp}-{label}"
    priv = EVROOT / "private" / f"{stamp}-{label}"
    work = EVROOT / "work" / f"{stamp}-{label}"
    for d in (art, priv, work):
        d.mkdir(parents=True, exist_ok=True)
    failures, infra = [], []
    samples = [host_start] if host_start else []
    stop_sampling = threading.Event()
    def sample_host():
        while not stop_sampling.wait(5):
            sample = host_snapshot()
            if sample:
                samples.append(sample)
    sampler = threading.Thread(target=sample_host, daemon=True)
    sampler.start()
    summary = {"label": label, "candidate": str(original), "candidate_hash": digest, "session_id": os.environ.get("PRAHARI_EVAL_SESSION"), "stamp": stamp, "artifacts": str(art.relative_to(PROJ)),
               "quick": a.quick, "host_start": host_start,
               "contended": host_start['load_average'][0] > 1.5 if host_start else None, "queued_s": round(queued, 1)}

    def finish(score, scores, extra=None):
        stop_sampling.set()
        sampler.join()
        summary['host_end'] = host_snapshot()
        if summary['host_end']:
            samples.append(summary['host_end'])
        if samples:
            summary['host_during'] = {
                'samples': len(samples),
                'load_1m_max': max(x['load_average'][0] for x in samples),
                'load_1m_mean': mean([x['load_average'][0] for x in samples]),
                'cpu_steal_percent_max': max(x['cpu_steal_percent'] for x in samples),
                'cpu_steal_percent_mean': mean([x['cpu_steal_percent'] for x in samples]),
            }
        if host_start is None or summary['host_end'] is None:
            infra.append('host load or CPU steal measurement unavailable')
        summary.update({"score": score, "scores": scores, "failures": failures, "infra_errors": infra,
                        "full_wall_s": time.monotonic() - full_start})
        try:
            if candidate_hash(original) != digest:
                failures.append('candidate modified during eval')
        except (OSError, ValueError):
            if digest is not None:
                failures.append('candidate modified during eval')
        if samples and max(x['cpu_steal_percent'] for x in samples) > 20:
            infra.append('CPU steal exceeded 20 percent')
        summary["promotable"] = ((not a.quick) and not failures and not infra and summary['contended'] is False
                                 and summary.get('rss_method') == 'systemd_scope'
                                 and summary.get('isolation_method') == 'bwrap')
        if extra:
            summary.update(extra)
        (art / "summary.json").write_text(json.dumps(summary, indent=1))
        with open(PROJ / "research" / "evals" / "ledger.jsonl", "a") as f:
            f.write(json.dumps(summary) + "\n")
        with open(PROJ / "research" / "LOG.md", "a") as f:
            f.write(f"- {stamp} `{label}` score={summary['score']} D={scores.get('D')} E={scores.get('E')} "
                    f"P={scores.get('P')} C={scores.get('C')} fail={len(failures)} quick={a.quick}\n")
        shutil.rmtree(work, ignore_errors=True)
        return summary

    if digest is None:
        failures.append('candidate could not be copied or hashed')
        return finish(0.0, {})
    if not (cand / "bin" / "predict").exists() or not (cand / "bin" / "explain").exists():
        failures.append("missing bin/predict or bin/explain")
        return finish(0.0, {})

    india_path = HIDDEN / 'india_hidden_v2.jsonl'
    try:
        india_data = india_path.read_bytes()
        if hashlib.sha256(india_data).hexdigest() != INDIA_V2_SHA256:
            raise ValueError('SHA-256 mismatch')
        india_rows = load_india(india_data, expected_sha256=INDIA_V2_SHA256)
        if len(india_rows) != 400:
            raise ValueError('expected 400 India v2 rows')
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        infra.append(f'adaptive India v2 data missing or invalid: {exc}')
        return finish(0.0, {})

    try:
        hidden_rows, hidden_hashes = {}, {}
        for name in ('sms_test', 'url_test', 'indic_test', 'flow_test', 'explain_set'):
            data = (HIDDEN / (name + '.jsonl')).read_bytes()
            hidden_hashes[name] = hashlib.sha256(data).hexdigest()
            hidden_rows[name] = [json.loads(line) for line in data.decode('utf-8').splitlines() if line.strip()]
            if not hidden_rows[name]:
                raise ValueError(name + ' is empty')
        hidden_hashes['india_hidden_v2'] = INDIA_V2_SHA256
        summary['hidden_sha256'] = hidden_hashes
    except (OSError, ValueError, UnicodeError) as exc:
        infra.append(f'hidden data missing or invalid: {exc}')
        return finish(0.0, {})

    env = {k: v for k, v in os.environ.items() if not k.startswith(("BOXD", "SAIL", "OPENAI", "ANTHROPIC", "GH_", "GITHUB"))}
    method = 'systemd_scope' if scope_available(env) else 'proc_fallback'
    summary['rss_method'] = method
    # A failed bwrap probe fails closed: never claim isolation we cannot create.
    try:
        probe = subprocess.run(['bwrap', '--ro-bind', '/', '/', '--tmpfs', '/tmp', '--tmpfs', '/dev/shm', '--',
                                '/usr/bin/python3', '-c',
                                'import os; assert os.statvfs("/sys/fs/cgroup").f_flag & os.ST_RDONLY'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        isolated = probe.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        isolated = False
    summary['isolation_method'] = 'bwrap' if isolated else 'unavailable'

    env.update(isolation_env(scratch))
    env.update({
        'PRAHARI_RSS_METHOD': method,
        'PRAHARI_ISOLATION_METHOD': summary['isolation_method'],
        'PRAHARI_SCRATCH': str(scratch), 'PRAHARI_WORK': str(work),
        'PRAHARI_EXTERNAL_PREFIX': 'prahari-eval-' + uuid.uuid4().hex + '-',
        "PYTHONPATH": str(PROJ / "eval" / "guard"),
        "HC_GUARD_LOG": str(work / "guard.log"),
        "HC_GUARD_DENY_PATHS": f"{HIDDEN}:{DATA / 'indic'}:{EVROOT / 'private'}",
        "HC_MODEL_REGISTRY": str(REGISTRY),
        "HC_PY": str(PY),
        "http_proxy": "http://127.0.0.1:9", "https_proxy": "http://127.0.0.1:9",
        "HTTP_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9", "no_proxy": "127.0.0.1,localhost",
        "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "OMP_NUM_THREADS": env.get("OMP_NUM_THREADS", "2"),
    })
    (work / "guard.log").touch()
    log = art / "run.log"
    scores, details = {}, {}

    # ---------------- D: detection ----------------
    D = {}
    timings = {}
    for task, src, field, ptask in (("sms", "sms_test", "text", "sms"), ("url", "url_test", "url", "url"),
                                     ("indic", "indic_test", "text", "sms"), ("flow", "flow_test", "features", "flow")):
        gold_rows = hidden_rows[src]
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
        legacy = det_metrics(gold, preds)
        D[task] = conservative(gold, preds, .01)
        D[task]["legacy"] = legacy
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
    legacy_d = round(sum(W['D'][t] * D[t]['legacy']['score'] for t in W['D'] if t in D), 4)
    scores['D'] = mean([D[t]['score'] if t in D else 0 for t in W['D']])
    details["detection"] = D

    # ---------------- I: adaptive India validation ----------------
    india_in, india_out = work / 'india.in.jsonl', work / 'india.out.jsonl'
    write_jsonl(india_in, [{'id': r['id'], 'text': r['text'], 'route': r['route']} for r in india_rows])
    res = run_proc([str(PY), str(PROJ / 'eval' / 'india_v2_runner.py'), str(cand), str(india_in), str(india_out)],
                   env, 900, cand, priv / 'proc.log', vis_log=log)
    india_res = res
    if res['rc'] != 0 or res['timed_out']:
        failures.append(f"India prediction rc={res['rc']} timeout={res['timed_out']}")
    india_preds = {r.get('id'): r.get('label') for r in (read_jsonl(india_out) or []) if isinstance(r, dict)}
    gold_i = {r['id']: int(r['label'] == 'malicious') for r in india_rows}
    india_metrics = conservative(gold_i, india_preds, .03)
    if india_metrics['invalid']:
        failures.append(f"India prediction: {india_metrics['invalid']} missing/invalid labels")
    inj_gold = {r['id']: gold_i[r['id']] for r in india_rows if r['route'] == 'injection'}
    inj = conservative(inj_gold, india_preds, .03)['conservative']
    scores['I'] = india_metrics['score']
    details['india'] = {'metrics': india_metrics, 'injection_recall': inj['recall'] or 0.0,
                        'benign_ai_mention_fpr': inj['fpr'] or 0.0}

    # ---------------- E: explanation ----------------
    items = hidden_rows['explain_set']
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
    reps = 1
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
    e_sum, legacy_e_sum, grounding_sum, consistency_v2_sum, valid, plausible = 0.0, 0.0, 0.0, 0.0, 0, 0
    for it in items:
        o = outs.get(it["id"])
        tot, r, ok, grounded, diagnostic = explanation_components(it, o)
        legacy_e_sum += tot
        consistency_v2_sum += diagnostic
        grounding_sum += grounded
        e_sum += tot
        valid += ok
        plausible += bool(ok and llm_plausible(o))
        for k in check_tot:
            check_tot[k] += r[k]
        by_kind.setdefault(it["kind"], []).append(tot)
        per_item.append({"id": it["id"], "kind": it["kind"], "score": round(tot, 3), "checks": r,
                         "output": o})
    n = max(1, len(items))
    scores["E"] = .85 * e_sum / n + .15 * grounding_sum / n
    details["explanation"] = {"n": len(items), "valid": valid, "llm_plausible": plausible,
                              "grounding_pass_rate": grounding_sum / n, "consistency_v2": consistency_v2_sum / n,
                              "check_rates": {k: round(v / n, 3) for k, v in check_tot.items()},
                              "by_kind": {k: round(sum(v) / len(v), 3) for k, v in by_kind.items()}}
    write_jsonl(priv / "explain_items.jsonl", per_item)
    if valid < len(items):
        failures.append(f"explain: {len(items) - valid} missing/invalid outputs")

    # ---------------- P: performance ----------------
    walls = sorted(r["wall_s"] for r in runs) or [None]
    med_wall = walls[len(walls) // 2]
    lat = med_wall / n if med_wall else None
    rss_gb = max((r["peak_rss_mb"] for r in runs if r["peak_rss_mb"] is not None), default=0) / 1024
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
    legacy_rss = runs[0]['legacy_peak_rss_mb'] / 1024 if runs else 0
    legacy_lat = round(runs[0]['wall_s'], 3) / n if runs else None
    legacy_parts = dict(p_parts, explain_latency=logscale(legacy_lat, 3.0, 15.0),
                        peak_rss=clip((3.0 - legacy_rss) / 2.0) if legacy_rss > 0 else 0.0)
    legacy_p = round(sum(W['P'][k] * legacy_parts[k] for k in W['P']), 4)
    P["parts"] = {k: round(v, 3) for k, v in p_parts.items()}
    scores["P"] = sum(W["P"][k] * p_parts[k] for k in W["P"])
    details["performance"] = P
    llm_stats = [o.get("llm", {}) for o in outs.values() if isinstance(o, dict)]
    if llm_stats:
        def med(key):
            v = sorted(s.get(key) for s in llm_stats if isinstance(s.get(key), (int, float)))
            return v[len(v) // 2] if v else None
        P["llm_median"] = {k: med(k) for k in ("prompt_tokens", "generated_tokens", "prefill_tps", "decode_tps")}

    # ---------------- C: compliance ----------------
    tests = run_proc([str(PY), "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "tests"], env, 600, cand, art / "tests.log") \
        if (cand / "tests").is_dir() else {"rc": 1}
    app = run_proc([str(cand / "bin" / "app"), "--selftest"], env, 300, cand, art / "app.log") \
        if (cand / "bin" / "app").exists() else {"rc": 1}
    guard_lines = (work / 'guard.log').read_text().splitlines()
    (art / 'guard.log').write_text('\n'.join(guard_lines) + ('\n' if guard_lines else ''))
    net_viol = [l for l in guard_lines if 'NET blocked' in l]
    file_viol = [l for l in guard_lines if 'FILE blocked' in l]
    if file_viol:
        failures.append(f'candidate tried to read hidden eval data ({len(file_viol)} attempts)')
    process_runs = list(timings.values()) + [india_res] + runs + [tests, app]
    if any(r.get('stray_cgroup') for r in process_runs):
        failures.append('stray cgroup or process outside evaluator scope')
    if any(r.get('persistent_state') for r in process_runs):
        failures.append('persistent state outside scratch')
    if any(r.get('stray_unit') for r in process_runs):
        failures.append('stray unit')
    if any(r.get('stray_process') for r in process_runs):
        failures.append('stray process')
    peaks = [r.get('peak_rss_mb') for r in process_runs]
    if any(p is None for p in peaks):
        rss_gb = None
    else:
        rss_gb = max(peaks) * (1024 ** 2) / 1e9
    P['peak_rss_gb'] = rss_gb
    rss_gib = max(peaks) / 1024 if rss_gb else None
    p_parts['peak_rss'] = clip((3.0 - rss_gib) / 2.0) if rss_gib else 0.0
    P['parts']['peak_rss'] = p_parts['peak_rss']
    scores['P'] = sum(W['P'][k] * p_parts[k] for k in W['P'])
    if not measurements_ok(lat, rss_gb, any(r.get('timed_out', True) for r in process_runs)):
        failures.append('performance sanity cap failed: missing measurement, timeout, latency > 10.0 s/item, or RSS > 3.0 GB')
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

    legacy_total = 100 * (W['top']['D']*legacy_d + W['top']['E']*round(legacy_e_sum/n, 4) +
                          W['top']['P']*legacy_p + W['top']['C']*scores['C'])
    if not gate['pass']:
        legacy_total = min(legacy_total, W['gate_cap'])
    total = v3_total(scores['D'], scores['I'], scores['E'], scores['P'])
    if not gate['pass'] or net_viol or file_viol:
        total = 0.0
    (art / "details.json").write_text(json.dumps(details, indent=1))
    return finish(total, scores, {"proxy_v2_legacy": legacy_total, "detection": D, "india": details["india"],
        "grounding_pass_rate": grounding_sum / n, "latency_s_per_item": lat, "peak_process_tree_rss_gb": rss_gb, "headline": {
        "sms_f1": D.get("sms", {}).get("conservative", {}).get("f1"), "url_f1": D.get("url", {}).get("conservative", {}).get("f1"),
        "indic_f1": D.get("indic", {}).get("conservative", {}).get("f1"), "indic_fpr": D.get("indic", {}).get("conservative", {}).get("fpr"),
        "flow_f1": D.get("flow", {}).get("conservative", {}).get("f1"), "explain_s_per_item": P["explain_s_per_item"],
        "peak_rss_gb": P["peak_rss_gb"], "decode_tps": (P.get("llm_median") or {}).get("decode_tps"),
        "model": cfg.get("model")}})


if __name__ == "__main__":
    sys.exit(main())
