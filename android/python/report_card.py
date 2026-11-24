"""Offline report card and family warning for a SCAM or SUSPICIOUS result.

Nothing here decides a verdict. The category comes from the detector's own scam-type phrase,
with a few text cues to pick the impersonated party. Text built here is only ever copied to the
clipboard or handed to the Android share sheet by the user; nothing is sent automatically.

Chakshu categories are the list in the Sanchar Saathi FAQ ("What is suspected fraud
communication?", items i-xi, sancharsaathi.gov.in), English names kept exactly as published.
"""
import json
import re
import time
import unicodedata
from urllib.parse import unquote
from pathlib import Path

# id, official English name, Hindi name. Order is the FAQ order.
CHAKSHU = (
    ('investment', 'Investment, Stock Market and Trading', 'निवेश, शेयर बाज़ार और ट्रेडिंग'),
    ('dot_trai', 'Impersonation as DoT / TRAI', 'DoT / TRAI बनकर धोखा'),
    ('police_govt', 'Impersonation as Police, CBI, Customs, Aadhaar, RBI etc',
     'पुलिस, CBI, कस्टम, आधार, RBI आदि बनकर धोखा'),
    ('relative', 'Impersonation as a relative / friend', 'रिश्तेदार / दोस्त बनकर धोखा'),
    ('kyc_payment', 'KYC and Payment related to Bank / Electricity / Gas / Insurance etc',
     'बैंक / बिजली / गैस / बीमा आदि से जुड़े KYC और भुगतान'),
    ('customer_care', 'Fake Customer Care Helpline', 'नकली कस्टमर केयर हेल्पलाइन'),
    ('job_offer', 'Online job/ gift/ lottery / loans offers', 'ऑनलाइन नौकरी / उपहार / लॉटरी / लोन का ऑफ़र'),
    ('ivr', 'IVR / Robo Calls', 'IVR / रोबो कॉल'),
    ('sextortion', 'Sextortion', 'सेक्सटॉर्शन (अश्लील फ़ोटो/वीडियो से ब्लैकमेल)'),
    ('link', 'Suspected link/ website', 'संदिग्ध लिंक / वेबसाइट'),
    ('other', 'Any Other Suspected Fraud', 'कोई और संदिग्ध धोखा'),
)
_NAMES = {cid: (en, hi) for cid, en, hi in CHAKSHU}

# One plain description and one safety step per category, for the family message.
FAMILY = {
    'investment': ('fake investment or trading tip',
                   'No real app or group guarantees profit. Do not deposit money.',
                   'नकली निवेश या ट्रेडिंग टिप',
                   'कोई असली ऐप या ग्रुप पक्का मुनाफ़ा नहीं देता। पैसे जमा न करें।'),
    'dot_trai': ('fake DoT or TRAI call about your SIM',
                 'DoT and TRAI never call to cut your SIM. Hang up.',
                 'SIM बंद करने वाली नकली DoT या TRAI कॉल',
                 'DoT और TRAI SIM बंद करने के लिए कॉल नहीं करते। फ़ोन काट दें।'),
    'police_govt': ('fake police, CBI, customs or RBI threat',
                    'Police never arrest anyone or collect money on a call. Hang up.',
                    'नकली पुलिस, CBI, कस्टम या RBI की धमकी',
                    'पुलिस कॉल पर न गिरफ़्तार करती है, न पैसे मांगती है। फ़ोन काट दें।'),
    'relative': ('message from a "relative" on a new number asking for money',
                 'Call the person on their old number before you send anything.',
                 'नए नंबर से "रिश्तेदार" बनकर पैसे मांगने वाला मैसेज',
                 'पैसे भेजने से पहले उनके पुराने नंबर पर कॉल करके पूछें।'),
    'kyc_payment': ('fake bank, KYC or bill payment message',
                    'Banks never ask for OTP, PIN or KYC by message or link. Use the official app.',
                    'नकली बैंक, KYC या बिल भुगतान वाला मैसेज',
                    'बैंक मैसेज या लिंक से OTP, PIN या KYC नहीं मांगते। सिर्फ़ असली ऐप इस्तेमाल करें।'),
    'customer_care': ('fake customer care number',
                      'Take helpline numbers only from the official app or website. Never install an app a caller asks for.',
                      'नकली कस्टमर केयर नंबर',
                      'हेल्पलाइन नंबर सिर्फ़ असली ऐप या वेबसाइट से लें। कॉल करने वाले के कहने पर कोई ऐप न डालें।'),
    'job_offer': ('fake job, prize or loan offer',
                  'Real jobs, prizes and loans never ask you to pay first.',
                  'नकली नौकरी, इनाम या लोन का ऑफ़र',
                  'असली नौकरी, इनाम या लोन के लिए पहले पैसे नहीं देने पड़ते।'),
    'ivr': ('recorded robo call',
            'Hang up on recorded calls that ask you to press a key.',
            'रिकॉर्ड की हुई रोबो कॉल',
            'बटन दबाने को कहने वाली रिकॉर्डेड कॉल तुरंत काट दें।'),
    'sextortion': ('blackmail threat',
                   'Do not pay. Block the sender and report at cybercrime.gov.in.',
                   'ब्लैकमेल की धमकी',
                   'पैसे न दें। भेजने वाले को ब्लॉक करें और cybercrime.gov.in पर शिकायत करें।'),
    'link': ('fake website link',
             'Do not open the link. Type the official website yourself.',
             'नकली वेबसाइट का लिंक',
             'लिंक न खोलें। असली वेबसाइट खुद टाइप करके खोलें।'),
    'upi': ('fake UPI payment QR or link',
            'Receiving money never needs a UPI PIN. Check the name before you pay.',
            'नकली UPI पेमेंट QR या लिंक',
            'पैसे पाने के लिए कभी UPI PIN नहीं लगता। भुगतान से पहले नाम जांचें।'),
    'other': ('scam message',
              'Do not reply, pay or share any code. Check with the official source.',
              'ठगी वाला मैसेज',
              'जवाब न दें, पैसे न भेजें, कोई कोड न बताएं। असली स्रोत से पुष्टि करें।'),
}

MEDIUM = {
    'qr': ('QR code', 'QR कोड'),
    'whatsapp': ('WhatsApp', 'WhatsApp'),
    'sms': ('SMS', 'SMS'),
    'sms_or_whatsapp': ('SMS or WhatsApp message', 'SMS या WhatsApp मैसेज'),
    'url': ('Link', 'लिंक'),
    'upi': ('UPI QR or payment link', 'UPI QR या पेमेंट लिंक'),
}

# The medium inside an English sentence of the family message (Hindi uses MEDIUM in brackets).
FAMILY_MEDIUM = {
    'qr': ('through a QR code', ''),
    'whatsapp': ('on WhatsApp', ''),
    'sms': ('by SMS', ''),
    'sms_or_whatsapp': ('by SMS or WhatsApp', ''),
}

LOST_MONEY = ('Already lost money? Call 1930 / cybercrime.gov.in',
              'पैसे चले गए? 1930 पर कॉल करें / cybercrime.gov.in')
DEBIT_ALERT = 'a bank debit alert to confirm'
# MainActivity.OWN_CONTACT_LINE: what the app shows for an alert it raises to SUSPICIOUS.
RAISED_EVIDENCE = ('Sends you to its own link or number; real bank alerts point to the bank app or a '
                   'toll-free line')

# Scam-type phrases the detector emits (llm.scam_type, llm.MECH_TYPE, upi.scam_type_for) whose
# category is certain from the phrase alone. Phrases that need text context are in _CONTEXT.
_TYPE = {
    'sextortion or blackmail': 'sextortion',
    'a fake police or customs threat': 'police_govt',
    'a safe-account transfer scam': 'police_govt',
    'an impersonation scam': 'relative',
    'an investment or trading scam': 'investment',
    'a fake job or loan scam': 'job_offer',
    'a fake job or task scam': 'job_offer',
    'a fake prize or lottery scam': 'job_offer',
    'a fake lottery or prize scam': 'job_offer',
    'OTP or PIN theft': 'kyc_payment',
    'a fake KYC or account check': 'kyc_payment',
    'an account-blocking scam': 'kyc_payment',
    'an account-blocking threat': 'kyc_payment',
    'an electricity disconnection scam': 'kyc_payment',
    'a payment fraud': 'kyc_payment',
    'a fake payment request': 'kyc_payment',
    'UPI collect-request fraud': 'kyc_payment',
    'a QR-code payment scam': 'kyc_payment',
    DEBIT_ALERT: 'kyc_payment',
    'a phishing link': 'link',
    'a phishing link on a lookalike domain': 'link',
    'a shortened link that hides its destination': 'link',
    'a link worth checking': 'link',
}
# Phrases that name a mechanism, not a Chakshu category: the text decides, else "other".
_CONTEXT = {'an extortion threat', 'a crypto payment scam', 'an advance-fee scam', 'a remote-access app scam',
            'a gift-card scam', 'an identity-document scam', 'a scam message', 'a message worth checking'}

_SEXTORTION = re.compile(r'private (?:recording|photo|video)|intimate|nude|morphed|sextortion|अश्लील', re.I)
_DOT_TRAI = re.compile(r'\b(?:dot|trai)\b|department of telecom|दूरसंचार विभाग|ट्राई', re.I)
_RELATIVE = re.compile(
    r"\b(?:papa|mummy|mumma|beta|beti|bhai|bhaiya|didi|uncle|aunty|chacha|mama|son|daughter|"
    r"dad|mom|cousin)\b.{0,60}\b(?:new number|naya number|this is my number|phone (?:lost|broke|kharab))\b|"
    r"\b(?:new number|naya number)\b.{0,60}\b(?:papa|mummy|beta|bhai|didi|uncle|dad|mom)\b", re.I)
_POLICE = re.compile(
    r'\b(?:police|cbi|ncb|narcotics|customs|court|arrest|warrant|fir|cyber cell|aadhaar|aadhar|rbi|ed)\b|'
    r'digital arrest|पुलिस|गिरफ़्तार|गिरफ्तार|आधार', re.I)
# A bank or KYC scam is reported as fake customer care only when it names a support desk, not
# when it merely quotes a helpline or toll-free number.
_CARE_DESK = re.compile(r'customer (?:care|support|service)|support (?:team|executive|agent)|कस्टमर केयर', re.I)
_CARE = re.compile(r'customer (?:care|support|service)|helpline|help desk|support (?:team|executive|agent)|toll[- ]free|'
                   r'कस्टमर केयर', re.I)
_IVR = re.compile(r'\bivr\b|press \d|dabay?e|दबाएं|recorded (?:message|call)|robo ?call', re.I)
_JOB = re.compile(r'\b(?:job|salary|loan|lottery|prize|gift|reward|work from home|part[- ]time|task|lucky draw|kbc)\b|'
                  r'नौकरी|लोन|लॉटरी|इनाम', re.I)
_INVEST = re.compile(r'\b(?:invest\w*|trading|stock|share market|ipo|returns?|profit|double)\b|निवेश|मुनाफ़ा|मुनाफा', re.I)
_CUSTOMS = re.compile(r'\bcustoms\b|कस्टम', re.I)
_BANK = re.compile(r'\b(?:bank|kyc|upi|otp|pin|account|card|electricity|bijli|gas|insurance|refund)\b|बैंक|खाता|बिजली', re.I)
_THREAT = re.compile(r'case|warrant|arrest|legal|parcel|illegal|मुकदमा|गिरफ़्तार|गिरफ्तार', re.I)


def category(kind, text, scam_type):
    """Chakshu category id for one result. Deterministic; never changes a verdict."""
    text = str(text or '')
    scam = str(scam_type or '').strip()
    base = 'kyc_payment' if scam.startswith('a UPI ') else _TYPE.get(scam)
    if base == 'sextortion' or _SEXTORTION.search(text):
        return 'sextortion'
    if _DOT_TRAI.search(text) and base in (None, 'police_govt', 'kyc_payment'):
        return 'dot_trai'
    if base == 'relative' or (base is None and _RELATIVE.search(text)):
        return 'relative'
    if base:
        if base == 'kyc_payment' and scam != DEBIT_ALERT and _CARE_DESK.search(text):
            return 'customer_care'
        return base
    # A mechanism phrase or a generic one: only text context names the category.
    if _POLICE.search(text) and _THREAT.search(text):
        return 'police_govt'
    if scam == 'an advance-fee scam' and _CUSTOMS.search(text):
        return 'police_govt'  # a customs fee impersonates customs; a plain courier fee does not
    if _CARE.search(text):
        return 'customer_care'
    if _INVEST.search(text) and scam != 'an advance-fee scam':
        return 'investment'
    if _JOB.search(text):
        return 'job_offer'
    if scam == 'a remote-access app scam' and _BANK.search(text):
        return 'kyc_payment'
    if _IVR.search(text):
        return 'ivr'
    if kind == 'url':
        return 'link'
    return 'other'


_URL = re.compile(r'(?i)\b(?:https?|hxxps?)://[^\s<>"\']+|\bwww\.[^\s<>"\']+')
_HOST = re.compile(r'(?i)\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}\b')


def defang(s):
    """hxxp(s):// and [.] for every link or bare host. Already defanged input is unchanged."""
    s = str(s or '')

    def url(m):
        u = re.sub(r'(?i)^http', 'hxxp', m.group(0))
        return re.sub(r'(?<!\[)\.(?!\])', '[.]', u)

    out, last = [], 0
    for m in _URL.finditer(s):
        out.append(_HOST.sub(lambda h: h.group(0).replace('.', '[.]'), s[last:m.start()]))
        out.append(url(m))
        last = m.end()
    out.append(_HOST.sub(lambda h: h.group(0).replace('.', '[.]'), s[last:]))
    return ''.join(out)


# Two-part public suffixes common in Indian scam links; anything else keeps its last two labels.
_SUFFIX2 = {'co.in', 'gov.in', 'nic.in', 'org.in', 'net.in', 'ac.in', 'edu.in', 'res.in', 'firm.in', 'gen.in',
            'ind.in', 'co.uk', 'org.uk', 'com.au', 'com.sg', 'com.my', 'co.za', 'com.br', 'com.cn', 'com.hk',
            'com.pk', 'com.bd', 'com.np', 'com.ng', 'co.id', 'co.jp', 'co.kr', 'co.nz'}


_GENERIC2 = {'com', 'co', 'net', 'org', 'gov', 'ac', 'edu', 'ltd', 'plc', 'nic', 'res', 'mil', 'or', 'ne', 'go'}
# Characters IDNA treats as a label dot (ideographic, fullwidth and halfwidth full stops).
_IDNA_DOTS = re.compile('[\u3002\uff0e\uff61]')


def registrable(host):
    """The registered name of a host (evil.top for a.b.evil.top, sbi.co.in for x.sbi.co.in).

    Subdomains and paths are what a scammer can personalise per victim at no cost; the
    registered name is what the family needs to avoid."""
    labels = [x for x in host.split('.') if x]
    keep = 3 if len(labels) >= 3 and '.'.join(labels[-2:]) in _SUFFIX2 else 2
    return '.'.join(labels[-keep:])


def _ambiguous(registered):
    """True when the last two labels may themselves be a public suffix not in _SUFFIX2 (com.tr,
    gov.de...). Without a full suffix list the safe choice is to leave the link out: showing
    them could name a shared suffix, and keeping a third label could keep a personal subdomain."""
    labels = registered.split('.')
    return (len(labels) == 2 and len(labels[-1]) == 2 and labels[0] in _GENERIC2
            and registered not in _SUFFIX2)


def link_origin(text):
    """First link in the text as scheme and registered domain only, defanged. No subdomain, path
    or query: those can carry the reader's own name, id or number."""
    # Percent-encoded and IDNA dots separate labels too: normalise them before anything reads a host.
    text = _IDNA_DOTS.sub('.', re.sub(r'%2[eE]', '.', str(text or '')))
    for m in re.finditer(r'(?i)\b(https?)://([^\s/?#<>"\']+)|\bwww\.([^\s/?#<>"\']+)', text):
        if _official(m.group(0).rstrip('.,);!')):
            continue  # an official link quoted beside the scam one is not what to avoid
        return _origin(m)
    return ''


def _official(url):
    try:
        from triage import rules
        return any(name == 'official_domain' for name, _ in rules.url_indicators(url))
    except Exception:
        return False


def _origin(m):
    if m.group(1):
        host = m.group(2).split('@')[-1].split(':')[0]
        origin = f'{m.group(1).lower()}://{host.lower()}'
    else:
        origin = 'www.' + m.group(3).split(':')[0].lower()
    scheme, _, host = origin.rpartition('://') if '://' in origin else ('', '', origin)
    # Percent-encoded and IDNA dots separate labels too, so they cannot hide a subdomain.
    host = _IDNA_DOTS.sub('.', unquote(host)).lower()
    # A decoded host may only hold hostname characters: letters (with Indic vowel signs), digits,
    # hyphens and dots. Anything else (a newline, '@', ':', '/', a bidi control) leaves the link out,
    # so no decoded text can reach the family message.
    if not host or not all(c.isalnum() or c in '.-' or unicodedata.category(c) in ('Mn', 'Mc') for c in host):
        return ''
    host = registrable(host.rstrip('.,);!').removeprefix('www.'))
    if _ambiguous(host):
        return ''
    # A registered name can still carry a number, even split by hyphens; leave such a link out.
    # Internationalised names (secure.भारत) are kept.
    if re.search(r'\d{4,}', host) or len(re.findall(r'\d', host)) >= 6:
        return ''
    tld = host.rsplit('.', 1)[-1] if '.' in host else ''
    punycode = re.fullmatch(r'xn--[a-z0-9-]{2,59}', tld)
    if not punycode and (len(tld) < 2 or not all(c.isalpha() or unicodedata.category(c) in ('Mn', 'Mc') for c in tld)):
        return ''
    # Defanged by hand: defang()'s bare-host pattern is ASCII-only, and a Unicode host must not
    # keep a live dot.
    return (('hxxp' + scheme[4:] + '://') if scheme else '') + host.replace('.', '[.]')


# [ \t]* keeps both linear on long runs of blank lines. The value must look like a sender ID or
# number (no spaces), so "from: 10 AM to 11 AM" is not taken for a sender.
_SENDER_LINE = re.compile(r'^[ \t]*(?:from|sender|प्रेषक)[ \t]*[:\-][ \t]*([A-Za-z0-9+@._-]{3,40})[ \t]*$', re.I | re.M)
_DLT = re.compile(r'\A[ \t]*([A-Z]{2}-(?=[A-Z0-9]{0,5}[A-Z])[A-Z0-9]{6}(?:-[SPTG])?)\b')


def sender(text):
    """Sender only when the shared text names it: a From:/Sender: line or a leading DLT header."""
    text = str(text or '')
    m = _SENDER_LINE.search(text) or _DLT.search(text)
    return m.group(1).strip() if m else ''


def medium_key(kind, source=''):
    if source in ('qr', 'whatsapp', 'sms'):
        return source
    if kind == 'upi':
        return 'upi'
    if kind == 'url':
        return 'url'
    return 'sms_or_whatsapp'


_STRINGS = None


def _strings():
    global _STRINGS
    if _STRINGS is None:
        path = Path(__file__).resolve().parent / 'strings_hi.json'
        try:
            _STRINGS = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            _STRINGS = {}
    return _STRINGS


_SLOT = {'n': r'(\d+)', 'count': r'(\d+)', 'tld': r'([A-Za-z0-9]+)', 'host': r"([^\s']+)",
         'reg': r"([^\s']+)", 'ip': r"([^\s']+)", 'brand': r"([^']+)", 'b': r"([^']+)",
         'what': r'(link|text|message)'}


def _template(english):
    names, pat, i = [], ['^'], 0
    while i < len(english):
        if english[i] == '{':
            end = english.find('}', i + 1)
            if end < 0:
                return None
            names.append(english[i + 1:end])
            pat.append(_SLOT.get(names[-1], r'(.+?)'))
            i = end + 1
        else:
            pat.append(re.escape(english[i]))
            i += 1
    pat.append('$')
    return re.compile(''.join(pat)), names


def hindi_line(english):
    """Same lookup order as L10n.t: exact ui, exact evidence, then templates; '' when none."""
    table = _strings()
    line = str(english or '').strip()
    if not line:
        return ''
    for key in ('ui', 'evidence'):
        value = (table.get(key) or {}).get(line)
        if value:
            return value
    rows = [(item.get('en', ''), item.get('hi', '')) for item in table.get('templates') or []]
    rows += [(en, hi) for en, hi in (table.get('evidence') or {}).items() if '{' in en]
    for en, hi in sorted(rows, key=lambda r: -len(r[0])):
        compiled = _template(en) if en and hi else None
        if not compiled:
            continue
        m = compiled[0].match(line)
        if m:
            out = hi
            for idx, name in enumerate(compiled[1]):
                out = out.replace('{' + name + '}', m.group(idx + 1))
            return out
    return ''


def _date(today):
    t = today if today is not None else time.localtime()
    return time.strftime('%d-%m-%Y', t)


def mask(s):
    """Hide 4+ digit runs (OTPs, account and phone numbers) the same way quote_span does."""
    return re.sub(r'(?<!\d)\d{4,}(?!\d)', lambda m: '•' * len(m.group(0)), str(s or ''))


def _quote(q, seen):
    # UPI quotes come straight from the parsed payload, so they are masked here as well.
    q = mask(defang(str(q or '').strip().replace('"', "'")))
    if not q or q in seen:
        return ''
    seen.add(q)
    return f': "{q}"'


def report_text(lang, kind, text, scam, evidence, quotes, source='', today=None, cid=None):
    hi = lang == 'hi'
    cid = cid or category(kind, text, scam)
    en_name, hi_name = _NAMES[cid]
    med = MEDIUM[medium_key(kind, source)]
    who = sender(text)
    lines = ['संदिग्ध धोखे की रिपोर्ट (Sanchar Saathi Chakshu के लिए)' if hi
             else 'Suspected fraud report (for Sanchar Saathi Chakshu)']
    lines.append(('माध्यम: ' if hi else 'Medium: ') + (med[1] if hi else med[0]))
    lines.append(f'श्रेणी: {hi_name} ({en_name})' if hi else f'Category: {en_name}')
    if who:
        lines.append(('भेजने वाला: ' if hi else 'Sender: ') + defang(who))
    lines.append(('जांच की तारीख: ' if hi else 'Checked on: ') + _date(today))
    if scam:
        lines.append(('प्रकार: ' if hi else 'Type: ') + ((hindi_line(scam) or scam) if hi else scam))
    shown = [(e, (quotes or [])[i] if i < len(quotes or []) else '')
             for i, e in enumerate(evidence or []) if str(e or '').strip()][:3]
    if shown:
        lines.append('संकेत:' if hi else 'Evidence:')
        seen = set()
        for line, quote in shown:
            words = (hindi_line(line) or line) if hi else line
            lines.append(f'- {mask(defang(words))}{_quote(quote, seen)}')
    lines.append('इस फ़ोन पर Prahari से ऑफ़लाइन जांचा गया। कुछ भी भेजा नहीं गया।' if hi
                 else 'Checked offline on this phone by Prahari. Nothing was sent.')
    lines.append(LOST_MONEY[1] if hi else LOST_MONEY[0])
    return '\n'.join(lines)


def family_text(lang, kind, text, scam, lab=1, source='', cid=None):
    """Short warning to forward. Never the message body, sender, numbers or names.

    It speaks only about the one checked item: "flagged as a scam" for DANGEROUS, "may be a scam"
    for SUSPICIOUS."""
    hi = lang == 'hi'
    cid = cid or category(kind, text, scam)
    what_en, step_en, what_hi, step_hi = FAMILY['upi' if kind == 'upi' else cid]
    key = medium_key(kind, source)
    # A link or UPI item already says what it is; only a message or QR names how it arrived.
    med = FAMILY_MEDIUM[key] if key not in ('url', 'upi') else ('', '')
    link = link_origin(text)
    sure = lab == 1
    if hi:
        noun = f" ({MEDIUM[key][1].removesuffix(' मैसेज')})" if med[0] else ''
        head = (f'ठगी की चेतावनी: {what_hi}{noun}। Prahari ने इसे ठगी बताया।' if sure
                else f'सावधान: {what_hi}{noun}। यह ठगी हो सकती है।')
        parts = [head, step_hi]
        if link:
            parts.append(f'यह लिंक न खोलें: {link}')
        parts.append('पैसे चले गए हों तो तुरंत 1930 पर कॉल करें।')
    else:
        how = f' {med[0]}' if med[0] else ''
        head = (f'Scam warning: I got a {what_en}{how}. Prahari flagged it as a scam.' if sure
                else f'Be careful: I got a {what_en}{how}. It may be a scam.')
        parts = [head, step_en]
        if link:
            parts.append(f'Do not open this link: {link}')
        parts.append('If money is lost, call 1930 at once.')
    return '\n'.join(parts)


def card(kind, text, lab, scam, evidence, quotes, source='', today=None, raised=False):
    """Report card for a SCAM or SUSPICIOUS message or link result, or None.

    An ordinary bank debit alert gets none: it is something to confirm in the bank app, not a
    fraud report. raised=True is the card for an alert the app shows as SUSPICIOUS because it
    names its own link or number (MainActivity.bankAlertLevel)."""
    if kind == 'flow':
        return None
    if raised:
        # The detector's benign reading is not shown for a raised alert, so it is not reported.
        scam, lab, evidence, quotes = DEBIT_ALERT, 'uncertain', [RAISED_EVIDENCE], []
    elif lab == 0 or scam == DEBIT_ALERT:
        return None
    cid = category(kind, text, scam)
    en_name, hi_name = _NAMES[cid]
    return {
        'category': cid, 'category_en': en_name, 'category_hi': hi_name,
        'report_en': report_text('en', kind, text, scam, evidence, quotes, source, today, cid),
        'report_hi': report_text('hi', kind, text, scam, evidence, quotes, source, today, cid),
        'family_en': family_text('en', kind, text, scam, lab, source, cid),
        'family_hi': family_text('hi', kind, text, scam, lab, source, cid),
    }
