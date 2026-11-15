"""LIFE-CORE-017: run under a dedicated, pre-provisioned non-root UID."""
import argparse
from .core.reconciled_write import ReconciledWriteService

def main():
    p=argparse.ArgumentParser()
    for field in ('registry','db','socket','uids'): p.add_argument('--'+field,required=True)
    a=p.parse_args()
    from .core.production_consolidation import enforce_legacy_cli
    enforce_legacy_cli(a.db)
    ReconciledWriteService(a.registry,a.db,a.socket,allowed_uids={int(x) for x in a.uids.split(',')}).serve()

if __name__=='__main__': main()
