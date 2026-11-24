#!/usr/bin/env bash
# Reproducible Arm Linux benchmark sweep for Prahari (Neoverse-N1, Neoverse-V2, RPi 5, etc.).
# Writes all artifacts to OUT_DIR (default under /var/tmp) without modifying the git working tree.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PY="${HC_PY:-$ROOT/.venv/bin/python}"
REG="${HC_MODEL_REGISTRY:-$ROOT/models/registry.json}"
MODELS="${PRAHARI_MODELS:-llama32-1b-qlora}"
THREADS="${PRAHARI_THREADS:-1,2,4}"
PROMPT_LENGTHS="${PRAHARI_PROMPT_LENGTHS:-short,default,long}"
GATING="${PRAHARI_GATING:-all}"
REPEATS="${PRAHARI_REPEATS:-3}"
PIN_CPUS="${PRAHARI_PIN_CPUS:-}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
OUT_DIR="${PRAHARI_OUT_DIR:-/var/tmp/prahari-perf-arm-$STAMP}"

if [[ ! -x "$PY" ]]; then
  echo "ERROR: Python interpreter not executable at HC_PY=$PY" >&2
  exit 1
fi
if [[ ! -f "$REG" ]]; then
  echo "ERROR: Model registry not found at HC_MODEL_REGISTRY=$REG" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"
echo "=== Prahari Arm Linux benchmark ==="
echo "Host: $(uname -a)"
echo "Python: $PY"
echo "Registry: $REG"
echo "Models: $MODELS | Threads: $THREADS | Prompts: $PROMPT_LENGTHS | Gating: $GATING | Repeats: $REPEATS"
echo "Output dir: $OUT_DIR"

EXTRA_ARGS=()
if [[ -n "$PIN_CPUS" ]]; then
  EXTRA_ARGS+=(--pin-cpus "$PIN_CPUS")
fi
if [[ "${PRAHARI_OFFLINE_UNSHARE:-0}" == "1" ]]; then
  EXTRA_ARGS+=(--offline-unshare)
fi
if [[ "${PRAHARI_PERF_PROFILE:-0}" == "1" ]]; then
  EXTRA_ARGS+=(--perf-profile)
fi

"$PY" "$ROOT/bench/perf/arm_bench.py" \
  --python "$PY" \
  --registry "$REG" \
  --models "$MODELS" \
  --threads "$THREADS" \
  --prompt-lengths "$PROMPT_LENGTHS" \
  --gating-mode "$GATING" \
  --repeats "$REPEATS" \
  --detector-bench \
  --out-dir "$OUT_DIR" \
  "${EXTRA_ARGS[@]}"

if [[ "${PRAHARI_OFFLINE_PROOF:-0}" == "1" ]]; then
  echo "=== Running standalone kernel network-namespace offline proof (unshare -n) ==="
  unshare -n -- bash -c '
    set +e
    echo "--- ip -brief link ---"; ip -brief link
    echo "--- curl https://example.com ---"; curl -m 5 -sS https://example.com -o /dev/null; echo "curl_exit=$?"
    echo "--- DNS huggingface.co ---"; getent ahosts huggingface.co; echo "dns_exit=$?"
    echo "--- raw TCP 1.1.1.1:443 ---"
    "'"$PY"'" -c "import socket; s=socket.socket(); s.settimeout(5); s.connect((\"1.1.1.1\",443))"; echo "tcp_exit=$?"
  ' | tee "$OUT_DIR/offline-proof.txt"
fi

echo "Done. Review $OUT_DIR/summary.md and $OUT_DIR/results.json"
