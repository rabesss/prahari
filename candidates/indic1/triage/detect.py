"""Classical detectors (scikit-learn) + rule evidence. Models live in artifacts/."""
from pathlib import Path

import joblib
import numpy as np

from . import indicrules, rules

ART = Path(__file__).resolve().parents[1] / "artifacts"
_cache = {}

FLOW_CAT = ("protocol_type", "service", "flag")
STRONG = {"credential_request", "kyc_threat", "authority_threat", "remote_app", "brand_lookalike",
          "digit_swap", "ip_host", "payment_request"}


def _model(name):
    if name not in _cache:
        _cache[name] = joblib.load(ART / f"{name}.joblib")
    return _cache[name]


def _decide(p, ev, lo=0.32, hi=0.60):
    strong = sum(1 for n, _ in ev if n in STRONG)
    if any(n == "official_domain" for n, _ in ev) and strong == 0:
        p = min(p, 0.5)
    p = min(1.0, p + 0.1 * strong)
    if p >= hi:
        return 1, p
    if p <= lo:
        return 0, p
    return "uncertain", p


def _text_decision(p, score, prot, strong):
    """Combine the TF-IDF probability with the Indian-context request/protection evidence.

    Strong scam mechanics (a secret to hand over, a collect request, a paid "job", a payment
    tied to a link or deadline) lift even a Hindi message the English model has never seen.
    Protection phrases genuine alerts use ("we never ask for OTP", "no customs fee") pull a
    suspicious-looking receipt back down; two independent protection phrases clear it.
    """
    if strong:
        return max(p, 0.80)
    if prot >= 1.6:
        return min(p, 0.20)
    if prot >= 0.8:
        return min(p, 0.25)
    return p


def predict_text(texts):
    m = _model("sms")
    ps = m.predict_proba(texts)[:, 1]
    out = []
    for t, p in zip(texts, ps):
        ind_ev, score, prot, strong = indicrules.indicators(t)
        p = _text_decision(float(p), score, prot, strong)
        ev = list(ind_ev) if ind_ev else rules.text_indicators(t)
        lab, s = _decide(p, [], lo=0.32, hi=0.60)
        out.append((lab, s, [d for _, d in ev][:6]))
    return out


def predict_url(urls):
    m = _model("url")
    ps = m.predict_proba([u.lower() for u in urls])[:, 1]
    out = []
    for u, p in zip(urls, ps):
        ev = rules.url_indicators(u)
        lab, s = _decide(float(p), ev)
        out.append((lab, s, [d for _, d in ev]))
    return out


def flow_matrix(rows, cats=None):
    import pandas as pd
    df = pd.DataFrame(rows)
    for c in FLOW_CAT:
        df[c] = df[c].astype("category")
        if cats is not None:
            df[c] = df[c].cat.set_categories(cats[c])
    return df


def predict_flow(feature_rows):
    bundle = _model("flow")
    X = flow_matrix(feature_rows, bundle["cats"])[bundle["columns"]]
    ps = bundle["model"].predict_proba(X)[:, 1]
    out = []
    for f, p in zip(feature_rows, ps):
        ev = []
        if f.get("serror_rate", 0) > 0.5:
            ev.append("most connections were half-open (SYN errors)")
        if f.get("num_failed_logins", 0) > 0:
            ev.append(f"{int(f['num_failed_logins'])} failed logins")
        if f.get("dst_host_diff_srv_rate", 0) > 0.5:
            ev.append("the host contacted many different services")
        if f.get("root_shell", 0) > 0:
            ev.append("a root shell was obtained")
        lab = 1 if p >= 0.5 else 0
        out.append((lab, float(p), ev))
    return out


def predict_flow_text(text):
    ev = rules.flow_text_indicators(text)
    lab = 1 if any(n != "rejected" for n, _ in ev) else ("uncertain" if ev else 0)
    return lab, (0.9 if lab == 1 else 0.5 if ev else 0.1), [d for _, d in ev]


def classify_any(kind, inp):
    """Used by explain: returns (label, score, evidence) for any input kind."""
    if kind == "url":
        return predict_url([inp])[0]
    if kind == "flow":
        return predict_flow_text(inp)
    if kind == "injection":
        inj = rules.injection_indicators(inp)
        if inj:
            return 1, 0.95, [d for _, d in inj]
    return predict_text([inp])[0]
