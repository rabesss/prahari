import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'candidates/BEST'), str(ROOT/'android/python')]
# Chaquopy installs only NumPy: block the desktop-only packages so an import of
# any of them fails here as it would on the phone.
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
