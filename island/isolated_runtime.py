"""Linux-only isolated experimental runtime; no privileged operations performed."""
import argparse,json
from .socket_isolation import IsolatedAuthorityServer,IsolatedProductionServer
from .bound_ipc import PinnedBoundAuthorityClient
from .production_admission import ProductionAdmissionClient

def main():
 p=argparse.ArgumentParser();p.add_argument('role',choices=['authority','service','permit','client'])
 for k in ('socket','db','permit-db','authority','client-uid','service-uid','witness-uid','recovery-token','crash-at','payload'):
  p.add_argument('--'+k,type=int if k.endswith('uid') else str)
 a=p.parse_args()
 if a.role=='authority':IsolatedAuthorityServer(a.socket,a.db,a.permit_db,a.service_uid,a.client_uid).serve()
 elif a.role=='service':IsolatedProductionServer(a.socket,a.db,a.authority,a.client_uid,a.witness_uid,a.crash_at).serve(recovery_token=a.recovery_token)
 elif a.role=='permit':print(json.dumps(PinnedBoundAuthorityClient(a.socket,a.witness_uid).execute('issue')),flush=True)
 else:print(json.dumps(ProductionAdmissionClient(a.socket).admit((a.payload or 'stage017').encode())),flush=True)
if __name__=='__main__':main()
