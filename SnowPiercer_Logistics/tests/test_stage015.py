import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
import pytest
from snowpiercer_logistics.secure import AdmissionError
from snowpiercer_logistics.stage015 import DirectAttestationAuthority, attested_permit_request
from snowpiercer_logistics.stage013 import run_as_uid


def test_invalid_token_fails_closed():
    from snowpiercer_logistics.stage015 import _token_digest
    with pytest.raises(AdmissionError): _token_digest('not-a-token')


def test_legacy_protocol_not_inherited(tmp_path):
    with DirectAttestationAuthority(tmp_path / 'broker', os.geteuid(), os.geteuid() + 100) as broker:
        with pytest.raises(AdmissionError):
            attested_permit_request(broker.socket_path, 'issue', scope='recovery')


@pytest.mark.skipif(sys.platform != 'linux' or os.geteuid() != 0, reason='Linux root required')
def test_real_cross_uid_attestation_replay_and_restart(tmp_path):
    # Authority runs as root; separate real client and service subprocesses have
    # kernel-verified UIDs. This is a broker E2E, not a ledger/witness E2E.
    client_uid, service_uid = 12004, 12001
    with DirectAttestationAuthority(tmp_path / 'broker', 0, service_uid) as broker:
        os.chmod(broker.root, 0o711)
        os.chmod(broker.socket_path, 0o666)
        token = attested_permit_request(broker.socket_path, 'issue_attested',
                                        scope='recovery', client_uid=client_uid)['permit']
        script = ('import sys,json; from snowpiercer_logistics.stage015 import attested_permit_request; '
                  'print(json.dumps(attested_permit_request(sys.argv[1],sys.argv[2],'
                  'scope="recovery",client_uid=int(sys.argv[3]),permit=sys.argv[4])))')
        envpath = str(Path(__file__).resolve().parents[1])
        # Run from a public temp location because tmp_path ancestors may be 0700.
        import shutil
        public = Path(tempfile.mkdtemp(prefix='log015_', dir='/tmp'))
        try:
            os.chmod(public, 0o755)
            os.chmod(tmp_path, 0o711)
            os.chmod(tmp_path.parent, 0o711)
            os.chmod(tmp_path.parent.parent, 0o711)
            # Python package is under /mnt/data, accessible to these UIDs.
            env = {'PYTHONPATH': envpath, 'PYTHONWARNINGS':'error::ResourceWarning,error::DeprecationWarning'}
            def as_uid(uid, action, client=client_uid):
                cmd = [sys.executable, '-c', script, str(broker.socket_path), action, str(client), token]
                def drop():
                    os.setgroups([]); os.setgid(uid); os.setuid(uid)
                return subprocess.run(cmd, env={**os.environ, **env}, preexec_fn=drop,
                                      capture_output=True, text=True, timeout=8)
            assert as_uid(service_uid, 'consume_attested').returncode != 0
            assert as_uid(client_uid, 'attest').returncode == 0
            assert as_uid(service_uid, 'consume_attested', 12005).returncode != 0
            assert as_uid(service_uid, 'consume_attested').returncode == 0
            assert as_uid(service_uid, 'consume_attested').returncode != 0
        finally:
            shutil.rmtree(public)
