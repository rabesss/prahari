"""When to look for an installed screen-sharing app. Python never sees which apps are installed.

The Android side checks a fixed list of packages (RemoteApps.kt, declared in the manifest's
<queries>) only when verdict() sets remote_app_check. Nothing here changes a verdict.
"""
import re

from triage import llm, rules
import report_card

# The detector's own remote_app rule, looked up by name so the two never drift apart.
REMOTE_APP = re.compile(next(pat for name, pat, _ in rules.TEXT_RULES if name == 'remote_app'))
# Scam types that try to reach a bank, KYC, UPI, OTP or support desk: what a watched screen steals.
MONEY_TYPES = {
    'OTP or PIN theft', 'a safe-account transfer scam', 'a remote-access app scam', report_card.DEBIT_ALERT,
}
# Banks, wallets and UPI apps among the detector's known brands (rules.BRANDS).
BANK_BRANDS = [b for b in rules.BRANDS if b in {'sbi', 'hdfc', 'icici', 'axis', 'kotak', 'pnb', 'paytm', 'phonepe',
                                                'gpay', 'bhim', 'npci', 'paypal'}] + ['yono', 'bob', 'canara']
# Words that put a bank, KYC, UPI, OTP or support desk in the message itself, plus the bank and
# wallet names in BANK_BRANDS. Refund wording counts: fake refund desks are the classic route to a
# screen-sharing app. An electricity or job scam without
# one of these does not show the banner.
MONEY_DESK = re.compile(
    r'\b(?:bank\w*|kyc|upi|otp|pin|cvv|mpin|net ?banking|account|a/c|debit|credit card|card|wallet|'
    r'customer (?:care|support|service)|support (?:team|executive|agent)|helpline|refund|'
    + '|'.join(re.escape(b) for b in BANK_BRANDS) + r')\b|बैंक|खाता|कस्टमर केयर', re.I)


def needs_check(kind, text, lab, scam, actions=()):
    """True when an installed remote-control app would matter for this result."""
    if kind == 'flow':
        return False
    text = str(text or '')
    if REMOTE_APP.search(text.lower()) and lab != 0:
        return True
    if lab == 0 and llm.DEBIT_STEP not in (actions or ()):
        return False
    scam = str(scam or '')
    if kind == 'upi' or scam.startswith('a UPI ') or scam in MONEY_TYPES or llm.DEBIT_STEP in (actions or ()):
        return True
    return bool(MONEY_DESK.search(text)) or report_card.category(kind, text, scam) == 'customer_care'
