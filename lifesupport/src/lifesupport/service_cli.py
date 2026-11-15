import argparse
from .core.service import LifecycleService

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--registry',required=True); p.add_argument('--db',required=True); p.add_argument('--socket',required=True)
    a=p.parse_args(); LifecycleService(a.registry,a.db,a.socket).serve()
if __name__=='__main__': main()
