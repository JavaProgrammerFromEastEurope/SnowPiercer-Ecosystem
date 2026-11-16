"""ISLAND-GEO-021 isolated Linux runtime; permits are read from inherited FD."""
import argparse
import json
import os
from pathlib import Path
from .anchored_admission import AdmissionDenied
from .attested_broker import AttestedWriteBroker, AttestedAdmissionFacade, SignedAdmissionClient, sign_admission, _read_private_file
from .bound_ipc import PinnedBoundAuthorityClient
from .socket_isolation import IsolatedAuthorityServer
from .production_admission import secure_directory
from .mandatory_guard import _safe_existing


def main():
    p = argparse.ArgumentParser()
    p.add_argument('role', choices=('authority', 'broker', 'facade', 'permit', 'sign', 'submit', 'client'))
    for name in ('socket', 'db', 'permit-db', 'authority', 'broker-socket', 'public-key', 'private-key',
                 'client-uid', 'service-uid', 'broker-uid', 'witness-uid', 'facade-uid',
                 'token-fd', 'crash-at', 'payload', 'envelope-file'):
        p.add_argument('--' + name, type=int if name.endswith('uid') or name == 'token-fd' else str)
    a = p.parse_args()
    if a.role == 'authority':
        # Preflight both authority databases and every SQLite sidecar before binding.
        for db_path in (a.db, a.permit_db):
            secure_directory(Path(db_path).parent, os.geteuid())
            _safe_existing(Path(db_path), os.geteuid())
        IsolatedAuthorityServer(a.socket, a.db, a.permit_db, a.broker_uid, a.client_uid).serve()
    elif a.role == 'broker':
        if a.token_fd is None:
            raise AdmissionDenied('mandatory recovery token FD')
        try:
            token = os.read(a.token_fd, 129).decode('ascii')
        finally:
            os.close(a.token_fd)
        AttestedWriteBroker(a.socket, a.db, a.authority, a.public_key, a.client_uid,
                            a.service_uid, a.witness_uid, a.crash_at).serve(token)
    elif a.role == 'facade':
        AttestedAdmissionFacade(a.socket, a.broker_socket, a.client_uid,
                                a.broker_uid, a.witness_uid).serve()
    elif a.role == 'permit':
        print(json.dumps(PinnedBoundAuthorityClient(a.socket, a.witness_uid).execute('issue')), flush=True)
    else:
        if a.role == 'submit':
            envelope = json.loads(Path(a.envelope_file).read_text())
        else:
            key = _read_private_file(a.private_key, os.geteuid(), 32)
            envelope = sign_admission(a.payload.encode(), key, os.geteuid(), a.broker_uid)
        if a.role == 'sign':
            print(json.dumps(envelope, sort_keys=True), flush=True)
        else:
            print(json.dumps(SignedAdmissionClient(a.socket, a.facade_uid).admit(envelope)), flush=True)


if __name__ == '__main__':
    main()
