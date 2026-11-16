"""Experimental cross-UID entrypoints. Never use as a certified safety controller."""
import argparse,json
from .bound_ipc import BoundAuthorityServer,BoundProductionServer,PinnedBoundAuthorityClient
from .production_admission import ProductionAdmissionClient

def main():
    p=argparse.ArgumentParser()
    p.add_argument('role',choices=('authority','service','permit','client'))
    for k in ('socket','db','permit-db','authority','client-uid','service-uid','witness-uid','recovery-token','crash-at','payload'):
        p.add_argument('--'+k,type=int if k.endswith('uid') else str)
    a=p.parse_args()
    if a.role=='authority': BoundAuthorityServer(a.socket,a.db,a.permit_db,a.service_uid,a.client_uid).serve()
    elif a.role=='service': BoundProductionServer(a.socket,a.db,a.authority,a.client_uid,a.witness_uid,a.crash_at).serve(recovery_token=a.recovery_token)
    elif a.role=='permit': print(json.dumps(PinnedBoundAuthorityClient(a.socket,a.witness_uid).execute('issue')),flush=True)
    else: print(json.dumps(ProductionAdmissionClient(a.socket).admit((a.payload or 'stage016').encode())),flush=True)
if __name__=='__main__': main()
