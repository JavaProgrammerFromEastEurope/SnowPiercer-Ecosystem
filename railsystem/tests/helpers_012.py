"""NONPRODUCTION, volatile provider fakes. Never deploy as witness or permit ledger."""
import json
import os
import signal
import socket
import stat
import tempfile
import time
from pathlib import Path

GID = 62580
CLIENT, SERVICE, WITNESS, RECOVERY = 62581, 62582, 62583, 62584


def drop(uid, gid=GID):
    os.setgroups([gid])
    os.setgid(gid)
    os.setuid(uid)


def launch_provider(parent, uid, kind):
    folder = parent / (kind + '-ipc')
    folder.mkdir(mode=0o750)
    os.chown(folder, uid, GID)
    path = folder / 'provider.sock'
    rd, wr = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(rd)
        try:
            drop(uid)
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(str(path))
                os.chmod(path, 0o660)
                server.listen(8)
                os.write(wr, b'R')
                os.close(wr)
                sequence, nonce, used = 0, '', set()
                while True:
                    conn, _ = server.accept()
                    with conn:
                        conn.settimeout(3)
                        raw = bytearray()
                        while not raw.endswith(b'\n') and len(raw) < 4096:
                            block = conn.recv(4096 - len(raw))
                            if not block: break
                            raw.extend(block)
                        try:
                            req = json.loads(raw)
                            response = {'domain':'snowpiercer.railsystem.provider.v1',
                                        'kind':req['kind'], 'operation':req['operation'], 'status':'OK'}
                            if req['domain'] != response['domain'] or req['kind'] != kind:
                                raise ValueError('domain/kind')
                            if kind == 'anchor':
                                if req['operation'] == 'read':
                                    response.update(sequence=sequence, nonce=nonce)
                                elif req['operation'] == 'advance':
                                    previous, target = req['expected'], req['next']
                                    valid = (previous == [sequence,nonce] and target[0] > sequence)
                                    if valid: sequence,nonce = target
                                    response['advanced'] = bool(valid)
                                else: raise ValueError('verb')
                            elif req['operation'] == 'ready': response['ready'] = True
                            elif req['operation'] == 'consume':
                                digest = req['digest']; response['consumed'] = digest not in used
                                used.add(digest)
                            else: raise ValueError('verb')
                        except Exception:
                            response = {'domain':'snowpiercer.railsystem.provider.v1',
                                        'kind':kind, 'operation':'invalid', 'status':'DENIED'}
                        conn.sendall(json.dumps(response, sort_keys=True).encode()+b'\n')
        except BaseException:
            try: os.write(wr, b'E')
            except OSError: pass
        os._exit(0)
    os.close(wr)
    try:
        import select
        readable, _, _ = select.select([rd], [], [], 4)
        if not readable or os.read(rd, 1) != b'R':
            raise RuntimeError('test-only provider failed to start')
    finally:
        os.close(rd)
    return pid, path


def stop_provider(pid):
    try: os.kill(pid, signal.SIGTERM)
    except ProcessLookupError: pass
    try: os.waitpid(pid, 0)
    except ChildProcessError: pass
