"""Privileged disposable-Linux four-UID verification; not a production safety certificate.

Uses kernel getpeercred, actual Unix file permissions and SIGKILL (exit -9).
The trusted root test orchestrator deliberately provisions and mutates files.
"""
import json
import os
import pathlib
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from island.attested_broker import ALL_CRASH_POINTS
EVIDENCE = ROOT / 'evidence'
U = {'client': 24001, 'service': 24002, 'broker': 24003, 'witness': 24004}
GID = 24000
R = {'stage': 'ISLAND-GEO-021', 'environment': {'uid': os.geteuid(), 'linux': sys.platform},
     'uids': U, 'checks': {}, 'crash_matrix': [], 'processes': [], 'limitations': [
         'Root test controller may replace every file and impersonate every UID',
         'Witness and permit authority intentionally share UID 24004',
         'Broker UID code execution can call legacy Python APIs directly',
         'No external secure monotonic root: simultaneous local/witness rollback not ruled out',
         'No power-loss/fsync hardware fault injection or independently certified MAC policy',
         'Test-only root removes orphaned sockets after SIGKILL',
     ]}
PROCS = []
SEQ = 0


def drop(role):
    def f():
        os.setgroups([])
        os.setgid(GID)
        os.setuid(U[role])
        os.umask(0o077)
    return f


def command(role, args, background=False, token=None, timeout=12):
    global SEQ
    SEQ += 1
    name = f'{SEQ:03}-{role}-{args[0]}'
    argv = [sys.executable, '-m', 'island.attested_runtime', *args]
    env = {**os.environ, 'PYTHONPATH': str(ROOT), 'PYTHONDONTWRITEBYTECODE': '1',
           'PYTHONWARNINGS': 'error::ResourceWarning,error::DeprecationWarning'}
    logdir = EVIDENCE / 'stage022-fouruid-process'
    logdir.mkdir(exist_ok=True)
    record = {'name': name, 'role': role, 'stdout': f'stage022-fouruid-process/{name}.out',
              'stderr': f'stage022-fouruid-process/{name}.err', 'exit_code': None}
    R['processes'].append(record)
    read_fd = write_fd = None
    if token is not None:
        read_fd, write_fd = os.pipe()
        argv += ['--token-fd', str(read_fd)]
    if background:
        out = open(logdir / f'{name}.out', 'wb')
        err = open(logdir / f'{name}.err', 'wb')
        try:
            proc = subprocess.Popen(argv, env=env, cwd=ROOT, preexec_fn=drop(role),
                                    stdout=out, stderr=err,
                                    pass_fds=(() if read_fd is None else (read_fd,)))
            PROCS.append((proc, record))
        finally:
            out.close()
            err.close()
            if read_fd is not None:
                os.close(read_fd)
                try:
                    os.write(write_fd, token.encode('ascii'))
                finally:
                    os.close(write_fd)
        return proc
    if token is not None:
        raise RuntimeError('tokens permitted only through inherited FD to background broker')
    try:
        completed = subprocess.run(argv, env=env, cwd=ROOT, preexec_fn=drop(role),
                                   capture_output=True, timeout=timeout)
        (logdir / f'{name}.out').write_bytes(b'[REDACTED DIRECT-CLIENT RECOVERY TOKEN]\n' if args[0]=='permit' else completed.stdout)
        (logdir / f'{name}.err').write_bytes(completed.stderr)
        record['exit_code'] = completed.returncode
        return completed
    except subprocess.TimeoutExpired:
        record['exit_code'] = 'TIMEOUT'
        raise


def finish(proc, sig=signal.SIGTERM):
    if proc.poll() is None:
        os.kill(proc.pid, sig)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill(); proc.wait(timeout=5)
    for p, info in PROCS:
        if p is proc:
            info['exit_code'] = proc.returncode
            break
    return proc.returncode


def wait_socket(path, proc, timeout=5):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if path.is_socket():
            return
        if proc.poll() is not None:
            break
        time.sleep(.02)
    for p, info in PROCS:
        if p is proc:
            raise RuntimeError(f'{info["name"]} not ready: {proc.returncode}: ' +
                               (EVIDENCE / info['stderr']).read_text(errors='replace')[-700:])
    raise RuntimeError('server startup timeout')


def result(name, passed, **details):
    R['checks'][name] = {'pass': bool(passed), **details}
    if not passed:
        raise AssertionError(name + ': ' + repr(details))


def negative_access(role, path, name):
    # An actual OS open, not a synthetic permission check.
    argv = [sys.executable, '-c', 'import os,sys;fd=os.open(sys.argv[1],os.O_RDWR|os.O_NOFOLLOW);os.close(fd)', str(path)]
    p = subprocess.run(argv, preexec_fn=drop(role), capture_output=True, timeout=5)
    result(name, p.returncode != 0 and b'PermissionError' in p.stderr, exit_code=p.returncode)


def main():
    if os.geteuid() != 0 or sys.platform != 'linux' or not hasattr(socket, 'SO_PEERCRED'):
        R['blocked'] = 'Linux root test orchestrator with SO_PEERCRED required'
        return 2
    with tempfile.TemporaryDirectory(prefix='island021-') as td:
        base = pathlib.Path(td)
        os.chmod(base, 0o711)
        ipc = base / 'ipc'
        ipc.mkdir()
        os.chmod(ipc, 0o1777)
        for role in U:
            directory = base / role
            directory.mkdir()
            os.chown(directory, U[role], GID)
            os.chmod(directory, 0o700)
        ws = ipc / 'w.sock'
        bs = ipc / 'b.sock'
        fs = ipc / 'f.sock'
        wd = base / 'witness' / 'w.db'
        pd = base / 'witness' / 'p.db'
        bd = base / 'broker' / 'b.db'
        private_path = base / 'client' / 'private.key'
        public_path = base / 'broker' / 'client.pub'
        key = Ed25519PrivateKey.generate()
        private_path.write_bytes(key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()))
        public_path.write_bytes(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))
        for path, role in ((private_path, 'client'), (public_path, 'broker')):
            os.chown(path, U[role], GID)
            os.chmod(path, 0o600)
        os.chmod(private_path.parent, 0o700)
        def authority_args():
            return ['authority','--socket',str(ws),'--db',str(wd),'--permit-db',str(pd),
                    '--client-uid',str(U['client']),'--broker-uid',str(U['broker'])]
        def broker_args(point=None, sock=bs):
            args = ['broker','--socket',str(sock),'--db',str(bd),'--authority',str(ws),
                    '--public-key',str(public_path),'--client-uid',str(U['client']),
                    '--service-uid',str(U['service']),'--witness-uid',str(U['witness'])]
            if point:
                args += ['--crash-at',point]
            return args
        def facade_args():
            return ['facade','--socket',str(fs),'--broker-socket',str(bs),
                    '--client-uid',str(U['client']),'--broker-uid',str(U['broker']),
                    '--witness-uid',str(U['witness'])]
        def permit():
            response = command('client',['permit','--socket',str(ws),'--witness-uid',str(U['witness'])])
            if response.returncode != 0:
                raise RuntimeError('direct client permit issuance failed: ' + response.stderr.decode()[-350:])
            return json.loads(response.stdout)['token']
        def start_broker(point=None, sock=bs):
            if sock.exists() or sock.is_symlink():
                # Privileged disposable-test controller is allowed to clean stale crash socket.
                sock.unlink()
            p = command('broker', broker_args(point,sock), background=True, token=permit())
            wait_socket(sock,p)
            return p
        def signed_path(payload):
            sign = command('client',['sign','--private-key',str(private_path),
                      '--broker-uid',str(U['broker']),'--payload',payload])
            if sign.returncode != 0:
                raise RuntimeError('signing failed: ' + sign.stderr.decode()[-400:])
            filename = base / ('message-' + str(len(list(base.glob('message-*')))) + '.json')
            filename.write_bytes(sign.stdout)
            os.chmod(filename,0o644)
            return filename
        def submit(path):
            return command('client',['submit','--socket',str(fs),'--facade-uid',str(U['service']),
                                     '--envelope-file',str(path)])
        def client(payload):
            return command('client',['client','--socket',str(fs),'--facade-uid',str(U['service']),
                '--private-key',str(private_path),'--broker-uid',str(U['broker']),'--payload',payload])
        w = command('witness',authority_args(),background=True)
        wait_socket(ws,w)
        result('witness_peer_owner', ws.stat().st_uid == U['witness'])
        b = start_broker()
        f = command('service',facade_args(),background=True)
        wait_socket(fs,f)
        result('four_uid_real_processes', all(p.poll() is None for p in (w,b,f)) and
               len(set(U.values())) == 4, pids={'witness':w.pid,'broker':b.pid,'facade':f.pid})
        good_path = signed_path('signed-first')
        good = submit(good_path)
        result('direct_client_signed_admission', good.returncode == 0,
               response=good.stdout.decode(errors='replace')[-500:])
        replay = submit(good_path)
        result('signed_replay_denied',replay.returncode!=0,exit_code=replay.returncode)
        forged = json.loads(good_path.read_text())
        forged['message']['payload']='666f72676564'
        forged_path = base / 'forged.json'
        forged_path.write_text(json.dumps(forged))
        os.chmod(forged_path,0o644)
        invalid = submit(forged_path)
        result('service_cannot_forge_client_signature',invalid.returncode!=0,exit_code=invalid.returncode)
        negative_access('service',bd,'facade_legacy_ledger_denied')
        negative_access('client',bd,'client_legacy_ledger_denied')
        negative_access('witness',bd,'witness_legacy_ledger_denied')
        negative_access('service',private_path,'facade_cannot_read_client_key')
        negative_access('broker',private_path,'broker_cannot_read_client_key')
        negative_access('service',wd,'facade_cannot_read_witness')
        negative_access('client',pd,'client_cannot_read_permits')
        result('socket_owner_separation',
               [p.stat().st_uid for p in (ws,bs,fs)] == [U['witness'],U['broker'],U['service']])
        # Peer authentication rejects direct client to broker, even with a genuine signature.
        snippet = ('from island.attested_broker import AttestedBrokerClient;'
                   'import json,sys;AttestedBrokerClient(sys.argv[1],24003).admit(json.load(open(sys.argv[2])))')
        direct = subprocess.run([sys.executable,'-c',snippet,str(bs),str(good_path)],
                                cwd=ROOT,env={**os.environ,'PYTHONPATH':str(ROOT)},
                                preexec_fn=drop('client'),capture_output=True,timeout=5)
        result('broker_rejects_direct_client_peer',direct.returncode != 0 and b'AdmissionDenied' in direct.stderr)
        # Exclusive lifetime lease: 2nd broker with different socket fails, even with fresh permit.
        competing = command('broker',broker_args(sock=ipc/'competing.sock'),background=True,token=permit())
        try:
            rc = competing.wait(timeout=5)
        except subprocess.TimeoutExpired:
            rc = None
        result('concurrent_broker_startup_denied',rc is not None and rc != 0,exit_code=rc)
        finish(competing)
        finish(b)
        # 17 real broker process deaths; each restart proves reconciliation and forward progress.
        for index, point in enumerate(ALL_CRASH_POINTS):
            b = start_broker(point)
            triggered = client('killpoint-' + str(index))
            try:
                died = b.wait(timeout=5)
            except subprocess.TimeoutExpired:
                died = None
            finish(b, signal.SIGKILL if died is None else signal.SIGTERM)
            record = {'point':point,'broker_exit':b.returncode,'request_exit':triggered.returncode,
                      'restarted':False,'fresh_admission':False}
            R['crash_matrix'].append(record)
            if b.returncode != -signal.SIGKILL:
                raise AssertionError('crash point did not kill broker: ' + repr(record))
            b = start_broker()
            record['restarted'] = b.poll() is None
            fresh = client('recovered-' + str(index))
            record['fresh_admission'] = fresh.returncode == 0
            if fresh.returncode != 0:
                raise AssertionError('recovered broker refused admission: ' + fresh.stderr.decode()[-700:])
            finish(b)
        result('real_sigkill_matrix',len(R['crash_matrix']) == len(ALL_CRASH_POINTS)
               and all(p['broker_exit']==-signal.SIGKILL and p['restarted'] and p['fresh_admission']
                       for p in R['crash_matrix']),count=len(R['crash_matrix']))
        # Each off-line tamper must be rejected at startup; repairs are root test-only.
        lock = base/'broker'/'.broker-startup.lock'
        with closing(sqlite3.connect(bd)) as db:
            old=db.execute('SELECT COUNT(*) FROM accepted').fetchone()[0]
            result('admission_chain_advanced',old>=19,sequence_count=old)
        old_mode = lock.stat().st_mode & 0o777
        lock.rename(lock.with_suffix('.safe'))
        lock.symlink_to(lock.with_suffix('.safe'))
        rejected = command('broker',broker_args(),background=True,token=permit())
        rc = rejected.wait(timeout=5)
        result('startup_lock_symlink_denied',rc!=0,exit_code=rc)
        finish(rejected)
        lock.unlink()
        lock.with_suffix('.safe').rename(lock)
        # Simulate a malicious root write to phase journal; do not infer root resistance.
        with closing(sqlite3.connect(bd)) as db:
            db.execute('INSERT OR REPLACE INTO phase VALUES (1,?,?,?,?)',
                       (999,'f'*64,'f'*64,'f'*64))
            db.commit()
        rejected = command('broker',broker_args(),background=True,token=permit())
        rc = rejected.wait(timeout=5)
        result('phase_journal_tampering_denied',rc!=0,exit_code=rc)
        finish(rejected)
        with closing(sqlite3.connect(bd)) as db:
            db.execute('DELETE FROM phase WHERE id=1');db.commit()
        # Replace ledger with symlink for startup; preserve original bytes for rollback of test.
        original = bd.with_suffix('.saved')
        bd.rename(original)
        bd.symlink_to(original)
        rejected = command('broker',broker_args(),background=True,token=permit())
        rc = rejected.wait(timeout=5)
        result('ledger_symlink_denied',rc!=0,exit_code=rc)
        finish(rejected)
        bd.unlink(); original.rename(bd)
        # SQLite sidecar and checkpoint/wal symlink probes.
        for suffix in ('-journal','-wal','-shm'):
            target = pathlib.Path(str(bd)+suffix)
            if target.exists():
                raise AssertionError('unexpected existing SQLite sidecar: '+str(target))
            target.symlink_to(bd)
            rejected = command('broker',broker_args(),background=True,token=permit())
            rc = rejected.wait(timeout=5)
            result('sqlite_sidecar_'+suffix[1:]+'_denied',rc!=0,exit_code=rc)
            finish(rejected)
            target.unlink()
        # Socket occupation and fake/root-owned IPC endpoint fail closed.
        if bs.exists(): bs.unlink()  # controller removes last stopped broker socket
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as fake:
            fake.bind(str(bs)); fake.listen(2)
            rejected = command('broker',broker_args(),background=True,token=permit())
            rc = rejected.wait(timeout=5)
            result('occupied_broker_socket_denied',rc!=0,exit_code=rc)
            finish(rejected)
        if bs.exists():bs.unlink()
        # Facade must refuse a root-owned socket impersonating the broker.
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as fake_peer:
            fake_peer.bind(str(bs));os.chmod(bs,0o660);os.chown(bs,0,GID)
            fake_peer.listen(2)
            spoofed = client('fake-broker-peer')
            result('root_owned_fake_broker_peer_denied',spoofed.returncode != 0,
                   exit_code=spoofed.returncode)
        if bs.exists():bs.unlink()
        # Authority permit DB symlink substitution must fail preflight before socket publication.
        finish(w)
        if ws.exists():ws.unlink()
        original_permit = pd.with_suffix('.saved')
        pd.rename(original_permit)
        pd.symlink_to(original_permit)
        substituted = command('witness',authority_args(),background=True)
        try:
            denied = substituted.wait(timeout=5)
        except subprocess.TimeoutExpired:
            denied = None
        result('permit_database_symlink_denied',denied is not None and denied != 0,
               exit_code=denied)
        finish(substituted)
        pd.unlink();original_permit.rename(pd)
        # Witness database genesis rollback after committed local chain.
        for ext in ('','-journal','-wal','-shm'):
            path=pathlib.Path(str(wd)+ext)
            if path.exists():path.unlink()
        if ws.exists():ws.unlink()
        w = command('witness',authority_args(),background=True)
        wait_socket(ws,w)
        rejected = command('broker',broker_args(),background=True,token=permit())
        rc = rejected.wait(timeout=5)
        result('witness_genesis_rollback_denied',rc!=0,exit_code=rc)
        finish(rejected)
        finish(f)
        finish(w)
    return 0


if __name__ == '__main__':
    try:
        exit_code = main()
    except Exception as exc:
        R['error'] = repr(exc)
        exit_code = 1
    finally:
        for proc, record in PROCS:
            if proc.poll() is None:
                finish(proc)
            record['exit_code'] = proc.returncode
        R['success'] = exit_code == 0 and all(x['pass'] for x in R['checks'].values())
        (EVIDENCE/'stage022-fouruid-e2e.json').write_text(json.dumps(R, indent=2, sort_keys=True)+'\n')
        print(json.dumps({'success':R['success'], 'checks':R['checks'],
                          'crash_count':len(R['crash_matrix']), 'error':R.get('error')},indent=2))
    sys.exit(exit_code)
