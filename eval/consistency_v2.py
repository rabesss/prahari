"""Versioned explanation consistency heuristic; independent of the frozen proxy."""
import re

CLAIM = re.compile(r'\b(no risk found|nothing suspicious|safe|unsafe|dangerous|malicious|phishing|fraud(?:ulent)?|scam|suspicious)\b', re.I)
NEGATION = re.compile(r"\b(?:not|never|isn't|isnt|aren't|arent|without)\s+(?:(?:very|really|entirely|completely|totally|necessarily)\s+){0,2}(?:(?:a|an|the)\s+)?$", re.I)
SPLIT = re.compile(r'[.;!?]|\b(?:but|however|although|though|yet|except|while)\b', re.I)


def consistent(verdict, text):
    """Flag opposite explicit claims; contrast clauses and local negation are evaluated independently."""
    if verdict not in (0, 1, 'uncertain'): raise ValueError('invalid verdict')
    if verdict == 'uncertain': return True
    for clause in SPLIT.split(text.lower()):
        for match in CLAIM.finditer(clause):
            term = match.group()
            # Generic warnings about future scams are advice, not claims about the item.
            prefix = clause[:match.start()]
            negated = bool(NEGATION.search(prefix))
            if term not in ('no risk found', 'nothing suspicious') and not negated and not re.search(
                    r"\b(?:is|are|looks|seems|appears|was|were|isn't|aren't)\b", prefix):
                continue
            benign = term in ('no risk found', 'nothing suspicious', 'safe')
            # Negation applies only to words preceding this claim within this clause.
            if negated: benign = not benign
            if (verdict == 1 and benign) or (verdict == 0 and not benign): return False
    return True
