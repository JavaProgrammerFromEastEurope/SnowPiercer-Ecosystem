"""Read-only cross-UID service child for LIFE-CORE-015."""
import argparse
from .core.cross_uid import AuthorizedLifecycleService

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--registry',required=True)
    p.add_argument('--db',required=True)
    p.add_argument('--socket',required=True)
    p.add_argument('--uids',required=True)
    a=p.parse_args()
    allowed={int(x) for x in a.uids.split(',')}
    AuthorizedLifecycleService(a.registry,a.db,a.socket,allowed_uids=allowed).serve()

if __name__=='__main__': main()
