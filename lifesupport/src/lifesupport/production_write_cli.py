"""Run as the pre-provisioned dedicated, non-root service UID."""
import argparse
from .core.production_write import ProductionWriteService

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--registry',required=True)
    p.add_argument('--db',required=True)
    p.add_argument('--socket',required=True)
    p.add_argument('--uids',required=True)
    a=p.parse_args()
    from .core.production_consolidation import enforce_legacy_cli
    enforce_legacy_cli(a.db)
    ProductionWriteService(a.registry,a.db,a.socket,allowed_uids={int(x) for x in a.uids.split(',')}).serve()

if __name__=='__main__': main()
