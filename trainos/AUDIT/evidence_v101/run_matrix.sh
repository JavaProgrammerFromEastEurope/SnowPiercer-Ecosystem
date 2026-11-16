#!/bin/bash
set -u
cd "$(dirname "$0")/../.."
for i in 1 2 3; do
 python scripts/ci/run_bounded_pytest.py --timeout 105 --report "AUDIT/evidence_v101/combined_${i}.json" -- -q -W error::ResourceWarning -W error::DeprecationWarning -W error::pytest.PytestUnraisableExceptionWarning tests/domains/recovery tests/domains/ci_release tests/domains/pytest_diagnostics
 echo $? >"AUDIT/evidence_v101/combined_${i}.exitcode"
done
python scripts/ci/run_bounded_pytest.py --timeout 155 --report AUDIT/evidence_v101/full_after.json -- -q -W error::ResourceWarning -W error::DeprecationWarning -W error::pytest.PytestUnraisableExceptionWarning tests
echo $? >AUDIT/evidence_v101/full_after.exitcode
