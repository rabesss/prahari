"""The app must work with networking disabled. `unshare -rn` is unavailable on the
evaluation host, so use the controller's import-time offline guard (eval/guard),
which is what bin/eval injects into every candidate process."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

CAND = Path(__file__).resolve().parents[1]
REPO = CAND.parents[1]
GUARD = REPO / "eval" / "guard"


def _env(tmp):
    return dict(os.environ, PYTHONPATH=str(GUARD), HC_PY=sys.executable,
                HC_GUARD_LOG=str(tmp / "guard.log"), HC_GUARD_DENY_PATHS="")


@pytest.mark.skipif(not GUARD.is_dir(), reason="controller offline guard not present")
def test_guard_blocks_network(tmp_path):
    code = ("import socket; s=socket.socket();\n"
            "s.settimeout(2); s.connect(('203.0.113.1', 80))")
    p = subprocess.run([sys.executable, "-c", code], env=_env(tmp_path),
                       capture_output=True, text=True)
    assert p.returncode != 0 and "network disabled by offline guard" in p.stderr


@pytest.mark.skipif(not GUARD.is_dir(), reason="controller offline guard not present")
def test_predict_runs_offline(tmp_path):
    inp, out = tmp_path / "in.jsonl", tmp_path / "out.jsonl"
    inp.write_text(json.dumps({"id": "u1", "url": "http://sbi-kyc.in-verify.top/login"}) + "\n")
    p = subprocess.run([str(CAND / "bin" / "predict"), "--task", "url",
                        "--in", str(inp), "--out", str(out)],
                       env=_env(tmp_path), capture_output=True, text=True)
    assert p.returncode == 0, p.stderr[-800:]
    rows = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
    assert rows and rows[0]["label"] == 1
