import argparse
from .core.supervision import ServiceSupervisor

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--registry',required=True); p.add_argument('--db',required=True); p.add_argument('--socket',required=True)
    p.add_argument('--production',action='store_true'); p.add_argument('--client-uid',type=int)
    args=p.parse_args()
    ServiceSupervisor(args.registry,args.db,args.socket,production=args.production,client_uid=args.client_uid).run()
if __name__=='__main__':main()
