#!/usr/bin/env python3
"""Heuristics, not proof of contest compliance or safe behaviour."""
import argparse
import ast
from pathlib import Path
import re
import sys

SECTIONS=('Problem','Architecture','Models','Datasets','Results','Performance','Limitations','Responsible AI')
SOURCES={'UCI SMS':r'UCI.*SMS|SMS.*UCI','Mendeley':r'Mendeley','PhiUSIIL':r'PhiUSIIL','NSL-KDD':r'NSL.KDD','Indian synthetic':r'Indian.context synthetic','karanverma19':r'karanverma19','bolewara':r'bolewara','Llama':r'Llama'}

def check(cand):
    cand=Path(cand); issues=[]
    def content(name):
        try: return (cand/name).read_text(encoding='utf-8')
        except OSError: issues.append(f'{name}: missing'); return ''
    readme=content('README.md'); report=content('REPORT.md'); data=content('DATA.md')
    for section in SECTIONS:
        if not re.search(r'^#{1,4}\s+'+re.escape(section)+r'(?=\s|,|$)[^\n]*$',report,re.I|re.M): issues.append(f'REPORT.md: missing {section} section')
    for label,pattern in {'setup':r'(?i)setup|install','application':r'(?i)compiled application|linux executable|android apk','offline':r'(?i)offline','demo':r'(?i)demo'}.items():
        if not re.search(pattern,readme): issues.append(f'README.md: missing {label}')
    for label,pattern in {'hardware':r'(?i)hardware|neoverse|device','model configuration':r'(?i)model','measured performance':r'(?i)performance','demo video':r'(?i)video','offline':r'(?i)offline'}.items():
        if not re.search(pattern,report): issues.append(f'REPORT.md: missing {label}')
    for label,pattern in SOURCES.items():
        if not re.search(pattern,data,re.I|re.S): issues.append(f'DATA.md: missing {label} source')
    for path in sorted(cand.rglob('*')):
        if not path.is_file() or path.suffix not in ('.py','.html','.js'): continue
        text=path.read_text(encoding='utf-8')
        if re.search(r'(?i)\bwebbrowser\s*\.\s*open(?:_new(?:_tab)?)?\s*\(|\bwindow\s*\.\s*open\s*\(|\b(?:window\.)?location\s*(?:\.href)?\s*=',text): issues.append(f'{path.relative_to(cand)}: possible automatic link opening')
        # Examine literal templates and prompts; regex rules matching scam language are not user-facing templates.
        if path.suffix == '.py' and path.name in ('server.py','llm.py'):
            try: tree=ast.parse(text)
            except SyntaxError: issues.append(f'{path.relative_to(cand)}: cannot parse'); continue
            for node in ast.walk(tree):
                if isinstance(node,ast.Constant) and isinstance(node.value,str) and re.search(r'(?i)\b(?:100\s*%\s*(?:safe|accurate|correct)|(?:always|definitely|certainly)\s+(?:safe|correct|malicious|benign)|guaranteed\s+(?:safe|correct|accurate))\b',node.value): issues.append(f'{path.relative_to(cand)}:{node.lineno}: possible certainty phrase')
    return issues

def main():
    p=argparse.ArgumentParser(); p.add_argument('candidate',nargs='?',default='candidates/BEST'); a=p.parse_args()
    issues=check(a.candidate)
    for issue in issues: print('HEURISTIC FAIL',issue)
    print(f'HEURISTIC READINESS {"FAIL" if issues else "PASS"}: {len(issues)} issue(s); manual review required')
    return bool(issues)
if __name__=='__main__': sys.exit(main())
