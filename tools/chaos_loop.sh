#!/usr/bin/env bash
# Phase 7 item 2: run the kill-and-restart chaos test N times; keep the full output of every failure.
#   tools/chaos_loop.sh [N] [python]
# Results: test-results/chaos/summary.txt and fail-<i>.txt (with the server logs of that run).
set -u
N=${1:-100}
PY=${2:-python}
cd "$(dirname "$0")/.."
OUT=test-results/chaos
mkdir -p "$OUT"
rm -f "$OUT"/fail-*.txt "$OUT/runs.txt" "$OUT/times.txt"
pass=0; fail=0
for i in $(seq 1 "$N"); do
  base=$(mktemp -d)
  t0=$(date +%s.%N)
  if "$PY" -m pytest tests/api/test_phase6_chaos.py -k kill_mid_session -s -p no:cacheprovider --basetemp "$base" > "$OUT/run.txt" 2>&1; then
    pass=$((pass + 1)); echo "$i PASS $(grep -o 'chaos:.*' "$OUT/run.txt" | head -1)" >> "$OUT/runs.txt"
  else
    fail=$((fail + 1)); echo "$i FAIL" >> "$OUT/runs.txt"
    { cat "$OUT/run.txt"; for f in $(find "$base" -name 'server-*.log'); do echo "=== $f"; cat "$f"; done; } > "$OUT/fail-$i.txt"
  fi
  rm -rf "$base"
  printf '%s %.1fs\n' "$i" "$(echo "$(date +%s.%N) - $t0" | bc)" >> "$OUT/times.txt"
done
echo "chaos kill-and-restart: $pass passed, $fail failed of $N runs" | tee "$OUT/summary.txt"
