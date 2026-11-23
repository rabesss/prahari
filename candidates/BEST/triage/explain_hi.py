"""Hindi summary of a checked item: fixed text assembled from the detector result, no model call.

Llama 3.2 1B cannot write usable Hindi on this hardware (a probe on dev items produced sentences
such as "आलसी लोगों को..." for a UPI scam), so the app's Hindi mode shows this summary next to the
English Llama explanation instead of asking the model for Hindi. The summary is

    {verdict line}: {strongest evidence phrase}। {key fact}

where the evidence phrase is the one the English opening uses (llm.compact_evidence) and the key
fact is the one the English prompt is grounded in (llm.key_fact). Every string comes from
explain_hi.json: evidence phrases reuse the app's Hindi table (android/python/strings_hi.json) where
the English matches, and the rest are written for this table (no machine translation). A
phrase the table does not know (a truncated detector line, a new rule) is never guessed: the
summary uses the per-verdict fallback reason instead. Hosts of risky links are defanged.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

from . import llm

_TABLE = Path(__file__).with_name("explain_hi.json")


@lru_cache(maxsize=1)
def table():
    if _TABLE.is_file():
        text = _TABLE.read_text(encoding="utf-8")
    else:  # Chaquopy may not expose __file__ as a real path; read it as package data instead
        import importlib.resources as resources
        text = resources.files("triage").joinpath("explain_hi.json").read_text(encoding="utf-8")
    data = json.loads(text)
    data["_patterns"] = [(re.compile(p["re"]), p["hi"]) for p in data.get("patterns", []) if p.get("hi")]
    return data


def _noun(kind):
    return "link" if kind == "url" else "network" if kind == "flow" else "message"


def _defang(host, official=False):
    return host if official else host.replace(".", "[.]")


def translate(phrase, depth=0):
    """Hindi for one evidence phrase, or None when the table does not cover it exactly."""
    t = table()
    phrase = (phrase or "").strip()
    if not phrase or depth > 3:
        return None
    hi = t["phrases"].get(phrase)
    if hi:
        return hi
    for rx, tmpl in t["_patterns"]:
        m = rx.search(phrase)
        if not m:
            continue
        vals = m.groupdict()
        if "inner" in vals:
            inner = translate(vals["inner"], depth + 1)
            if inner is None:
                return None
            vals["inner"] = inner
        if "host" in vals:
            vals["host"] = _defang(vals["host"], official=phrase.startswith("official domain"))
        try:
            return tmpl.format(**vals)
        except (KeyError, IndexError):
            return None
    # Two mechanism phrases joined by "and" (llm._harm_evidence joins the two shortest).
    join = t.get("join_and", {}).get("hi")
    if join:
        for m in re.finditer(r" and ", phrase):
            a, b = translate(phrase[:m.start()], depth + 1), translate(phrase[m.end():], depth + 1)
            if a and b:
                return join.format(a=a, b=b)
    return None


def summary_hi(kind, inp, verdict, evidence):
    """The Hindi summary line, or "" when the table has no translation for the verdict line."""
    t = table()
    key = "uncertain" if verdict == "uncertain" else str(int(verdict))
    head = ((t.get("verdict", {}).get(key) or {}).get(_noun(kind)) or {}).get("hi")
    if verdict == 0 and llm.DEBIT_STEP in llm.actions_for(kind, verdict, inp):
        # The app shows a cleared bank-debit alert as CHECK ALERT, not NO RISK; the summary agrees.
        head = (t.get("alert_heading") or {}).get("hi") or head
    if not head:
        return ""
    phrases = llm.compact_evidence(kind, inp, evidence, verdict)
    reason = translate(phrases[0]) if phrases else None
    if not reason:
        table_key = "fallback_reason_network" if kind == "flow" else "fallback_reason"
        reason = (t.get(table_key, {}).get(key) or {}).get("hi", "")
    fact = t.get("facts", {}).get(llm.key_fact(kind, inp, verdict, evidence), "")
    out = f"{head}: {reason}" if reason else head
    out = out.rstrip("।. ") + "।"
    if fact:
        out += " " + fact.strip()
    return out


def label_hi():
    return (table().get("label") or {}).get("hi", "")
