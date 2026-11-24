import json, re, unicodedata, collections
from pathlib import Path
p=Path(__file__).resolve().parent
rows=[json.loads(line) for line in (p/'fp_val_v1.jsonl').read_text(encoding='utf8').splitlines()]
assert len(rows)==240 and [r['id'] for r in rows]==[f'fv-{i:03d}' for i in range(1,241)]
assert collections.Counter(r['label'] for r in rows)=={0:150,1:90}
assert len({r['text'] for r in rows})==240
assert all(set(r)=={'id','text','label','lang','category','hard','why'} and r['lang'] in ('en','hi','hinglish') and type(r['hard']) is bool and r['why'] for r in rows)
def tokens(s):
    # Unicode letters, combining marks and digits form tokens; punctuation and whitespace split.
    out=[]; word=''
    for ch in unicodedata.normalize('NFKC',s).casefold():
        if unicodedata.category(ch)[0] in 'LMN': word+=ch
        elif word: out.append(word); word=''
    if word: out.append(word)
    return set(out)
pairs=[]
for i,a in enumerate(rows):
    x=tokens(a['text'])
    for b in rows[i+1:]:
        y=tokens(b['text']); pairs.append((len(x&y)/len(x|y),a['id'],b['id']))
pairs.sort(reverse=True)
print('max Jaccard',pairs[0]); print('top pairs',pairs[:15]); print('language',collections.Counter((r['label'],r['lang']) for r in rows)); print('hard',collections.Counter(r['label'] for r in rows if r['hard']))
assert pairs[0][0]<0.5
for label in (0,1): assert sum(r['hard'] for r in rows if r['label']==label)>=0.4*sum(r['label']==label for r in rows)
