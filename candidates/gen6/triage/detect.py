"""Classical detectors (scikit-learn) + rule evidence. Models live in artifacts/."""
from pathlib import Path

import joblib
import numpy as np

from . import indicrules, mech, rules, textmodel

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


_indic = None


def indic_model():
    global _indic
    if _indic is None:
        _indic = joblib.load(ART / "indic.joblib")
    return _indic


def predict_text(texts):
    """Detect scams in SMS and Indian-context messages.

    Indian-language and Indian-context messages go through the Indic model and the mechanism
    layer, where the verdict follows what the message asks the reader to do. Everything else keeps
    the generic English SMS model path unchanged, so the British SMS corpus behaviour is intact.
    """
    m = _model("sms")
    ps = m.predict_proba(texts)[:, 1]
    ana = {}
    idx = []
    for i, t in enumerate(texts):
        a = mech.analyze(t)
        ana[i] = a
        strong_safe = {"transaction_receipt", "otp_notification", "protective", "official_channel",
                       "bill_notice", "appointment_notice"} & set(a["safe"])
        if mech.indic_context(t) or strong_safe:
            idx.append(i)
    pi = {}
    if idx:
        p_ind = textmodel.prob(indic_model(), [texts[i] for i in idx])
        pi = dict(zip(idx, p_ind.tolist()))
    out = []
    for i, (t, p) in enumerate(zip(texts, ps)):
        if i in pi:
            a = ana[i]
            lab, s, _ = mech.decide(float(pi[i]), a)
            ev = mech.evidence(a) or [d for _, d in rules.text_indicators(t)]
            out.append((lab, s, ev[:6]))
            continue
        a = ana[i]
        decisive = [n for n, _ in a["harm"] if n in mech.DECISIVE]
        benign_note = not a["harm"] and (a["official_channel"] or a["receipt"] or a["bill"]
                                        or a["appointment"] or a["notice"])
        if decisive:
            out.append((1, max(float(p), 0.85), mech.evidence(a)[:6]))
            continue
        if benign_note:
            out.append((0, min(float(p), 0.40), mech.evidence(a)[:6]))
            continue
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
        if f.get("num_failed_logins", 0) > 0:
            ev.append("failed login attempts recorded on the connection")
            p = max(float(p), 0.90)
        if f.get("wrong_fragment", 0) > 0:
            ev.append("malformed packet fragments, typical of a teardrop or pod flood")
            p = max(float(p), 0.90)
        if f.get("land", 0) > 0:
            ev.append("source and destination are the same host and port")
            p = max(float(p), 0.90)
        if f.get("serror_rate", 0) > 0.5:
            ev.append("most connections were half-open (SYN errors)")
        if f.get("num_failed_logins", 0) > 0:
            ev.append(f"{int(f['num_failed_logins'])} failed logins")
        if f.get("dst_host_diff_srv_rate", 0) > 0.5:
            ev.append("the host contacted many different services")
        if f.get("root_shell", 0) > 0:
            ev.append("a root shell was obtained")
        lab = 1 if p >= 0.10 else 0
        out.append((lab, float(p), ev))
    return out


def predict_flow_text(text):
    ev = rules.flow_text_indicators(text)
    harm = [(n, d) for n, d in ev if n not in ("rejected", "beaconing")]
    if rules.BENIGN_FLOW.search(text) and not any(n in ("root", "flood") for n, _ in harm):
        return 0, 0.35, ["routine traffic, consistent with a normal update or expected session"]
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
