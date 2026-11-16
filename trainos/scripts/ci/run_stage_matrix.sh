#!/usr/bin/env bash
# Run each TrainOS stage in its own process, with a hard per-stage timeout.
# Usage: run_stage_matrix.sh START END LOG_DIR [TIMEOUT_SECONDS]
set -uo pipefail

if [[ $# -lt 3 || $# -gt 4 ]]; then
  echo "Usage: $0 START END LOG_DIR [TIMEOUT_SECONDS]" >&2
  exit 2
fi
start="$1"
end="$2"
log_dir="$3"
timeout_seconds="${4:-180}"

if ! [[ "$start" =~ ^[0-9]+$ && "$end" =~ ^[0-9]+$ && "$timeout_seconds" =~ ^[0-9]+$ ]]; then
  echo "START, END, and TIMEOUT_SECONDS must be non-negative integers" >&2
  exit 2
fi
if (( start < 1 || end < 1 || start > end || timeout_seconds < 1 )); then
  echo "Require 1 <= START <= END and TIMEOUT_SECONDS >= 1" >&2
  exit 2
fi

# Fail early on a typo in the stage range instead of reporting a false green run.
found=0
for n in $(seq "$start" "$end"); do
  if [[ -d "tests/stage${n}" ]]; then found=$((found + 1)); fi
done
if (( found == 0 )); then
  echo "No tests/stageN directories found in range ${start}-${end}" >&2
  exit 2
fi

mkdir -p "$log_dir"
summary="$log_dir/summary.tsv"
printf 'stage\tstatus\texit_code\tseconds\tlog\n' > "$summary"
failed=0

for n in $(seq "$start" "$end"); do
  test_dir="tests/stage${n}"
  [[ -d "$test_dir" ]] || continue
  log_file="$log_dir/stage${n}.log"
  start_epoch=$(date +%s)
  printf '\n=== stage%s (timeout %ss) ===\n' "$n" "$timeout_seconds"
  set +e
  PYTHONPATH="${PYTHONPATH:-.}" timeout --signal=TERM --kill-after=10s "${timeout_seconds}s" \
    python -m pytest -q --durations=10 "$test_dir" >"$log_file" 2>&1
  code=$?
  set -e
  elapsed=$(( $(date +%s) - start_epoch ))
  if (( code == 0 )); then
    status=PASS
  elif (( code == 124 || code == 137 )); then
    status=TIMEOUT
    failed=1
  else
    status=FAIL
    failed=1
  fi
  printf '%s\t%s\t%s\t%s\t%s\n' "$n" "$status" "$code" "$elapsed" "$(basename "$log_file")" >> "$summary"
  printf '%s: %s (exit=%s, %ss)\n' "stage$n" "$status" "$code" "$elapsed"
  tail -n 4 "$log_file" || true
done

printf '\nStage summary: %s (%s stage directories)\n' "$summary" "$found"
exit "$failed"
