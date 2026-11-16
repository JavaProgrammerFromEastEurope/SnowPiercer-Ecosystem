"""ISLAND-GEO-012: Linux multi-UID process entrypoints; experimental, not certified."""
import argparse, json, os, socket, sys
from .anchored_admission import WitnessServer, WitnessClient, AdmissionDenied
from .production_admission import ProductionAdmissionServer, ProductionAdmissionClient
from .production_fencing import PinnedWitnessClient

def main():
    p=argparse.ArgumentParser(); p.add_argument('role',choices=['witness','service','client']); p.add_argument('--socket',required=True); p.add_argument('--db'); p.add_argument('--witness'); p.add_argument('--client-uid',type=int); p.add_argument('--service-uid',type=int); p.add_argument('--witness-uid',type=int); p.add_argument('--payload',default='stage012')
    a=p.parse_args()
    if a.role=='witness':
        WitnessServer(a.socket,a.db,{a.service_uid}).serve()
    elif a.role=='service':
        s=ProductionAdmissionServer(a.socket,a.db,a.witness,{a.client_uid},a.witness_uid)
        s.witness_client_factory=lambda path: PinnedWitnessClient(path,a.witness_uid)
        s.serve()
    else:
        print(json.dumps(ProductionAdmissionClient(a.socket).admit(a.payload.encode()),sort_keys=True),flush=True)
if __name__=='__main__': main()
