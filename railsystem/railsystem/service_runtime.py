"""RAIL-TRUST-012: recovery service executable for an externally managed OS unit.

No self-daemonization, privilege switch, fallback to legacy direct recovery,
or automatic stale-socket deletion. Service must be managed by systemd or
another independent process manager. SIGKILL leaves stale socket -> NO-GO.
"""
from __future__ import annotations
import argparse
import json
import signal
import sys
from pathlib import Path
from .os_boundary import validate_production_config
from .privileged_recovery import PrivilegedRecoveryBroker
from .trusted_admission import read_protected_json


def serve(config, *, once=False):
    provider, permit_store = validate_production_config(config)
    uids = config['uids']
    public_key = Path(config['recovery_public_key_file']).read_text(encoding='ascii').strip()
    permit = read_protected_json(config['permit_file'])
    broker = PrivilegedRecoveryBroker(config['state_dir'], config['ipc_dir'],
        transport_gid=config['transport_gid'], allowed_uids=frozenset({uids['client']}),
        provider=provider, permit_store=permit_store)
    stop = False
    def term(_signum, _frame):
        nonlocal stop
        stop = True
    previous = signal.signal(signal.SIGTERM, term)
    try:
        broker.start()
        broker.listener.settimeout(1.0)
        while not stop:
            try:
                broker.handle_one(permit=permit, recovery_public_key=public_key)
            except TimeoutError:
                continue
            if once:
                break
    finally:
        try: broker.close()
        finally: signal.signal(signal.SIGTERM, previous)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args(argv)
    try:
        from .os_managed_fencing import require_production_isolation
        require_production_isolation()  # mandatory OS MAC / independently attested anchor
        config = read_protected_json(args.config)
        serve(config, once=args.once)
    except (Exception,) as exc:
        # Exclude sensitive socket request payload/permit bytes from logs.
        print('RAIL-TRUST-012 BLOCKED: '+type(exc).__name__, file=sys.stderr)
        return 2
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
