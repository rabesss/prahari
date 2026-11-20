#!/usr/bin/env python3
"""Controller-only promotion: validate the comparison and update BEST and its pin."""
import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile

from compare_v3 import BEST_PIN, compare
from run_eval import candidate_hash


def promote(candidate, best_dir, best_runs, candidate_runs, threshold, pin=BEST_PIN):
    # Promotion needs the three-run confirmation; compare() alone also accepts two-run screens.
    if len(best_runs) != 3 or len(candidate_runs) != 3:
        raise ValueError('promotion requires exactly three runs per side')
    result = compare(best_runs, candidate_runs, threshold)
    if not result['pass']:
        raise ValueError('comparison failed: ' + '; '.join(result['failures']))
    candidate = candidate.resolve()
    best_dir = best_dir.resolve()
    if candidate == best_dir or not candidate.is_dir():
        raise ValueError('invalid candidate directory')
    if candidate_hash(best_dir) != pin.read_text().strip():
        raise ValueError('current BEST differs from pin')
    digest = candidate_hash(candidate)
    if digest != candidate_runs[0]['candidate_hash']:
        raise ValueError('candidate differs from evaluated content')
    with tempfile.TemporaryDirectory(prefix='.prahari-promotion-', dir=best_dir.parent) as temp:
        temp = Path(temp)
        replacement, previous = temp / 'replacement', temp / 'previous'
        shutil.copytree(candidate, replacement, symlinks=True)
        if candidate_hash(replacement) != digest:
            raise ValueError('promotion copy differs from evaluated content')
        os.replace(best_dir, previous)
        try:
            os.replace(replacement, best_dir)
            with tempfile.NamedTemporaryFile(mode='w', dir=pin.parent, prefix='.BEST.sha256-', delete=False) as f:
                pin_tmp = Path(f.name)
                f.write(digest + '\n')
            try:
                os.replace(pin_tmp, pin)
            finally:
                pin_tmp.unlink(missing_ok=True)
        except BaseException:
            if best_dir.exists():
                shutil.rmtree(best_dir)
            os.replace(previous, best_dir)
            raise
    return digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--best', nargs='+', required=True, type=Path)
    parser.add_argument('--candidate-runs', nargs='+', required=True, type=Path)
    parser.add_argument('--threshold', type=float, required=True)
    args = parser.parse_args()
    try:
        digest = promote(args.candidate, BEST_PIN.parents[2] / 'candidates/BEST',
                         [json.loads(p.read_text()) for p in args.best],
                         [json.loads(p.read_text()) for p in args.candidate_runs], args.threshold)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.exit(1, f'promotion failed: {exc}\n')
    print(digest)


if __name__ == '__main__':
    main()
