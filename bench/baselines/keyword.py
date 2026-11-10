#!/usr/bin/env python3
"""Deliberately simple, untrained keyword and URL baseline."""
import re
from urllib.parse import urlparse

WORDS = re.compile(r'\b(?:otp|pin|kyc|prize|winner|urgent|verify|refund|collect|lottery|password|blocked|fee|customs)\b|ओटीपी|इनाम|शुल्क|बंद होगा',re.I)

def label(task, row):
    if task in ('sms','indic'): return int(bool(WORDS.search(row['text'])))
    if task == 'url':
        u=row['url'].lower(); host=urlparse(u if '://' in u else 'http://'+u).hostname or ''
        return int(bool(re.search(r'login|verify|secure|refund|account|kyc|[0-9]{1,3}(?:\.[0-9]{1,3}){3}|\.top$|\.xyz$',host)))
    f=row['features']
    return int(any(float(f.get(k,0))>0 for k in ('num_failed_logins','wrong_fragment','land','root_shell')) or float(f.get('serror_rate',0))>0.5)
