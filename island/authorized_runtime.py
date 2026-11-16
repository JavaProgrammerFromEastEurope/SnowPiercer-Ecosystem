"""Explicit experimental CLI for the cross-UID authority and admission service."""
import argparse, json
from .authorized_production import AuthorityServer, AuthorizedProductionServer, AuthorityClient
from .production_admission import ProductionAdmissionClient

def main():
    p=argparse.ArgumentParser()
    p.add_argument('role',choices=['authority','service','client','permit'])
    for flag in ('socket','db','authority','permit-db','client-uid','service-uid','witness-uid','crash-at','recovery-token','payload'):
        p.add_argument('--'+flag, type=int if flag.endswith('uid') else str)
    a=p.parse_args()
    if a.role=='authority': AuthorityServer(a.socket,a.db,a.permit_db,a.service_uid,a.client_uid).serve()
    elif a.role=='service': AuthorizedProductionServer(a.socket,a.db,a.authority,a.client_uid,a.witness_uid,a.crash_at).serve(recovery_token=a.recovery_token)
    elif a.role=='permit': print(json.dumps(AuthorityClient(a.socket).execute('issue')),flush=True)
    else: print(json.dumps(ProductionAdmissionClient(a.socket).admit((a.payload or 'test').encode())),flush=True)
if __name__=='__main__': main()
