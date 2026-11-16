#!/bin/sh
set -u
cd "$(dirname "$0")/../.." || exit 125
mkdir -p AUDIT/evidence_v104
for n in 1 2 3; do
  echo "strict_full_$n BEGIN $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> AUDIT/evidence_v104/matrix-launcher.log
  python -m scripts.ci.verify_v104 --case strict_full --iteration "$n" --timeout 900
  code=$?
  echo "strict_full_$n END code=$code $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> AUDIT/evidence_v104/matrix-launcher.log
done
for n in 1 2 3; do
  echo "combined_$n BEGIN $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> AUDIT/evidence_v104/matrix-launcher.log
  python -m scripts.ci.verify_v104 --case combined --iteration "$n" --timeout 480
  code=$?
  echo "combined_$n END code=$code $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> AUDIT/evidence_v104/matrix-launcher.log
done
