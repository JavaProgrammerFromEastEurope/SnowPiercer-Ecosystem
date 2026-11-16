"""Negative-control proof that strict warnings are errors; stdout/stderr retained."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'AUDIT'/'evidence_v105'


def main():
    OUT.mkdir(exist_ok=True,parents=True)
    with tempfile.TemporaryDirectory(prefix='trainos-v105-warnings-') as directory:
        path=Path(directory)/'test_warning_policy.py'
        path.write_text("import warnings\n"
                        "def test_resource_warning():\n"
                        "    warnings.warn('resource probe',ResourceWarning)\n"
                        "def test_deprecation_warning():\n"
                        "    warnings.warn('deprecation probe',DeprecationWarning)\n")
        cmd=[sys.executable,'-m','pytest','-q','-c',str(ROOT/'pytest.ini'),
             '-W','error::ResourceWarning','-W','error::DeprecationWarning',
             '-W','error::pytest.PytestUnraisableExceptionWarning',str(path)]
        env=dict(os.environ, PYTHONWARNINGS='error::ResourceWarning,error::DeprecationWarning')
        proc=subprocess.run(cmd,capture_output=True,cwd=ROOT,env=env,timeout=60)
        stdout=proc.stdout.decode(errors='replace');stderr=proc.stderr.decode(errors='replace')
        (OUT/'warning_negative_control.stdout.log').write_text(stdout)
        (OUT/'warning_negative_control.stderr.log').write_text(stderr)
        (OUT/'warning_negative_control.exitcode').write_text(str(proc.returncode)+'\n')
        result={'schema':'trainos.v105.warning-negative-control.v1','exitcode':proc.returncode,
                'command':cmd,'resource_warn_raised_as_error':'resource probe' in stdout,
                'deprecation_warn_raised_as_error':'deprecation probe' in stdout,
                'two_expected_failures':'2 failed' in stdout,
                'test_status':'PASS' if proc.returncode!=0 and '2 failed' in stdout and
                                          'resource probe' in stdout and 'deprecation probe' in stdout else 'FAIL',
                'note':'Negative-control failure is expected; not a release regression failure.'}
        (OUT/'WARNING_NEGATIVE_CONTROL_V105.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2))
        return 0 if result['test_status']=='PASS' else 1

if __name__=='__main__':
    raise SystemExit(main())
