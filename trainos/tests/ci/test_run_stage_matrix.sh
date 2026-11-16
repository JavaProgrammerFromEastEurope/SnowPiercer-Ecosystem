#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
runner="$ROOT/scripts/ci/run_stage_matrix.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# Invalid ranges must fail before invoking pytest.
if "$runner" 0 2 "$tmp/invalid" >/dev/null 2>&1; then
  echo 'expected stage 0 to be rejected' >&2; exit 1
fi
if "$runner" 1000 1001 "$tmp/empty" >/dev/null 2>&1; then
  echo 'expected an empty stage range to be rejected' >&2; exit 1
fi

# Stub only the Python test runner; exercise the actual timeout/summary plumbing.
mkdir -p "$tmp/bin"
cat > "$tmp/bin/python" <<'PY'
#!/usr/bin/env bash
last="${@: -1}"
case "$last" in
  tests/stage117) echo '2 passed in 0.01s'; exit 0 ;;
  tests/stage118) echo 'intentional simulated failure'; exit 1 ;;
  tests/stage119) echo 'intentional simulated timeout'; exit 124 ;;
  *) echo "unexpected test path: $last" >&2; exit 9 ;;
esac
PY
chmod +x "$tmp/bin/python"
set +e
PATH="$tmp/bin:$PATH" "$runner" 117 119 "$tmp/logs" 5 >"$tmp/stdout" 2>&1
rc=$?
set -e
[[ "$rc" -eq 1 ]]
grep -q $'117\tPASS\t0\t' "$tmp/logs/summary.tsv"
grep -q $'118\tFAIL\t1\t' "$tmp/logs/summary.tsv"
grep -q $'119\tTIMEOUT\t124\t' "$tmp/logs/summary.tsv"
test -s "$tmp/logs/stage117.log"
test -s "$tmp/logs/stage118.log"
test -s "$tmp/logs/stage119.log"
echo 'run_stage_matrix shell tests (PASS/FAIL/TIMEOUT): PASS'
