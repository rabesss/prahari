"""Report card and family warning: Chakshu categories, defanging, templates and privacy."""
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'candidates/BEST'), str(ROOT / 'android/python')]
import report_card as rc  # noqa: E402

DAY = time.strptime('2026-11-24', '%Y-%m-%d')

# The official list, Sanchar Saathi FAQ "What is suspected fraud communication?" i-xi.
OFFICIAL = [
    'Investment, Stock Market and Trading',
    'Impersonation as DoT / TRAI',
    'Impersonation as Police, CBI, Customs, Aadhaar, RBI etc',
    'Impersonation as a relative / friend',
    'KYC and Payment related to Bank / Electricity / Gas / Insurance etc',
    'Fake Customer Care Helpline',
    'Online job/ gift/ lottery / loans offers',
    'IVR / Robo Calls',
    'Sextortion',
    'Suspected link/ website',
    'Any Other Suspected Fraud',
]
assert [en for _, en, _ in rc.CHAKSHU] == OFFICIAL
assert all(hi.strip() for _, _, hi in rc.CHAKSHU)
assert set(rc.FAMILY) == {cid for cid, _, _ in rc.CHAKSHU} | {'upi'}
print('official Chakshu category names passed')

# One fixture per category, from detector scam-type phrases and text cues.
CASES = [
    ('investment', 'sms', 'Join our VIP group, guaranteed 3x returns on stock trading', 'an investment or trading scam'),
    ('dot_trai', 'sms', 'TRAI notice: your SIM will be blocked in 2 hours, press 9 to talk to officer',
     'an account-blocking threat'),
    ('police_govt', 'sms', 'This is CBI. A parcel in your name has drugs, you are under digital arrest',
     'a fake police or customs threat'),
    ('relative', 'sms', 'Papa this is my new number, phone kharab, send 20000 to my friend urgently',
     'an impersonation scam'),
    ('kyc_payment', 'sms', 'Dear customer your SBI KYC is expiring, update at http://sbi-kyc.in-verify.top',
     'a fake KYC or account check'),
    ('customer_care', 'sms', 'Flipkart customer care: install AnyDesk so our support executive can process refund',
     'a remote-access app scam'),
    ('job_offer', 'sms', 'Part time job, earn Rs 5000 daily by liking videos, pay Rs 500 registration',
     'a fake job or task scam'),
    ('ivr', 'sms', 'Recorded message: press 1 now to stop the deduction', 'a scam message'),
    ('sextortion', 'sms', 'I have your private video, pay or I send it to your contacts', 'sextortion or blackmail'),
    ('link', 'url', 'http://amaz0n-refund-help.top/claim', 'a phishing link on a lookalike domain'),
    ('other', 'sms', 'Reply YES to confirm', 'a scam message'),
]
for want, kind, text, scam in CASES:
    got = rc.category(kind, text, scam)
    assert got == want, (want, got, text)

# Every UPI scam type is a payment category.
for scam in ('a UPI AutoPay mandate scam', 'a UPI refund or receive-money QR scam', 'a UPI collect-request QR scam',
             'a UPI KYC or impersonation QR scam', 'a UPI QR payment scam', 'a UPI payment QR worth checking'):
    assert rc.category('upi', 'upi://pay?pa=x@ybl', scam) == 'kyc_payment', scam

# A mechanism phrase alone does not name a category: context decides, else "other".
assert rc.category('sms', 'Pay 50000 or we will hurt your family', 'an extortion threat') == 'other'
assert rc.category('sms', 'Send USDT to this wallet to unlock your account', 'a crypto payment scam') == 'other'
assert rc.category('sms', 'Double your money: invest in our crypto trading plan', 'a crypto payment scam') == 'investment'
assert rc.category('sms', 'Your parcel is held at customs, pay Rs 1500 fee', 'an advance-fee scam') == 'police_govt'
assert rc.category('sms', 'Courier delivery: pay 99 rupees fee to release your parcel now', 'an advance-fee scam') == 'other'
assert rc.category('sms', 'You won a lucky draw, pay Rs 999 to release the prize', 'an advance-fee scam') == 'job_offer'
assert rc.category('sms', 'Pay Rs 999 processing fee today', 'an advance-fee scam') == 'other'
assert rc.category('sms', 'Install AnyDesk, your bank account will be blocked', 'a remote-access app scam') == 'kyc_payment'
assert rc.category('sms', 'Install AnyDesk now', 'a remote-access app scam') == 'other'
assert rc.category('sms', 'Buy 5 Google Play cards and send me the codes, I am in a meeting', 'a gift-card scam') == 'other'
# Priority: sextortion wording beats a police phrase; police plus safe account stays police.
assert rc.category('sms', 'Police case: your nude video, pay now', 'a fake police or customs threat') == 'sextortion'
assert rc.category('sms', 'RBI officer: move funds to a safe account', 'a safe-account transfer scam') == 'police_govt'
assert rc.category('sms', 'Call SBI customer care 9876543210 to unblock your KYC', 'a fake KYC or account check') == \
    'customer_care'
print('Chakshu category mapping passed')

# Defang.
assert rc.defang('http://sbi-kyc.in-verify.top/a?b=1') == 'hxxp://sbi-kyc[.]in-verify[.]top/a?b=1'
assert rc.defang('see https://x.co now') == 'see hxxps://x[.]co now'
assert rc.defang('www.evil.top') == 'www[.]evil[.]top'
assert rc.defang('the domain sbi-kyc.top imitates') == 'the domain sbi-kyc[.]top imitates'
assert rc.defang('Rs.2,450 e.g. 9:30') == 'Rs.2,450 e.g. 9:30'
once = rc.defang('http://a.b.top and c.d.in')
assert rc.defang(once) == once, once
assert rc.link_origin('Open http://Sbi-KYC.top/verify?mob=9876543210&name=Asha now') == 'hxxp://sbi-kyc[.]top'
assert rc.link_origin('go to www.evil.top/x?id=1') == 'evil[.]top'
assert rc.link_origin('http://user:pw@evil.top:8080/x') == 'hxxp://evil[.]top'
assert rc.link_origin('http://asha.9876543210.evil.top/') == 'hxxp://evil[.]top'  # subdomains are dropped
assert rc.link_origin('https://alice-smith.98-76-54-32-10.example.com/reset') == 'hxxps://example[.]com'
assert rc.link_origin('http://x.sbl-help.co.in/a') == 'hxxp://sbl-help[.]co[.]in'
assert rc.link_origin('http://x.sbi.co.in/a') == ''  # only official links: nothing to avoid
assert rc.link_origin('http://98765-43210.top/') == ''  # a number in the registered name itself
assert rc.link_origin('no link here') == ''
assert rc.link_origin('http://x%0Aupi%3A%2F%2Fpay%3Fpa%3Drahul%40ybl.com') == ''  # decoded newline/URL
assert rc.link_origin('https://asha%40gmail.com/phish') == ''  # decoded '@'
assert rc.link_origin('https://evil%E2%80%AE.top/x') == ''  # decoded bidi override
assert rc.link_origin('https://asha.com.in/kyc') == ''  # com.in is not a listed suffix: left out
for _odd in ('http://x%0Aupi%3A%2F%2Fpay%3Fpa%3Drahul%40ybl.com', 'https://asha%40gmail.com/phish'):
    _fam = rc.family_text('en', 'sms', 'Pay now ' + _odd, 'a fake payment request', 1)
    assert '@' not in _fam and 'upi://' not in _fam and 'asha' not in _fam and 'rahul' not in _fam, _fam
assert rc.link_origin('https://asha。evil.top/x') == 'hxxps://evil[.]top'  # IDNA dot
assert rc.link_origin('https://asha%2Eevil.top/x') == 'hxxps://evil[.]top'  # percent-encoded dot
assert rc.link_origin('https://secure.xn--h2brj9c/verify') == 'hxxps://secure[.]xn--h2brj9c'  # punycode TLD
assert rc.link_origin('https://pay.evil.com.tr/x') == ''  # unlisted two-part suffix: left out
assert rc.link_origin('https://asha.gov.de/x') == ''  # gov.de may be registrable: left out, never asha
assert rc.link_origin('https://sbi%2Eco%2Ein/ then http://sbi-kyc.top/x') == 'hxxp://sbi-kyc[.]top'  # official after normalising
assert rc.link_origin('https://sbi\u3002co\u3002in/ then http://sbi-kyc.top/x') == 'hxxp://sbi-kyc[.]top'
assert rc.link_origin('www.नाम%2Eभारत/x') == 'नाम[.]भारत'  # scheme-less Unicode host has no live dot
assert rc.link_origin('http://98-765-432-10.evil.top/x') == 'hxxp://evil[.]top'  # numbered subdomain dropped
assert rc.link_origin('http://98-765-432-10.top/x') == ''  # a number split by hyphens in the name
assert rc.link_origin('https://secure.भारत/verify') == 'hxxps://secure[.]भारत'  # IDN kept
assert rc.mask('OTP 123456 to 9876543210, Rs 499') == 'OTP •••••• to ••••••••••, Rs 499'
print('defanging passed')

# Sender only when given; medium from the source hint.
assert rc.sender('From: VM-SBIBNK\nYour KYC expires') == 'VM-SBIBNK'
assert rc.sender('AD-HDFCBK-S Your card is blocked') == 'AD-HDFCBK-S'
assert rc.sender('Dear customer, update KYC') == ''
assert rc.medium_key('sms', 'whatsapp') == 'whatsapp'
assert rc.medium_key('sms', '') == 'sms_or_whatsapp'
assert rc.medium_key('upi', 'qr') == 'qr'
assert rc.medium_key('url', '') == 'url'

KYC = 'From: VM-SBIBNK\nDear Asha, your SBI KYC is expiring. OTP 482910. Update at http://sbi-kyc.in-verify.top/u?m=9876543210'
EV = ['asks you to share or enter an OTP, PIN or CVV',
      'the domain sbi-kyc.in-verify.top imitates \'sbi\' on .top',
      'says your KYC must be updated or your account will be blocked',
      'a fourth line that is not shown']
QUOTES = ['OTP ••••••', 'hxxp://sbi-kyc[.]in-verify[.]top/u?m=••••••…', '', '']
report = rc.report_text('en', 'sms', KYC, 'a fake KYC or account check', EV, QUOTES, 'sms', DAY)
lines = report.splitlines()
assert lines[0] == 'Suspected fraud report (for Sanchar Saathi Chakshu)'
assert 'Medium: SMS' in lines
assert 'Category: KYC and Payment related to Bank / Electricity / Gas / Insurance etc' in lines
assert 'Sender: VM-SBIBNK' in lines
assert 'Checked on: 24-11-2026' in lines
assert 'Type: a fake KYC or account check' in lines
assert lines[-1] == 'Already lost money? Call 1930 / cybercrime.gov.in'
assert 'a fourth line' not in report  # three evidence lines at most
assert 'sbi-kyc[.]in-verify[.]top' in report and 'http://' not in report and 'https://' not in report
assert '482910' not in report and '9876543210' not in report
assert not re.search(r'(?<![\d-])\d{4,}(?!\d)', report.replace('24-11-2026', '').replace('1930', ''))
hi_report = rc.report_text('hi', 'sms', KYC, 'a fake KYC or account check', EV, QUOTES, 'sms', DAY)
assert 'श्रेणी:' in hi_report and '(KYC and Payment related to Bank / Electricity / Gas / Insurance etc)' in hi_report
assert 'नकली KYC या खाता जांच' in hi_report  # scam type from the bundled Hindi table
assert 'पैसे चले गए? 1930 पर कॉल करें / cybercrime.gov.in' in hi_report
assert 'http://' not in hi_report
# UPI quotes come raw from the payload: the report masks them too.
upi_report = rc.report_text('en', 'upi', 'upi://pay?pa=9876543210@ybl&tn=share%20OTP%20123456', 'a UPI QR payment scam',
                            ['the UPI ID 9876543210@ybl is a personal number', 'the note asks for a PIN or OTP'],
                            ['pa=9876543210@ybl', 'share OTP 123456 for refund'], 'qr', DAY)
assert '123456' not in upi_report and '9876543210' not in upi_report, upi_report
assert 'Medium: QR code' in upi_report
_url_from = rc.report_text('en', 'sms', 'From: https://fraud.example\nPay now', 'a scam message', [], [])
assert 'https://' not in _url_from and 'fraud.example' not in _url_from
assert rc.sender('Meeting\nfrom: 10 AM to 11 AM') == ''
assert rc.sender('ID-123456 is your ID') == ''
assert rc.sender('From: +919812345678\nPay now') == '+919812345678'
_t0 = time.perf_counter(); rc.sender('\n' * 20000 + 'x'); assert time.perf_counter() - _t0 < 0.5
# The family link skips an official link quoted before the scam one.
assert rc.link_origin('Details at www.onlinesbi.sbi. To update call or http://sbi-kyc-update.top/x') == 'hxxp://sbi-kyc-update[.]top'
# A bank scam that only quotes a helpline stays a bank scam; a support desk makes it customer care.
assert rc.category('sms', 'Your SBI account will be blocked, update KYC. Toll free 1800112211', 'an account-blocking scam') == 'kyc_payment'
assert rc.category('sms', 'Bank customer care: share OTP to unblock', 'OTP or PIN theft') == 'customer_care'
assert rc.card('sms', 'SBI debit. For helpline call 9876543210', 0, '', [], [], raised=True)['category'] == 'kyc_payment'
assert '(SMS या WhatsApp)' in rc.family_text('hi', 'sms', 'Update KYC http://a-b.top', 'a fake KYC or account check', 1)
print('report template passed')

# Family message: no body, sender, name, numbers, path or query; cautious for SUSPICIOUS.
for lang in ('en', 'hi'):
    for lab in (1, 'uncertain'):
        fam = rc.family_text(lang, 'sms', KYC, 'a fake KYC or account check', lab, 'sms')
        for leak in ('Asha', 'VM-SBIBNK', '482910', '9876543210', '/u', 'm=', 'OTP 4', 'Dear'):
            assert leak not in fam, (leak, fam)
        assert 'hxxp://in-verify[.]top' in fam and 'sbi-kyc' not in fam
        assert '1930' in fam
        assert len(fam) < 400, len(fam)
assert rc.family_text('en', 'sms', KYC, 'a fake KYC or account check', 1).startswith('Scam warning: I got a fake bank, KYC or bill payment message')
assert 'may be a scam' in rc.family_text('en', 'sms', KYC, 'a fake KYC or account check', 'uncertain')
assert 'ठगी हो सकती है' in rc.family_text('hi', 'sms', KYC, 'a fake KYC or account check', 'uncertain')
assert 'Prahari ने इसे ठगी बताया' in rc.family_text('hi', 'sms', KYC, 'a fake KYC or account check', 1)
assert 'as a link' not in rc.family_text('en', 'url', 'http://amaz0n.top', 'a phishing link', 1)
assert 'UPI PIN' in rc.family_text('en', 'upi', 'upi://pay?pa=refund@ybl&am=4999', 'a UPI QR payment scam', 1)
assert 'refund@ybl' not in rc.family_text('en', 'upi', 'upi://pay?pa=refund@ybl&am=4999', 'a UPI QR payment scam', 1)
for cid in rc.FAMILY:
    what_en, step_en, what_hi, step_hi = rc.FAMILY[cid]
    assert all(x.strip() for x in (what_en, step_en, what_hi, step_hi)), cid
    assert re.search('[ऀ-ॿ]', what_hi + step_hi), cid
print('family template passed')

# Eligibility.
assert rc.card('sms', KYC, 0, '', EV, QUOTES) is None
assert rc.card('flow', 'port scan', 1, 'a port scan', [], []) is None
assert rc.card('sms', 'SBI: Rs 2,450 debited', 'uncertain', rc.DEBIT_ALERT, [], []) is None
raised = rc.card('sms', 'SBI: Rs 2,450 debited. Not you? call 9876543210', 0, '',
                 ['reads like a routine transaction receipt or delivery update'], [''], raised=True)
assert raised and raised['category'] == 'kyc_payment'
assert rc.RAISED_EVIDENCE in raised['report_en'] and 'routine' not in raised['report_en']
assert 'may be a scam' in raised['family_en']
card = rc.card('sms', KYC, 1, 'a fake KYC or account check', EV, QUOTES, 'whatsapp', DAY)
assert set(card) == {'category', 'category_en', 'category_hi', 'report_en', 'report_hi', 'family_en', 'family_hi'}
assert 'Medium: WhatsApp' in card['report_en']
kt = (ROOT / 'android/app/src/main/java/in/prahari/app/MainActivity.kt').read_text(encoding='utf-8')
assert f'private const val OWN_CONTACT_LINE = "{rc.RAISED_EVIDENCE}"' in kt
print('report card eligibility passed')

# Bundled strings for the two buttons, in both languages.
hi = json.loads((ROOT / 'android/python/strings_hi.json').read_text(encoding='utf-8'))
for key in ('report_copy', 'report_copy_desc', 'report_copied', 'report_copy_fail', 'family_send',
            'family_send_desc', 'family_chooser'):
    item = hi['new'][key]
    assert item['en'].strip() and re.search('[ऀ-ॿ]', item['hi']), key
    assert f'"{key}"' in kt, key
assert hi['new']['family_send']['hi'] == 'परिवार को बताएं'
# No permission, network or contacts access was added for this.
manifest = (ROOT / 'android/app/src/main/AndroidManifest.xml').read_text(encoding='utf-8')
assert 'uses-permission' not in manifest
assert 'READ_CONTACTS' not in kt and 'Intent.ACTION_SEND' in kt and 'EXTRA_EXCLUDE_COMPONENTS' in kt
print('button strings and permissions passed')
