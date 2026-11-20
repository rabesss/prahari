"""Round-three proxy primitives. Scores use unrounded values."""
import math
import re
from pathlib import Path

from conventional import metrics


def conservative(gold, predictions, knee):
    result = metrics(gold, predictions)
    rates = result['conservative']
    for key, value in rates.items():
        if value is None:
            rates[key] = 0.0
    f1, fpr = rates['f1'], rates['fpr']
    result['score'] = f1 * (1 - min(0.5, max(0.0, fpr - knee) * 5))
    return result


def total(d, i, e, p):
    return 100 * (0.30*d + 0.30*i + 0.25*e + 0.15*p)


def mean(values):
    return sum(values) / len(values) if values else 0.0


# Heuristics only: protective recommendations and conditionals are not input claims.
CLAIM = re.compile(r"\b(?:ask|asks|asked|asking|request|requests|requested|requesting|want|wants|demand|demands|demanded|demanding|contain|contains|mention|mentions|say|says|said|include|includes|requires?|tells?)\b|मांग(?:ता|ती|ा)?|चाहता", re.I)
CUES = {
    'payment': re.compile(r'\b(?:pay(?:ment|ing)?|transfer|send (?:money|funds)|fee|deposit|recharge|collect request)\b|भुगतान', re.I),
    'otp': re.compile(r'\b(?:otp|one[- ]time (?:password|code)|pin|verification code)\b', re.I),
    'link': re.compile(r'\b(?:link|url|website|web site)\b|https?://|\bwww\.|\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,}\b', re.I),
    'app': re.compile(r'\b(?:app(?:lication)?|apk|download|install)\b', re.I),
    'kyc': re.compile(r'\b(?:kyc|know your customer)\b', re.I),
    'call': re.compile(r'\b(?:call|phone|dial|telephone|helpline)\b', re.I),
}
URL = re.compile(r'\b[a-z][a-z0-9+.-]*://\S+|(?<![\w.])[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,}(?![\w.])', re.I)
PAYMENT_RECEIPT = re.compile(r'\b(?:payment|money|funds|amount|refund|deposit)\b.{0,45}\b(?:received|credited|paid|completed|processed|successful)\b|\b(?:received|credited|paid)\b.{0,45}\b(?:payment|money|funds|amount|refund)\b|\breceipt\b', re.I)
PAYMENT_REQUEST = re.compile(r'\b(?:pay|send|transfer|recharge|due|collect request|payment request|payment required)\b|भुगतान.{0,30}मांग', re.I)
REQUEST_CLAIM = re.compile(r'\b(?:ask|asks|asked|asking|request|requests|requested|requesting|want|wants|demand|demands|demanded|demanding|requires?)\b|मांग(?:ता|ती|ा)?|चाहता', re.I)
CONDITIONAL = re.compile(r"^\s*(?:if|when|unless|यदि|अगर|जब)\b", re.I)
NEGATED = re.compile(r"\b(?:not|never|doesn't|don't|didn't|does not|do not|did not)\s*$|नहीं\s*$", re.I)


def grounding(input_text, explanation):
    if not isinstance(explanation, str) or len(explanation.strip().split()) < 5:
        return False
    # A condition only exempts its own clause, not the following assertion.
    for clause in re.split(r'[,;।!?]|(?<!\w)\.(?!\w)|\b(?:and then|so|but)\b|(?:इसलिए|लेकिन|फिर)', explanation, flags=re.I):
        if CONDITIONAL.search(clause):
            continue
        claims = [m for m in CLAIM.finditer(clause) if not NEGATED.search(clause[:m.start()])]
        if not claims:
            continue
        for name, cue in CUES.items():
            if not cue.search(clause):
                continue
            if name == 'link':
                if not URL.search(input_text):
                    return False
            elif not cue.search(input_text):
                return False
            elif (name == 'payment' and REQUEST_CLAIM.search(clause)
                  and PAYMENT_RECEIPT.search(input_text) and not PAYMENT_REQUEST.search(input_text)):
                return False
    return True


def tree_rss_kb(pids, proc=Path('/proc')):
    total_kb = 0
    for pid in pids:
        try:
            status = (proc / str(pid) / 'status').read_text()
        except OSError:
            continue
        match = re.search(r'^VmRSS:\s+(\d+)\s+kB', status, re.M)
        if match:
            total_kb += int(match.group(1))
    return total_kb if total_kb else None


def measurements_ok(latency, rss, timed_out=False):
    def valid(v):
        return isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v) and v > 0
    return not timed_out and valid(latency) and valid(rss) and latency <= 10.0 and rss <= 3.0
