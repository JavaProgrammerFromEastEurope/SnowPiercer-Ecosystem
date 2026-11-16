#!/bin/bash
set +e
cd /mnt/data/trainos_v100
for n in 1 2 3; do
 python scripts/ci/run_bounded_pytest.py --timeout 95 --grace 2 --report AUDIT/evidence_v100/combined_${n}.json -- -q -W error::ResourceWarning -W error::DeprecationWarning -W error::pytest.PytestUnraisableExceptionWarning tests/domains/recovery tests/domains/ci_release tests/domains/pytest_diagnostics
 echo $? > AUDIT/evidence_v100/combined_${n}.exitcode
done
python scripts/ci/run_bounded_pytest.py --timeout 240 --grace 2 --report AUDIT/evidence_v100/full.json -- -q -W error::ResourceWarning -W error::DeprecationWarning -W error::pytest.PytestUnraisableExceptionWarning tests
 echo $? > AUDIT/evidence_v100/full.exitcode
