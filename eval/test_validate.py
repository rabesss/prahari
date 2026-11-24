"""Tests for the validation gate's metrics and regression check (eval/validate.py)."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("validate", Path(__file__).with_name("validate.py"))
validate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate)


def test_uncertain_counts_as_an_error_on_both_sides():
    m = validate.metrics([(1, 1), (1, "uncertain"), (0, 0), (0, "uncertain"), (0, 1)])
    assert (m["tp"], m["fn"], m["tn"], m["fp"], m["uncertain"]) == (1, 1, 1, 2, 2)
    assert m["recall"] == 0.5 and m["fpr"] == round(2 / 3, 4)


def test_regressions_flag_recall_drop_and_fpr_rise_only():
    base = {"a": {"status": "ok", "recall": 0.9, "fpr": 0.2}, "b": {"status": "ok", "recall": 1.0, "fpr": 0.1}}
    now = {"a": {"status": "ok", "recall": 0.95, "fpr": 0.1}, "b": {"status": "ok", "recall": 0.9, "fpr": 0.2},
           "c": {"status": "missing"}}
    bad = validate.regressions(now, base)
    assert bad == ["b: recall 1.0 -> 0.9", "b: FPR 0.1 -> 0.2"]
    base["c"] = {"status": "ok", "recall": 1.0, "fpr": 0.0}
    assert validate.regressions(now, base)[-1] == "c: scored in the baseline but now missing"


def test_sha_mismatch_fails_the_gate(tmp_path, monkeypatch):
    f = tmp_path / "set.jsonl"
    f.write_text('{"text": "hi", "label": 0}\n')
    monkeypatch.setattr(validate, "SETS", [("x", f, "sms", "heldback", "0" * 64)])
    assert validate.main(["--no-tests"]) == 1


def test_held_back_and_sealed_sets_are_hash_checked():
    roles = {name: (role, sha) for name, _, _, role, sha in validate.SETS + [validate.SEALED_SET]}
    for name, (role, sha) in roles.items():
        if role in ("heldback", "sealed", "tune"):
            assert sha and len(sha) == 64, name


def test_unknown_only_name_is_rejected():
    import pytest
    with pytest.raises(SystemExit) as e:
        validate.main(["--no-tests", "--only", "fp_val_vl"])
    assert "unknown set names" in str(e.value)


def test_route_regressions_are_reported():
    base = {"s": {"status": "ok", "recall": 1.0, "fpr": 0.0,
                  "by_route": {"injection": {"recall": 1.0, "fpr": 0.0}}}}
    now = {"s": {"status": "ok", "recall": 1.0, "fpr": 0.0,
                 "by_route": {"injection": {"recall": 0.9, "fpr": 0.0}}}}
    assert validate.regressions(now, base) == ["s/injection: recall 1.0 -> 0.9"]
