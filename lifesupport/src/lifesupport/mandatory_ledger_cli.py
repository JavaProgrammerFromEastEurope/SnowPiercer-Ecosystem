"""Opt-in service entrypoint. Key file must be pre-provisioned independently."""
import argparse
import os
import stat
from pathlib import Path
from .core.mandatory_ledger import MandatoryLedgerService

def main():
    p=argparse.ArgumentParser()
    for field in ('registry','db','socket','uids','anchor','key-file'):
        p.add_argument('--'+field,required=True)
    a=p.parse_args()
    path=Path(a.key_file)
    st=path.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_uid!=os.geteuid() or stat.S_IMODE(st.st_mode)!=0o600:
        raise ValueError('key file must be service-owned regular 0600')
    key=path.read_bytes()
    MandatoryLedgerService(a.registry,a.db,a.socket,allowed_uids={int(x) for x in a.uids.split(',')},anchor_path=a.anchor,key=key).serve()

if __name__=='__main__': main()
