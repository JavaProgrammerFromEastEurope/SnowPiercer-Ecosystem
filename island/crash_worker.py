"""Subprocess entrypoint for deterministic real SIGKILL testing."""
import argparse,json
from .crash_protocol import CrashInstrumentedAdmission
from .anchored_admission import WitnessClient

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--db',required=True);p.add_argument('--witness',required=True)
    p.add_argument('--crash-at');p.add_argument('--mode',choices=['admit','recover'],default='admit')
    a=p.parse_args()
    svc=CrashInstrumentedAdmission(a.db,WitnessClient(a.witness))
    result=svc.recover() if a.mode=='recover' else svc.admit(b'ISLAND-GEO-013-synthetic',a.crash_at)
    print(json.dumps(result),flush=True)
if __name__=='__main__':main()
