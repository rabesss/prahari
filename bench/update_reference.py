#!/usr/bin/env python3
"""Controller: regenerate after promotion and review each gate flag."""
import json
from pathlib import Path
import subprocess
import sys
from common import ROOT

candidate=sys.argv[1] if len(sys.argv)>1 else 'candidates/BEST'
result={'note':'Fixture gate flags are provisional: aarch64 confirmed; first x86 CI run must independently confirm before relying on them. Stress rows gate only if correct on reference.'}
for name, script, prefix in [('fixtures','gate.py','FIXTURE_JSON '),('stress','stress.py','STRESS_JSON ')]:
    run=subprocess.run([sys.executable,str(ROOT/'bench'/script),candidate,'--record'],capture_output=True,text=True)
    if run.returncode:
        sys.stdout.write(run.stdout); sys.stderr.write(run.stderr); raise SystemExit(f'{script} --record failed ({run.returncode})')
    for line in run.stdout.splitlines():
        if line.startswith(prefix): result[name]=json.loads(line[len(prefix):])
        else: print(line)
    if name not in result: raise RuntimeError('missing reference results')
(ROOT/'bench/reference.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print('Reference written; verify gate flags on x86 CI before relying on them.')
