"""Screen-sharing app banner: when it is asked for, and the package list it may look up."""
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'candidates/BEST'), str(ROOT / 'android/python')]
import remote_apps as ra  # noqa: E402
from triage import llm  # noqa: E402

# Verified on Google Play (HTTP 200 listing) on 24 Nov 2026, except RustDesk (F-Droid + upstream applicationId).
VERIFIED = {
    'com.anydesk.anydeskandroid', 'com.teamviewer.quicksupport.market', 'com.teamviewer.host.market',
    'com.teamviewer.teamviewer.market.mobile', 'com.carriez.flutter_hbb', 'com.sand.airdroid',
    'com.sand.airsos', 'com.sand.aircast',
}
A = '{http://schemas.android.com/apk/res/android}'
manifest = ET.parse(ROOT / 'android/app/src/main/AndroidManifest.xml').getroot()
queries = [x.get(A + 'name') for x in manifest.findall('./queries/package')]
kt = (ROOT / 'android/app/src/main/java/in/prahari/app/RemoteApps.kt').read_text(encoding='utf-8')
kt_pkgs = re.findall(r'"([a-z0-9_.]+)" to "', kt)
assert queries and len(queries) == len(set(queries))
assert queries == kt_pkgs, (queries, kt_pkgs)
assert set(queries) == VERIFIED
assert not manifest.findall('./uses-permission'), 'no permission is needed for named package queries'
assert not manifest.findall('./queries/intent')
assert 'QUERY_ALL_PACKAGES' not in (ROOT / 'android/app/src/main/AndroidManifest.xml').read_text()
main = (ROOT / 'android/app/src/main/java/in/prahari/app/MainActivity.kt').read_text(encoding='utf-8')
assert 'getInstalledPackages' not in main + kt and 'getInstalledApplications' not in main + kt
assert 'RemoteApps.installed(' in main and 'n("remote_app_banner")' in main
print('remote app package list and manifest passed')

# The detector's own rule is reused, not copied.
assert ra.REMOTE_APP.pattern == next(p for n, p, _ in ra.rules.TEXT_RULES if n == 'remote_app')

CASES = [
    # (expected, kind, text, lab, scam, actions)
    (True, 'sms', 'Install AnyDesk so our executive can fix your refund', 1, 'a remote-access app scam', []),
    (True, 'sms', 'Download quicksupport and share the code', 'uncertain', 'a scam message', []),
    (True, 'sms', 'Dear customer your SBI KYC is expiring, update at http://sbi-kyc.top', 1, 'a fake KYC or account check', []),
    (True, 'sms', 'Share the OTP to stop the debit', 1, 'OTP or PIN theft', []),
    (True, 'sms', 'Call Amazon customer care 9876543210 for refund', 'uncertain', 'a scam message', []),
    (True, 'upi', 'upi://pay?pa=refund@ybl&am=4999', 1, 'a UPI refund or receive-money QR scam', []),
    (True, 'sms', 'SBI: Rs 2,450 debited via UPI', 'uncertain', 'a bank debit alert to confirm', [llm.DEBIT_STEP]),
    (False, 'sms', 'SBI: Rs 2,450 debited via UPI', 0, '', [llm.DEBIT_STEP]),  # NO RISK: no banner
    (False, 'sms', 'Delivered: Your order #4412 has been delivered. Thank you for shopping.', 0, '', [llm.DEBIT_STEP]),
    (True, 'sms', 'यूपीआई से 4999 रुपये भेजें इस नंबर पर 9876543210', 1, 'a payment fraud', []),
    (False, 'sms', 'Hi Bob, I have your private video, pay or I leak it', 1, 'sextortion or blackmail', []),
    (False, 'sms', 'Part time job, earn Rs 5000 daily liking videos', 1, 'a fake job or task scam', []),
    (True, 'url', 'http://sbi-kyc.top/login', 1, 'a phishing link on a lookalike domain', []),
    (True, 'sms', 'Your SBI bank account has been compromised call 9876543210 immediately', 1, 'a scam message', []),
    (False, 'sms', 'your electricity connection will be disconnected, pay Rs 500 immediately', 1,
     'an electricity disconnection scam', []),
    (False, 'sms', 'I have your private video, pay or I leak it', 1, 'sextortion or blackmail', []),
    (False, 'url', 'http://netf1ix-login.top/verify', 1, 'a phishing link on a lookalike domain', []),
    (True, 'url', 'http://amaz0n-refund-help.top/claim', 1, 'a phishing link on a lookalike domain', []),
    (False, 'sms', 'Your OTP for login is 123456. Do not share it.', 0, '', []),
    (False, 'sms', 'Install AnyDesk from the official site for our office laptops', 0, '', []),
    (False, 'flow', 'remote desktop traffic to many hosts', 1, 'suspicious network traffic', []),
]
for want, kind, text, lab, scam, actions in CASES:
    got = ra.needs_check(kind, text, lab, scam, actions)
    assert got is want, (want, got, text)
print('remote app check conditions passed')

hi = json.loads((ROOT / 'android/python/strings_hi.json').read_text(encoding='utf-8'))
item = hi['new']['remote_app_banner']
assert item['en'] == ("A screen-sharing app ({apps}) is installed. Scammers use these to watch your bank app. "
                      "Uninstall it if a 'support agent' asked you to install it.")
assert '{apps}' in item['hi'] and re.search('[ऀ-ॿ]', item['hi'])
print('remote app banner strings passed')
