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


# Heuristics only: a general recommendation is not a claim about the input.
CLAIM = re.compile(r"\b(?:asks?|asking|requests?|requesting|contains?|wants? you to|says|said|demands?|demanding|requires?|tells? you to)\b", re.I)
CUES = {
    'payment': re.compile(r'\b(?:pay(?:ment|ing)?|transfer|send (?:money|funds)|fee|deposit|recharge|collect request)\b', re.I),
    'otp': re.compile(r'\b(?:otp|one[- ]time (?:password|code)|pin|verification code)\b', re.I),
    'link': re.compile(r'\b(?:link|url|website|web site)\b|https?://|\bwww\.|\b[a-z0-9-]+(?:\.[a-z0-9-]+)+\b', re.I),
    'app': re.compile(r'\b(?:app(?:lication)?|apk|download|install)\b', re.I),
    'kyc': re.compile(r'\b(?:kyc|know your customer)\b', re.I),
    'call': re.compile(r'\b(?:call|phone|dial|telephone|helpline)\b', re.I),
}
PAYMENT_RECEIPT = re.compile(r'\b(?:payment|money|funds|amount|refund|deposit)\b.{0,45}\b(?:received|credited|paid|completed|processed|successful)\b|\b(?:received|credited|paid)\b.{0,45}\b(?:payment|money|funds|amount|refund)\b', re.I)
PAYMENT_REQUEST = re.compile(r'\b(?:pay|send|transfer|deposit|recharge|fee|due|collect request|payment request|payment required)\b', re.I)


def grounding(input_text, explanation):
    for sentence in re.split(r'(?<=[.!?;])\s+', explanation):
        for claim in CLAIM.finditer(sentence):
            tail = sentence[claim.end():]
            # Negated statements about a request are not affirmative claims.
            if re.search(r"\b(?:does not|doesn't|did not|never|not)\s*$", sentence[:claim.start()], re.I):
                continue
            for name, cue in CUES.items():
                if not cue.search(tail):
                    continue
                if not cue.search(input_text):
                    return False
                if (name == 'payment' and PAYMENT_RECEIPT.search(input_text)
                        and not PAYMENT_REQUEST.search(input_text)
                        and (re.search(r'\b(?:asks?|asking|requests?|requesting|demands?|demanding|requires?|wants? you to|tells? you to)\b', claim.group(), re.I)
                             or PAYMENT_REQUEST.search(tail))):
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
