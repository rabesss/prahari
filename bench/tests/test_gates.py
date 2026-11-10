import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gate
import readiness
import stress
from common import digest


def test_uncertain_benign_is_not_correct():
    r=stress.evaluate([{'id':'x','label':0}], {'x':'uncertain'})
    assert not r['x']['correct']


def test_per_row_fixture_regression_fails(tmp_path, monkeypatch):
    f=tmp_path/'sms.jsonl'; f.write_text(json.dumps({'id':'x','input':'example','expect':0,'rationale':'benign'})+'\n')
    ref=tmp_path/'reference.json'; ref.write_text(json.dumps({'fixtures':{'sms.jsonl':{'sha256':digest(f),'n':1,'rows':{'x':{'expect':0,'prediction':0,'gate':True}}}}}))
    monkeypatch.setattr(gate,'FIXTURES',[f]); monkeypatch.setattr(gate,'predict',lambda *args: ({'x':1},{'invalid':0,'wall_s':0,'peak_rss_mb':1}))
    monkeypatch.setattr(sys,'argv',['gate.py','--reference',str(ref)])
    assert gate.main() == 1


def test_changed_fixture_requires_reference(tmp_path,monkeypatch,capsys):
    f=tmp_path/'sms.jsonl'; f.write_text(json.dumps({'id':'x','input':'example','expect':0,'rationale':'benign'})+'\n')
    ref=tmp_path/'reference.json'; ref.write_text(json.dumps({'fixtures':{'sms.jsonl':{'sha256':'wrong','n':1,'rows':{'x':{'expect':0,'prediction':0,'gate':True}}}}}))
    monkeypatch.setattr(gate,'FIXTURES',[f]); monkeypatch.setattr(gate,'predict',lambda *args: ({'x':0},{'invalid':0,'wall_s':0,'peak_rss_mb':1}))
    monkeypatch.setattr(sys,'argv',['gate.py','--reference',str(ref)])
    assert gate.main() == 1
    assert 'regenerate reference' in capsys.readouterr().out


def test_readiness_detects_sources_open_and_certainty(tmp_path):
    (tmp_path/'README.md').write_text('Setup offline compiled application demo')
    (tmp_path/'REPORT.md').write_text('\n'.join('## '+s for s in readiness.SECTIONS)+'\nhardware model performance demo video offline')
    (tmp_path/'DATA.md').write_text('UCI SMS Mendeley PhiUSIIL NSL-KDD Indian-context synthetic Llama karanverma19')
    (tmp_path/'app').mkdir(); (tmp_path/'app/server.py').write_text('import webbrowser\nwebbrowser.open(url)\nPAGE="This is definitely safe"\n')
    issues=readiness.check(tmp_path)
    assert any('bolewara' in x for x in issues)
    assert any('link opening' in x for x in issues)
    assert any('certainty phrase' in x for x in issues)
