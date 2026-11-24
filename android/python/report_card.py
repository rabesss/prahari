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
from pathlib import Path

# id, official English name, Hindi name. Order is the FAQ order.
CHAKSHU = (
    ('investment', 'Investment, Stock Market and Trading', 'निवेश, शेयर बाज़ार और ट्रेडिंग'),
    ('dot_trai', 'Impersonation as DoT / TRAI', 'DoT / TRAI बनकर धोखा'),
    ('police_govt', 'Impersonation as Police, CBI, Customs, Aadhaar, RBI etc',
     'पुलिस, CBI, कस्टम, आधार, RBI आदि बनकर धोखा'),
    ('relative', 'Impersonation as a relative / friend', 'रिश्तेदार / दोस्त बनकर धोखा'),
    ('kyc_payment', 'KYC and Payment related to Bank / Electricity / Gas / Insurance etc',
     'बैंक / बिजली / गैस / बीमा आदि से जुड़ा KYC और भुगतान'),
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
_CARE = re.compile(r'customer (?:care|support|service)|helpline|help desk|support (?:team|executive|agent)|toll[- ]free|'
                   r'कस्टमर केयर', re.I)
_IVR = re.compile(r'\bivr\b|press \d|dabay?e|दबाएं|recorded (?:message|call)|robo ?call', re.I)
_JOB = re.compile(r'\b(?:job|salary|loan|lottery|prize|gift|reward|work from home|part[- ]time|task|lucky draw|kbc)\b|'
                  r'नौकरी|लोन|लॉटरी|इनाम', re.I)
_INVEST = re.compile(r'\b(?:invest\w*|trading|stock|share market|ipo|returns?|profit|double)\b|निवेश|मुनाफ़ा|मुनाफा', re.I)
_PARCEL = re.compile(r'\b(?:customs|courier|parcel|fedex|dhl|india post|shipment)\b|पार्सल|कस्टम', re.I)
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
        if base == 'kyc_payment' and _CARE.search(text):
            return 'customer_care'
        return base
    # A mechanism phrase or a generic one: only text context names the category.
    if _POLICE.search(text) and _THREAT.search(text):
        return 'police_govt'
    if scam == 'an advance-fee scam' and _PARCEL.search(text):
        return 'police_govt'  # customs or courier fee: impersonates customs
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


def link_origin(text):
    """First link in the text as scheme and host only, defanged. No path or query: those can
    carry the reader's own id or number."""
    m = re.search(r'(?i)\b(https?)://([^\s/?#<>"\']+)|\bwww\.([^\s/?#<>"\']+)', str(text or ''))
    if not m:
        return ''
    if m.group(1):
        host = m.group(2).split('@')[-1].split(':')[0]
        origin = f'{m.group(1).lower()}://{host.lower()}'
    else:
        origin = 'www.' + m.group(3).split(':')[0].lower()
    origin = origin.rstrip('.,);!')
    # A personalised host can carry a phone or account number; leave such a link out.
    if re.search(r'\d{4,}', origin) or not _HOST.search(origin):
        return ''
    return defang(origin)


_SENDER_LINE = re.compile(r'^\s*(?:from|sender|प्रेषक)\s*[:\-]\s*([^\n]{2,40})$', re.I | re.M)
_DLT = re.compile(r'^\s*([A-Z]{2}-[A-Z0-9]{6}(?:-[SPTG])?)\b')


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


def _quote(q, seen):
    q = defang(str(q or '').strip().replace('"', "'"))
    if not q or q in seen:
        return ''
    seen.add(q)
    return f': "{q}"'


def report_text(lang, kind, text, scam, evidence, quotes, source='', today=None):
    hi = lang == 'hi'
    cid = category(kind, text, scam)
    en_name, hi_name = _NAMES[cid]
    med = MEDIUM[medium_key(kind, source)]
    who = sender(text)
    lines = ['संदिग्ध धोखे की रिपोर्ट (Sanchar Saathi Chakshu के लिए)' if hi
             else 'Suspected fraud report (for Sanchar Saathi Chakshu)']
    lines.append(('माध्यम: ' if hi else 'Medium: ') + (med[1] if hi else med[0]))
    lines.append(f'श्रेणी: {hi_name} ({en_name})' if hi else f'Category: {en_name}')
    if who:
        lines.append(('भेजने वाला: ' if hi else 'Sender: ') + who)
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
            lines.append(f'- {defang(words)}{_quote(quote, seen)}')
    lines.append('इस फ़ोन पर Prahari से ऑफ़लाइन जांचा गया। कुछ भी भेजा नहीं गया।' if hi
                 else 'Checked offline on this phone by Prahari. Nothing was sent.')
    lines.append(LOST_MONEY[1] if hi else LOST_MONEY[0])
    return '\n'.join(lines)


def family_text(lang, kind, text, scam, lab=1, source=''):
    """Short warning to forward. Never the message body, sender, numbers or names.

    It speaks only about the one checked item: "flagged as a scam" for DANGEROUS, "may be a scam"
    for SUSPICIOUS."""
    hi = lang == 'hi'
    cid = category(kind, text, scam)
    what_en, step_en, what_hi, step_hi = FAMILY['upi' if kind == 'upi' else cid]
    key = medium_key(kind, source)
    # A link or UPI item already says what it is; only a message or QR names how it arrived.
    med = FAMILY_MEDIUM[key] if key not in ('url', 'upi') else ('', '')
    link = link_origin(text)
    sure = lab == 1
    if hi:
        noun = f' ({MEDIUM[key][1]})' if med[0] else ''
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
        'report_en': report_text('en', kind, text, scam, evidence, quotes, source, today),
        'report_hi': report_text('hi', kind, text, scam, evidence, quotes, source, today),
        'family_en': family_text('en', kind, text, scam, lab, source),
        'family_hi': family_text('hi', kind, text, scam, lab, source),
    }
