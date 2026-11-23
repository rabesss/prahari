import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'candidates/BEST'), str(ROOT/'android/python')]
# Chaquopy installs only NumPy: block the desktop-only packages so an import of
# any of them fails here as it would on the phone.
import intake
assert intake.detect_mode('http://amaz0n-refund-help.top/claim') == 1
assert intake.detect_mode('  https://www.irctc.co.in/nget/train-search  ') == 1
assert intake.detect_mode('upi://pay?pa=refund@ybl&am=5000') == 1
assert intake.detect_mode('www.example.com/path') == 1
assert intake.detect_mode('Dear customer your SBI KYC is expiring, update at http://sbi-kyc.in-verify.top or the account will be blocked') == 0
assert intake.detect_mode('Aapka bijli connection aaj raat 9:30 kat jayega. Turant 98XXXXXX12 par call karein ya http://uppcl-bill-pay.top kholein.') == 0
assert intake.detect_mode('see https://example.com please') == 0
assert intake.detect_mode('tcp connections to 200 different ports on 10.0.0.5 within 10 seconds, all rejected') == 2
assert intake.detect_mode('{"num_failed_logins": 4, "serror_rate": 1}') == 2
assert intake.detect_mode('') == 0
assert intake.detect_mode('{not json}') == 0
print('share-text mode detection passed')

hi = json.loads((ROOT / 'android/python/strings_hi.json').read_text(encoding='utf-8'))
assert set(hi) >= {'ui', 'evidence', 'skip', 'new'}
assert isinstance(hi['ui'], dict) and hi['ui']['Check on this phone']
assert isinstance(hi['evidence'], dict) and '{host}' in next(k for k in hi['evidence'] if '{' in k)
assert isinstance(hi['skip'], list) and hi['skip']
for key, item in hi['new'].items():
    assert 'en' in item and 'hi' in item, key
print('hindi string table shape passed')

for blocked in ('joblib', 'sklearn', 'scipy', 'pandas', 'torch', 'executorch'):
    sys.modules[blocked] = None
import mobile
mobile.portable.ROOT = ROOT / 'android/build/generated/python/models'  # exported by CI first
class Fake:
    def __init__(self, replies): self.replies = iter(replies); self.prompts=[]
    def generate(self, prompt):
        self.prompts.append(prompt)
        return json.dumps({'text':next(self.replies),'stats':{'first_token_ms': 9}})
runner = Fake(["I'm sorry, I cannot help.", 'This message is DANGEROUS. It asks for an OTP.'])
e = mobile.BridgeExplainer(runner)
p = e.prompt('sms', 'Share your OTP at https://example.com', 1, ['asks for an OTP'])
text, stats = e.generate(p)
assert len(runner.prompts) == 2 and stats['retried'] and 'OTP' in text
assert 'https://example[.]com' in p and 'Verdict: DANGEROUS' in p
runner = Fake(["I cannot help.", "I cannot help.", "This message is DANGEROUS. It asks for an OTP."])
e = mobile.BridgeExplainer(runner)
text, stats = e.generate(p)
assert len(runner.prompts) == 3 and stats['evidence_only'] and 'Share your OTP' not in runner.prompts[-1]
print('fake bridge: prompt, retry and evidence-only fallback passed')

android_fake = Fake(['This is a test.'])
_, stats = mobile.BridgeExplainer(android_fake)._run('prompt')
assert stats['first_token_ms'] == 9
print('Android bridge TTFT field is the callback duration')

# Hindi lines are a parallel list. A missing English step stays blank, not a guess.
hi = mobile._actions_hi([
    'Do not click the link or reply to the message.',
    'This step is not in the table.',
])
assert hi == ['लिंक पर क्लिक न करें और मैसेज का जवाब न दें।', '']
assert mobile._actions_hi([mobile.llm.DEBIT_STEP])[0].startswith('पेमेंट आपका नहीं')

# Link evidence: brand imitation or a digit swap leads; everything else keeps detector order.
link_ev = [
    'the domain ends in .top, common for throwaway scam sites',
    'the domain amaz0n-refund-help.top is unusually long or hyphenated',
    'the domain amaz0n-refund-help.top swaps letters for digits to imitate a brand',
    'the link does not use HTTPS',
]
led = mobile._promote_link_signals(link_ev)
assert led[0] == link_ev[2] and led[1:] == [link_ev[0], link_ev[1], link_ev[3]]
brand = [
    'the link does not use HTTPS',
    "the domain pay.sbi-secure.top uses the name 'sbi' but is not that company's official site",
]
assert mobile._promote_link_signals(brand)[0] == brand[1]
assert mobile._promote_link_signals(['no HTTPS']) == ['no HTTPS']

# NO RISK evidence is the benign reading, never the overruled threat phrase.
from triage import mech
bank = ('SBI: Rs 2,450 debited via UPI. OTP 482910 kisi se share mat karein. '
        'If not you, block card in YONO app.')
raw = mech.evidence(mech.analyze(bank))
cleared = mobile.llm.benign_evidence('sms', bank, raw, 0)
assert cleared and not any('threaten' in line or 'block the account' in line for line in cleared)
assert mobile.llm.benign_evidence('sms', bank, ['threatens to block'], 1) == ['threatens to block']

# Report buttons follow the Hindi table's rules. Suspicious and network events have no pair.
chakshu = mobile._report_buttons('sms', 1, 'a fake KYC or account check', ['Do not open the link.'])
assert chakshu['primary']['id'] == 'report_chakshu' and chakshu['secondary']['id'] == 'lost_money_1930'
assert chakshu['primary']['en'] == 'Report on Sanchar Saathi Chakshu'
look = mobile._report_buttons('url', 1, 'a phishing link on a lookalike domain', ['Do not open the link.'])
assert look['primary']['id'] == 'report_chakshu' and look['secondary']['id'] == 'lost_money_1930'
debit = mobile._report_buttons('sms', 0, '', [mobile.llm.DEBIT_STEP])
assert debit['primary']['id'] == 'lost_money_1930' and debit['secondary']['id'] == 'report_cybercrime'
assert debit['primary']['hi'] == 'पैसे चले गए? 1930 पर कॉल करें'
sex = mobile._report_buttons('sms', 1, 'sextortion or blackmail', ['Do not pay; paying leads to more demands.'])
ext = mobile._report_buttons('sms', 1, 'an extortion threat', ['Do not pay; paying leads to more demands.'])
assert sex['primary']['id'] == ext['primary']['id'] == 'report_cybercrime'
assert sex['secondary']['id'] == 'lost_money_1930'
assert mobile._report_buttons('sms', 'uncertain', 'OTP or PIN theft', [mobile.llm.DEBIT_STEP]) is None
assert mobile._report_buttons('flow', 1, 'a port scan', ['Block the source address at the firewall or router.']) is None
assert mobile._report_buttons('sms', 0, '', ['Verify in the official app; never share your OTP or PIN.']) is None
print('hindi steps, link order, benign evidence and report buttons passed')

# End to end through the shipped detector, with only NumPy available.
class Echo:
    def generate(self, prompt):
        word = prompt.rsplit('Verdict: ', 1)[-1].split('\n')[0]
        reply = {'DANGEROUS': 'This item is DANGEROUS. It points to an unofficial site.', 'NO RISK FOUND': 'No risk found for this item.'}
        return json.dumps({'text': reply.get(word, 'This item is SUSPICIOUS.'), 'stats': {}})
for kind, text in [('sms', 'Dear customer your SBI KYC is expiring, update at http://sbi-kyc.in-verify.top or the account will be blocked'),
                   ('url', 'http://sbi-kyc.in-verify.top/login'),
                   ('flow', 'many connections to different ports from one host in a few seconds')]:
    out = json.loads(mobile.check(kind, text, Echo()))
    assert out['verdict'] in ('DANGEROUS', 'SUSPICIOUS', 'NO RISK FOUND — still verify'), out
    print(kind, out['verdict'], out['evidence'][:2])
print('mobile.check runs with only NumPy installed')
