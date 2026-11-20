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


# Lexical heuristics: advice and conditional clauses are not input claims.
CUES = {
    'payment': re.compile(r'\b(?:pay(?:ment|ing)?|transfer|money|funds|fee|deposit|recharge|collect request)\b|भुगतान', re.I),
    'otp': re.compile(r'\b(?:otp|pin|code|one[- ]time password)\b', re.I),
    'link': re.compile(r'\b(?:link|url|website|web site)\b', re.I),
    'app': re.compile(r'\b(?:app(?:lication)?|apk|download|install)\b', re.I),
    'kyc': re.compile(r'\b(?:kyc|know your customer)\b', re.I),
    'call': re.compile(r'\b(?:call|phone|dial|telephone|helpline)\b', re.I),
}
# Restrict bare domains to known TLDs and exclude email addresses and file names.
URL = re.compile(r'(?<![\w@.])(?:[a-z][a-z0-9+.-]*://[^\s]+|(?:[a-z0-9-]+\.)+(?:co\.in|gov\.in|com|in|org|net|io|xyz|top|example|test)(?![\w.-]))', re.I)
PAYMENT_RECEIPT = re.compile(r'\b(?:payment|money|funds|amount|refund|deposit)\b.{0,45}\b(?:received|credited|paid|completed|processed|successful)\b|\b(?:received|credited|paid)\b.{0,45}\b(?:payment|money|funds|amount|refund)\b|\breceipt\b', re.I)
PAYMENT_REQUEST = re.compile(r'\b(?:pay|send|transfer|recharge|due|collect request|payment request|payment required)\b|भुगतान.{0,30}मांग', re.I)
REQUEST_CLAIM = re.compile(r'\b(?:ask(?:s|ed|ing)?|request(?:s|ed|ing)?|want(?:s|ed)?|demand(?:s|ed|ing)?|require(?:s|d)?|transfer|pay|deposit|payment link|told to)\b|मांग|चाहत', re.I)
ADVICE = re.compile(r"^\s*(?:never|don't|do not|avoid|report|call|block|delete|verify|check|contact|ignore|if|when|unless|you should|you may want to|please|it is safer to|i would say)\b|^\s*(?:यदि|अगर|जब)", re.I)
ADVICE_MODAL = re.compile(r'\b(?:you should|you may want to|please|it is safer to|i would say)\b', re.I)
# Inputs may carry any real domain; only explanation-side wording is restricted.
INPUT_URL = re.compile(r'(?<![\w@.])(?:[a-z][a-z0-9+.-]*://[^\s]+|(?:[a-z0-9-]+\.)+(?!(?:pdf|js|py|txt|exe|jpg|jpeg|png|gif|doc|docx|xls|xlsx|zip|apk|csv|json|html?)(?![\w.-]))[a-z]{2,}(?![\w.-]))', re.I)
NOTE_PREFIX = re.compile(r'^\s*(?:please\s+)?(?:note|be aware|remember)\s+(?:that\s+)?', re.I)
ADVICE_SPLIT = re.compile(r"\band\s+(?=(?:you should|you may want to|please|it is safer to|never|don't|do not|report|call|block|delete|verify|check|contact|ignore)\b)", re.I)
NEGATION = re.compile(r"\b(?:no|not|never|doesn't|don't|didn't|does not|do not|did not|without)\b|नहीं", re.I)


def negated_cue(clause, match):
    before, after = clause[:match.start()], clause[match.end():]
    # Negation applies through an 'or' chain; an affirmative 'and' starts a new claim.
    before = re.split(r'\band\b', before, flags=re.I)[-1]
    if NEGATION.search(before):
        return True
    return bool(re.match(r"\s*(?:is|was|were|are|को|की|का)?\s*(?:\b(?:not|never)\b|नहीं)", after, re.I))


def grounding(input_text, explanation):
    if not isinstance(explanation, str) or len(re.findall(r'[^\W_]+', explanation, flags=re.UNICODE)) < 5:
        return False
    clauses = []
    for sentence in re.split(r'(?<=[.!?।])\s+', explanation):
        clauses.extend(re.split(r'[,;।!?]|\b(?:and then|so|but)\b|(?:इसलिए|लेकिन|फिर)', sentence, flags=re.I))
    split = []
    for clause in clauses:
        split.extend(ADVICE_SPLIT.split(clause))
    for clause in split:
        # "Please note that the sender requests an OTP" is a claim, not advice.
        clause = NOTE_PREFIX.sub('', clause)
        if ADVICE.search(clause):
            continue
        modal = ADVICE_MODAL.search(clause)
        if modal:
            # Only the advice tail is exempt; a claim before it is still checked.
            clause = clause[:modal.start()]
        for name, cue in CUES.items():
            matches = list(cue.finditer(clause))
            if not matches or all(negated_cue(clause, m) for m in matches):
                continue
            if name == 'link':
                if not INPUT_URL.search(input_text):
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
