"""Share-text helpers that do not import the detectors.

detect_mode returns 0 (SMS), 1 (link) or 2 (network). A link is only a bare URL
(or a URL with no other words), so a message that merely contains a link stays SMS.
strings_json is the bundled Hindi table beside this file.
"""
import json
import re
from pathlib import Path

_BARE = re.compile(
    r'(?i)^(?:https?://|upi://|upiglobal://|tez://|gpay://|phonepe://|paytmmp://|'
    r'bhim://|credpay://|amazonpay://|intent://[^\s#]*#Intent;[^\s]*scheme=upi|www\.)\S+$'
)
_URL = re.compile(
    r'(?i)\b(?:https?://|upi://|upiglobal://|tez://|gpay://|phonepe://|paytmmp://|'
    r'bhim://|credpay://|amazonpay://|www\.)\S+'
)
_BARE_UPI_QUERY = re.compile(r'(?i)^(?:[a-z][a-z0-9_]{0,15}=[^&\s]*&)+[a-z][a-z0-9_]{0,15}=[^&\s]*$')
_FLOW = re.compile(
    r'(?i)\b(?:port scans?|ports|tcp|udp|syn[- ]flood|failed logins?|'
    r'serror_rate|dst_host|num_failed_logins|packet fragments?|'
    r'half-open|teardrop|ping-of-death)\b')
_MESSAGE = re.compile(
    r'(?i)\b(?:dear|customer|otp|kyc|please|account|rupees|rs\.?|upi|bank|'
    r'whatsapp|sms|click|urgent|prize|lottery|aadhaar|pan)\b|'
    r'[\u0900-\u097F]')


def detect_mode(text):
    t = (text or '').strip()
    if not t:
        return 0
    if t.startswith('{') and t.endswith('}'):
        try:
            json.loads(t)
            return 2
        except (ValueError, TypeError):
            pass
    if _BARE.match(t):
        return 1
    if _BARE_UPI_QUERY.match(t) and re.search(r'(?i)(?:^|&)pa=[^&\s]+@[^&\s]+', t):
        return 1
    urls = list(_URL.finditer(t))
    if len(urls) == 1:
        rest = (t[:urls[0].start()] + t[urls[0].end():]).strip(' \t\r\n.,;:"\'()[]')
        if rest == '' or (len(rest) <= 12 and not any(ch.isalpha() for ch in rest)):
            return 1
    if _FLOW.search(t) and not _MESSAGE.search(t) and len(t) <= 500:
        return 2
    return 0


def strings_json():
    path = Path(__file__).resolve().parent / 'strings_hi.json'
    return path.read_text(encoding='utf-8')
