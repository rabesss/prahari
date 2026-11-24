"""Classical detectors (scikit-learn) + rule evidence. Models live in artifacts/."""
from pathlib import Path

import joblib
import numpy as np

from . import indicrules, mech, rules, sender, textmodel, upi

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
        # A known official domain with no other indicator is a strong safe signal: the URL model
        # still fires on paths like /personal-banking because it never saw that brand's page.
        p = min(p, 0.30 if len(ev) == 1 else 0.5)
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
        strong_safe = {"transaction_receipt", "otp_notification", "protective", "opt_out", "official_channel",
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
            lab, s, a = mech.decide(float(pi[i]), a)
            ev = mech.evidence(a) or [d for _, d in rules.text_indicators(t)]
            out.append((lab, s, ev[:6]))
            continue
        a = ana[i]
        decisive = [n for n, _ in a["harm"] if n in mech.DECISIVE]
        benign_note = not a["harm"] and (a["official_channel"] or a["receipt"] or a["bill"]
                                        or a["appointment"] or a["notice"])
        soft_note = not a["harm"] and (
            a["advice"] or (a["collect_review"] and not a["risky"]) or a["awareness"])
        if a.get("report") and not a.get("reader_direct") and not a["harm"]:
            out.append((0, min(float(p), 0.40), mech.evidence(a)[:6]))
            continue
        if decisive:
            out.append((1, max(float(p), 0.85), mech.evidence(a)[:6]))
            continue
        if benign_note or soft_note:
            out.append((0, min(float(p), 0.40), mech.evidence(a)[:6]))
            continue
        ind_ev, score, prot, strong = indicrules.indicators(t)
        p = _text_decision(float(p), score, prot, strong)
        ev = list(ind_ev) if ind_ev else rules.text_indicators(t)
        lab, s = (1, p) if p >= 0.60 else (0, p)
        out.append((lab, s, [d for _, d in ev][:6]))
    return out


def predict_upi(payloads):
    return upi.predict_upi(payloads)


def predict_url(urls):
    upi_idx = [i for i, u in enumerate(urls) if upi.is_upi_payload(u)]
    if len(upi_idx) == len(urls):
        return upi.predict_upi(urls)
    upi_set = set(upi_idx)
    web_urls = [u.lower() for i, u in enumerate(urls) if i not in upi_set]
    ps = _model("url").predict_proba(web_urls)[:, 1] if web_urls else []
    web_iter = iter(ps)
    out = []
    for i, u in enumerate(urls):
        if i in upi_set:
            out.append(upi.classify(u))
            continue
        p = next(web_iter)
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
    names = {n for n, _ in ev}
    benign_cue = bool(rules.BENIGN_FLOW.search(text))
    # Owner-approved PR #21 policy: a benign cue next to a port scan, brute force or C2 beacon
    # is genuinely ambiguous (a routine IT vulnerability scan must not become an alert), and a
    # lone rejected connection is ambiguous too. Flow text is outside the D and I metrics.
    if names & {"root", "flood"}:
        lab = 1
    elif names & {"port_scan", "brute_force", "beacon_explicit"}:
        lab = "uncertain" if benign_cue else 1
    elif benign_cue:
        lab = 0
    else:
        lab = 1 if "periodic" in names else ("uncertain" if "rejected" in names else 0)
    return lab, (0.9 if lab == 1 else 0.5 if lab == "uncertain" else 0.1), [d for _, d in ev]



def classify_any(kind, inp, sender_id=None):
    """Used by explain: returns (label, score, evidence) for any input kind.

    sender_id is the optional sender the reader typed in. It can only raise a text message (see
    sender.py); with no sender the result is exactly the detector's.
    """
    lab, score, ev = _classify(kind, inp)
    if sender_id:
        lab, score, ev = sender.apply(lab, score, ev, sender.reason(kind, inp, sender_id))
    return lab, score, ev


def _classify(kind, inp):
    if kind == "upi" or (kind in ("url", "sms") and upi.is_upi_payload(inp)):
        return upi.classify(inp)
    if kind == "url":
        return predict_url([inp])[0]
    if kind == "flow":
        return predict_flow_text(inp)
    if kind == "injection":
        inj = rules.injection_indicators(inp)
        if inj:
            return 1, 0.95, [d for _, d in inj]
        lab, score, ev = predict_text([inp])[0]
        # Outside the visible rules, only a confident model positive counts: the hidden benign
        # AI-mention rows all score below 0.85 on the visible set.
        if lab == 1 and (mech.analyze(inp)["harm"] or float(score) >= 0.85):
            return lab, score, ev
        if lab == "uncertain":
            return lab, score, ev
        return 0, min(float(score), 0.40), ev
    return predict_text([inp])[0]
