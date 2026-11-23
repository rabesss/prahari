#!/usr/bin/env bash
# End-to-end 30-minute Samsung Galaxy S23 Remote Test Lab (RTL) benchmark runner.
#
# Prerequisites (done once in browser before running this script):
#   1. Reserve an arm64 Samsung Galaxy S23 / S23 FE in Samsung Remote Test Lab.
#   2. Ensure local TCP port 8888 is free (Samsung RDB client binds 8888).
#   3. Launch Samsung RDB client -> Remote Debug Bridge -> Connect -> approve USB debugging.
#   4. Export ANDROID_SERIAL from `adb devices -l` (e.g. export ANDROID_SERIAL=localhost:PORT).
#
# Usage:
#   ANDROID_SERIAL=localhost:PORT \
#   APK=/path/to/prahari-android-arm64.apk \
#   PTE=/var/tmp/prahari-model/Llama-3.2-1B-Instruct-QLORA_INT4_EO8.pte \
#   TOK=/var/tmp/prahari-model/tokenizer.model \
#   ./bench/perf/run_s23_rtl.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PY="${PYTHON:-python3}"
SERIAL="${ANDROID_SERIAL:-}"
APK="${APK:-/var/tmp/prahari-final-v2/prahari-android-arm64.apk}"
PTE="${PTE:-/var/tmp/prahari-model/Llama-3.2-1B-Instruct-QLORA_INT4_EO8.pte}"
TOK="${TOK:-/var/tmp/prahari-model/tokenizer.model}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
OUT_DIR="${OUT_DIR:-/var/tmp/prahari-rtl-session-$STAMP}"
UNINSTALL_ON_EXIT="${UNINSTALL_ON_EXIT:-1}"

if [[ -z "$SERIAL" ]]; then
  echo "ERROR: Set ANDROID_SERIAL from \`adb devices -l\` (do not guess the RDB port)." >&2
  adb devices -l >&2 || true
  exit 2
fi

mkdir -p "$OUT_DIR"
echo "=== Prahari Galaxy S23 RTL Session ==="
echo "Serial:  $SERIAL"
echo "APK:     $APK"
echo "PTE:     $PTE"
echo "TOK:     $TOK"
echo "Out dir: $OUT_DIR"

cleanup() {
  echo "=== Cleanup: restoring airplane mode off ==="
  adb -s "$SERIAL" shell cmd connectivity airplane-mode disable >/dev/null 2>&1 || true
  if [[ "$UNINSTALL_ON_EXIT" == "1" ]]; then
    echo "=== Cleanup: uninstalling in.prahari.app ==="
    adb -s "$SERIAL" uninstall in.prahari.app >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo "=== Step 1/5: Verify device identity and arm64 ABI ==="
"$PY" "$ROOT/bench/perf/adb_bench.py" --serial "$SERIAL" probe --out-dir "$OUT_DIR"
ABI="$(adb -s "$SERIAL" shell getprop ro.product.cpu.abilist | tr -d '\r')"
if [[ "$ABI" != *arm64-v8a* ]]; then
  echo "ERROR: Device ABI ($ABI) is not arm64-v8a." >&2
  exit 1
fi
# Keep screen awake via timeout (avoid `svc power stayon true`, which drops Samsung RDB).
adb -s "$SERIAL" shell settings put system screen_off_timeout 1800000 || true

echo "=== Step 2/5: Install APK, audit INTERNET permission, push & hash model ==="
"$PY" "$ROOT/bench/perf/adb_bench.py" --serial "$SERIAL" stage \
  --apk "$APK" --pte "$PTE" --tokenizer "$TOK"

echo "=== Step 3/5: Record local + device SHA-256 manifest ==="
sha256sum "$APK" "$PTE" "$TOK" > "$OUT_DIR/local-sha256.txt"
adb -s "$SERIAL" shell sha256sum \
  /sdcard/Android/data/in.prahari.app/files/Llama-3.2-1B-Instruct-QLORA_INT4_EO8.pte \
  /sdcard/Android/data/in.prahari.app/files/tokenizer.model > "$OUT_DIR/device-sha256.txt"

echo "=== Step 4/5: Run timed checks (cold + 3x warm + benign + debit + link + port + airplane) ==="
# Exit code 2 means some checks timed out or were skipped; keep going so logs are still captured.
RUN_RC=0
"$PY" "$ROOT/bench/perf/adb_bench.py" --serial "$SERIAL" run \
  --out-dir "$OUT_DIR" \
  --with-airplane \
  --mem-poll-ms 500 \
  --settle-s 8 \
  --check-timeout-s 60 || RUN_RC=$?

echo "=== Step 5/5: Capture logcat tail and battery/thermal post-check ==="
adb -s "$SERIAL" logcat -d -t 250 > "$OUT_DIR/logcat-tail.txt" || true
adb -s "$SERIAL" shell dumpsys battery > "$OUT_DIR/battery-after.txt" || true

echo "=== Session complete ==="
echo "Summary: $OUT_DIR/summary.md"
echo "JSON:    $OUT_DIR/results.json"
echo "CSV:     $OUT_DIR/items.csv"
echo "Remember to close the Samsung Remote Test Lab reservation in the browser."
if [[ "$RUN_RC" != "0" ]]; then
  echo "WARNING: adb_bench run exited $RUN_RC: some checks are incomplete (see the Status column in summary.md)." >&2
  exit "$RUN_RC"
fi
