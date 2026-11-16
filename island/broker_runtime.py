"""ISLAND-GEO-020 opt-in broker deployment entrypoint (Linux)."""
import argparse
from .write_broker import WriteBroker,AdmissionFacade

def main():
    p=argparse.ArgumentParser()
    p.add_argument('role',choices=('broker','facade'))
    for field in ('socket','db','authority','broker-socket','client-uid','service-uid','broker-uid','witness-uid','recovery-token','crash-at'):
        p.add_argument('--'+field,type=int if field.endswith('uid') else str)
    a=p.parse_args()
    if a.role=='broker':
        WriteBroker(a.socket,a.db,a.authority,a.client_uid,a.service_uid,a.witness_uid,a.crash_at).serve(a.recovery_token)
    else:
        AdmissionFacade(a.socket,a.broker_socket,a.client_uid,a.broker_uid,a.witness_uid).serve()
if __name__=='__main__':main()
