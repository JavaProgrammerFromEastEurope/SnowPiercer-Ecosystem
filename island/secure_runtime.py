"""ISLAND-GEO-022 multi-UID lab runtime and deliberately fail-closed strict gate."""
import argparse
import json
import os
from pathlib import Path

from .anchored_admission import AdmissionDenied
from .attested_broker import (AttestedAdmissionFacade, SignedAdmissionClient,
                              sign_admission, _read_private_file)
from .bound_ipc import PinnedBoundAuthorityClient
from .host_security import StrictProductionBrokerMixin, require_separated_roles, require_production_security
from .monotonic_root import SoftwareRootServer
from .split_authorities import SplitWitnessServer, SplitPermitServer, SplitAttestedWriteBroker


class StrictSplitBroker(StrictProductionBrokerMixin, SplitAttestedWriteBroker):
    """Never accepts a software root or unconstrained Python execution as GO."""
    def serve(self, recovery_token, limit=None):
        require_production_security()  # Must deny before startup lease, permit or SQL.
        return super().serve(recovery_token, limit)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Island v0.23.0: explicit LAB or strict NO-GO runtime')
    parser.add_argument('role', choices=('lab-root','witness','permit-authority','lab-broker',
                                         'strict-broker','facade','issue','sign','submit'))
    for arg in ('socket','db','permit-db','root-socket','root-key','root-public-key','witness-socket',
                'permit-socket','broker-socket','public-key','private-key','token-fd','crash-at',
                'payload','envelope-file','client-uid','service-uid','broker-uid',
                'witness-uid','permit-uid','root-uid','facade-uid'):
        parser.add_argument('--'+arg, type=int if arg.endswith('uid') or arg=='token-fd' else str)
    a = parser.parse_args(argv)
    if a.role in ('lab-broker','strict-broker'):
        require_separated_roles(a.client_uid,a.service_uid,os.geteuid(),a.witness_uid,a.permit_uid,a.root_uid)
        if a.token_fd is None:
            raise AdmissionDenied('missing mandatory recovery token FD')
        try:
            token = os.read(a.token_fd,129).decode('ascii')
        finally:
            os.close(a.token_fd)
        cls = StrictSplitBroker if a.role=='strict-broker' else SplitAttestedWriteBroker
        broker = cls(a.socket,a.db,a.witness_socket,a.permit_socket,a.public_key,
                     a.client_uid,a.service_uid,a.witness_uid,a.permit_uid,a.crash_at)
        broker.serve(token)
    elif a.role == 'lab-root':
        SoftwareRootServer(a.socket,a.db,a.root_key,a.witness_uid,a.crash_at).serve()
    elif a.role == 'witness':
        require_separated_roles(a.client_uid,a.service_uid,a.broker_uid,os.geteuid(),a.permit_uid,a.root_uid)
        key = _read_private_file(a.root_public_key,os.geteuid(),32)
        SplitWitnessServer(a.socket,a.db,a.root_socket,a.root_uid,key,a.broker_uid,
                           a.permit_uid,a.crash_at).serve()
    elif a.role == 'permit-authority':
        require_separated_roles(a.client_uid,a.service_uid,a.broker_uid,a.witness_uid,os.geteuid(),a.root_uid)
        SplitPermitServer(a.socket,a.db,a.witness_socket,a.witness_uid,a.broker_uid,
                          a.client_uid,a.crash_at).serve()
    elif a.role == 'facade':
        AttestedAdmissionFacade(a.socket,a.broker_socket,a.client_uid,a.broker_uid,a.witness_uid).serve()
    elif a.role == 'issue':
        print(json.dumps(PinnedBoundAuthorityClient(a.socket,a.permit_uid).execute('issue')),flush=True)
    else:
        if a.role == 'sign':
            key = _read_private_file(a.private_key,os.geteuid(),32)
            value = sign_admission(a.payload.encode(),key,os.geteuid(),a.broker_uid)
            print(json.dumps(value,sort_keys=True),flush=True)
        elif a.role == 'submit':
            envelope = json.loads(Path(a.envelope_file).read_text())
            print(json.dumps(SignedAdmissionClient(a.socket,a.facade_uid).admit(envelope)),flush=True)


if __name__ == '__main__':
    main()
