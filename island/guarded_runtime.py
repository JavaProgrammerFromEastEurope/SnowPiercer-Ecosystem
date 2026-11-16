"""Experimental hardened entrypoint; no certified production deployment."""
import argparse
from .mandatory_guard import MandatoryGuardServer

def main():
    parser = argparse.ArgumentParser()
    for key in ('socket', 'db', 'authority', 'client-uid', 'witness-uid', 'recovery-token', 'crash-at'):
        parser.add_argument('--' + key, required=key not in ('crash-at',), type=int if key.endswith('uid') else str)
    args = parser.parse_args()
    MandatoryGuardServer(args.socket, args.db, args.authority,
                         args.client_uid, args.witness_uid, args.crash_at).serve(
                             recovery_token=args.recovery_token)

if __name__ == '__main__':
    main()
