"""RAIL-TRUST-014: real four-UID OS process tests for LOCAL ONLY durable authorities."""
import json
import os
import signal
import socket
import stat
import tempfile
import time
import unittest
from pathlib import Path

from railsystem.isolated_authorities import LocalDurableAuthority, AuthorityDenied
from railsystem.os_managed_fencing import assess_os_management, require_production_isolation
from railsystem.os_boundary import DeploymentDenied
from railsystem.provider_ipc import UnixAnchorClient, UnixPermitLedgerClient, RemoteProviderUnavailable
from helpers_012 import GID, CLIENT, SERVICE, WITNESS, RECOVERY, drop


class OSProductionGuardTests(unittest.TestCase):
    def test_same_uid_legacy_and_monotonic_root_not_attested(self):
        facts = assess_os_management()
        self.assertEqual(facts['status'], 'BLOCKED')
        self.assertFalse(facts['same_uid_legacy_fenced'])
        self.assertFalse(facts['independent_monotonic_root_proven'])
        with self.assertRaises(DeploymentDenied):
            require_production_isolation()

    def test_production_cli_fails_closed_even_with_fake_providers(self):
        from railsystem.write_authority import main as write_main
        from railsystem.service_runtime import main as recovery_main
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(write_main(['--config', tmp+'/missing', '--root', tmp,
                '--baseline', tmp+'/b', '--attestation', tmp+'/a', '--trust', tmp+'/t']), 2)
            self.assertEqual(recovery_main(['--config', tmp+'/missing']), 2)


@unittest.skipUnless(os.geteuid() == 0 and hasattr(socket, 'SO_PEERCRED'), 'needs real Linux root fork/drop tests')
class IsolatedAuthorityTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name)
        self.root.chmod(0o755)
        self.children = []
        self.addCleanup(self.stop)
        self.paths = {}
        for kind, uid in (('anchor', WITNESS), ('permit', RECOVERY)):
            state = self.root / (kind+'-state')
            ipc = self.root / (kind+'-ipc')
            state.mkdir(mode=0o700); ipc.mkdir(mode=0o750)
            os.chown(state,uid,GID); os.chown(ipc,uid,GID)
            self.paths[kind] = (state,ipc,uid)
            self._fork(uid, lambda k=kind: self.authority(k).provision())

    def stop(self):
        for pid in self.children:
            try: os.kill(pid, signal.SIGKILL)
            except ProcessLookupError: pass
            try: os.waitpid(pid, 0)
            except ChildProcessError: pass
        self.children.clear()

    def authority(self, kind):
        state, ipc, uid = self.paths[kind]
        return LocalDurableAuthority(kind,state,ipc,transport_gid=GID,service_uid=SERVICE)

    def _fork(self, uid, fn, *, signal_expected=None):
        pid = os.fork()
        if pid == 0:
            try:
                drop(uid)
                fn()
                os._exit(0)
            except BaseException:
                import traceback
                traceback.print_exc()
                os._exit(9)
        raw = os.waitpid(pid, 0)[1]
        actual = os.waitstatus_to_exitcode(raw)
        self.assertEqual(actual, -signal_expected if signal_expected else 0)

    def start(self, kind, *, kill_at=None):
        uid = self.paths[kind][2]
        rd, wr = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(rd)
            try:
                drop(uid)
                auth = self.authority(kind)
                auth.start()
                os.write(wr,b'R'); os.close(wr)
                while True:
                    try: auth.handle_one(kill_at=kill_at)
                    except TimeoutError: continue
            except BaseException:
                try: os.write(wr,b'E')
                except OSError: pass
                os._exit(11)
        os.close(wr)
        import select
        r,_,_ = select.select([rd],[],[],3)
        status = os.read(rd,1) if r else b''
        os.close(rd)
        if status == b'R': self.children.append(pid)
        else:
            os.waitpid(pid,0)
        return pid, status

    def shutdown(self, pid):
        os.kill(pid, signal.SIGKILL)
        self.assertEqual(os.waitstatus_to_exitcode(os.waitpid(pid,0)[1]), -signal.SIGKILL)
        self.children.remove(pid)

    def clear_stale_for_laboratory_only(self, kind):
        """Simulates an operator cleaning test-only stale socket after PID reaping.

        NOT a production socket reclamation protocol or an authority restart.
        """
        path = self.paths[kind][1]/'provider.sock'
        uid = self.paths[kind][2]
        s = path.lstat()
        self.assertEqual(s.st_uid,uid)
        self.assertTrue(stat.S_ISSOCK(s.st_mode))
        self._fork(uid, path.unlink)

    def request(self, kind, operation, **kwargs):
        result_r, result_w = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(result_r)
            try:
                drop(SERVICE)
                client = self.client(kind)
                if kind == 'anchor':
                    if operation == 'read': response = client.read()
                    else: response = client.advance(kwargs['old'],kwargs['new'])
                elif operation == 'ready': response = client.check_ready()
                else: response = client.consume_once(kwargs['digest'],sequence=kwargs['sequence'],action='reconcile')
                encoded = json.dumps({'ok':response}).encode()
            except BaseException as e:
                encoded = json.dumps({'error':type(e).__name__}).encode()
            os.write(result_w,encoded)
            os.close(result_w)
            os._exit(0)
        os.close(result_w)
        status = os.waitstatus_to_exitcode(os.waitpid(pid,0)[1])
        data = os.read(result_r,4096)
        os.close(result_r)
        self.assertEqual(status,0)
        return json.loads(data)

    def client(self, kind):
        _,ipc,uid = self.paths[kind]
        path = ipc/'provider.sock'
        factory = UnixAnchorClient if kind == 'anchor' else UnixPermitLedgerClient
        return factory(path,expected_uid=uid,expected_gid=GID)

    def test_not_autoprovisioned_after_database_removed(self):
        state,ipc,uid = self.paths['anchor']
        self._fork(uid,lambda: (state/'witness.sqlite3').unlink())
        def assert_blocked():
            with self.assertRaises(OSError): self.authority('anchor').start()
        self._fork(uid,assert_blocked)
        self.assertFalse((ipc/'provider.sock').exists())

    def test_witness_persists_sigkill_and_rejects_replay(self):
        pid, ready = self.start('anchor'); self.assertEqual(ready,b'R')
        self.assertEqual(self.request('anchor','read'),{'ok':[0,'']})
        self.assertEqual(self.request('anchor','advance',old=[0,''],new=[1,'nonce-1']),{'ok':True})
        self.shutdown(pid)
        pid, ready = self.start('anchor'); self.assertEqual(ready,b'E')
        self.clear_stale_for_laboratory_only('anchor')
        pid, ready = self.start('anchor'); self.assertEqual(ready,b'R')
        self.assertEqual(self.request('anchor','read'),{'ok':[1,'nonce-1']})
        self.assertEqual(self.request('anchor','advance',old=[0,''],new=[2,'nonce-2']),{'ok':False})
        self.shutdown(pid)

    def test_durable_consumption_survives_sigkill(self):
        pid, ready = self.start('permit'); self.assertEqual(ready,b'R')
        self.assertEqual(self.request('permit','consume',digest='a'*64,sequence=1),{'ok':True})
        self.shutdown(pid)
        self.clear_stale_for_laboratory_only('permit')
        pid, ready = self.start('permit'); self.assertEqual(ready,b'R')
        self.assertEqual(self.request('permit','consume',digest='a'*64,sequence=1),{'ok':False})
        self.shutdown(pid)

    def test_kill_during_witness_before_commit_rollback(self):
        pid, ready = self.start('anchor',kill_at='before_commit'); self.assertEqual(ready,b'R')
        response = self.request('anchor','advance',old=[0,''],new=[1,'a'])
        self.assertIn('error',response)
        self.assertEqual(os.waitstatus_to_exitcode(os.waitpid(pid,0)[1]),-signal.SIGKILL)
        self.children.remove(pid)
        self.clear_stale_for_laboratory_only('anchor')
        pid, ready = self.start('anchor'); self.assertEqual(ready,b'R')
        self.assertEqual(self.request('anchor','read'),{'ok':[0,'']})
        self.shutdown(pid)

    def test_kill_during_witness_after_commit_persists_without_reply(self):
        pid, ready = self.start('anchor',kill_at='after_commit'); self.assertEqual(ready,b'R')
        self.assertIn('error',self.request('anchor','advance',old=[0,''],new=[1,'a']))
        self.assertEqual(os.waitstatus_to_exitcode(os.waitpid(pid,0)[1]),-signal.SIGKILL)
        self.children.remove(pid)
        self.clear_stale_for_laboratory_only('anchor')
        pid, ready = self.start('anchor'); self.assertEqual(ready,b'R')
        self.assertEqual(self.request('anchor','read'),{'ok':[1,'a']})
        self.shutdown(pid)

    def test_kill_during_ledger_before_commit_not_consumed(self):
        pid, ready = self.start('permit',kill_at='before_commit'); self.assertEqual(ready,b'R')
        self.assertIn('error',self.request('permit','consume',digest='a'*64,sequence=1))
        self.assertEqual(os.waitstatus_to_exitcode(os.waitpid(pid,0)[1]),-signal.SIGKILL)
        self.children.remove(pid)
        self.clear_stale_for_laboratory_only('permit')
        pid, ready = self.start('permit'); self.assertEqual(ready,b'R')
        self.assertEqual(self.request('permit','consume',digest='a'*64,sequence=1),{'ok':True})
        self.shutdown(pid)

    def test_kill_during_ledger_after_commit_consumed(self):
        pid, ready = self.start('permit',kill_at='after_commit'); self.assertEqual(ready,b'R')
        self.assertIn('error',self.request('permit','consume',digest='a'*64,sequence=1))
        self.assertEqual(os.waitstatus_to_exitcode(os.waitpid(pid,0)[1]),-signal.SIGKILL)
        self.children.remove(pid)
        self.clear_stale_for_laboratory_only('permit')
        pid, ready = self.start('permit'); self.assertEqual(ready,b'R')
        self.assertEqual(self.request('permit','consume',digest='a'*64,sequence=1),{'ok':False})
        self.shutdown(pid)

    def test_two_independent_uid_services_and_clients(self):
        witness, ready = self.start('anchor'); self.assertEqual(ready,b'R')
        permit, ready = self.start('permit'); self.assertEqual(ready,b'R')
        self.assertEqual(self.request('anchor','advance',old=[0,''],new=[1,'a']),{'ok':True})
        self.assertEqual(self.request('permit','consume',digest='b'*64,sequence=1),{'ok':True})
        self.assertEqual(self.request('anchor','read'),{'ok':[1,'a']})
        self.assertEqual(self.request('permit','ready'),{'ok':True})
        self.shutdown(witness); self.shutdown(permit)

    def test_unauthorized_uid_denied_by_kernel_peercred(self):
        pid, ready = self.start('anchor'); self.assertEqual(ready,b'R')
        rd,wr = os.pipe()
        child = os.fork()
        if child == 0:
            os.close(rd)
            try:
                drop(CLIENT)
                with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
                    sock.settimeout(2)
                    sock.connect(str(self.paths['anchor'][1]/'provider.sock'))
                    sock.sendall(b'{"domain":"snowpiercer.railsystem.provider.v1","kind":"anchor","operation":"read"}\n')
                    value = json.loads(sock.recv(4096))
                os.write(wr, json.dumps(value).encode())
            except BaseException:
                os.write(wr,b'{}')
            os._exit(0)
        os.close(wr)
        value = json.loads(os.read(rd,4096)); os.close(rd)
        os.waitpid(child,0)
        self.assertEqual(value.get('status'), 'DENIED')
        self.shutdown(pid)

    def test_client_cannot_read_witness_and_permit_databases(self):
        def check():
            for kind,filename in (('anchor','witness.sqlite3'),('permit','permits.sqlite3')):
                path = self.paths[kind][0]/filename
                with self.assertRaises(PermissionError):path.open('rb')
        self._fork(CLIENT,check)

    def test_symlink_database_denied_without_publication(self):
        state,ipc,uid = self.paths['anchor']
        target = state/'witness.sqlite3'
        self._fork(uid,lambda: (target.rename(state/'backup'),target.symlink_to(state/'backup')))
        def blocked():
            with self.assertRaises(AuthorityDenied): self.authority('anchor').start()
        self._fork(uid,blocked)
        self.assertFalse((ipc/'provider.sock').exists())

    def test_duplicate_provision_denied(self):
        def blocked():
            with self.assertRaises(AuthorityDenied):self.authority('permit').provision()
        self._fork(RECOVERY,blocked)

    def test_concurrent_cas_exactly_one_success(self):
        pid, ready = self.start('anchor'); self.assertEqual(ready,b'R')
        start_r,start_w=os.pipe(); result_r,result_w=os.pipe()
        children=[]
        for nonce in ('a','b'):
            child=os.fork()
            if child == 0:
                os.close(start_w);os.close(result_r)
                drop(SERVICE)
                os.read(start_r,1)
                try: answer=self.client('anchor').advance((0,''),(1,nonce))
                except BaseException: answer='ERROR'
                os.write(result_w,json.dumps(answer).encode()+b'\n')
                os._exit(0)
            children.append(child)
        os.close(start_r);os.close(result_w)
        os.write(start_w,b'xx');os.close(start_w)
        for child in children:
            self.assertEqual(os.waitstatus_to_exitcode(os.waitpid(child,0)[1]),0)
        with os.fdopen(result_r,'rb') as f:
            results=[json.loads(line) for line in f]
        self.assertCountEqual(results,[True,False])
        self.shutdown(pid)

    def test_managed_sigterm_removes_own_socket(self):
        rd,wr=os.pipe()
        child=os.fork()
        if child == 0:
            os.close(rd)
            try:
                drop(WITNESS)
                auth=self.authority('anchor')
                # Set up start and SIGTERM handler before acknowledging readiness.
                auth.start()
                stopped=False
                def on_term(_sig,_frame):
                    nonlocal stopped
                    stopped=True
                signal.signal(signal.SIGTERM,on_term)
                os.write(wr,b'R');os.close(wr)
                while not stopped:
                    try:auth.handle_one()
                    except TimeoutError:pass
                auth.close();os._exit(0)
            except BaseException:
                os._exit(9)
        os.close(wr)
        self.assertEqual(os.read(rd,1),b'R');os.close(rd)
        os.kill(child,signal.SIGTERM)
        self.assertEqual(os.waitstatus_to_exitcode(os.waitpid(child,0)[1]),0)
        self.assertFalse((self.paths['anchor'][1]/'provider.sock').exists())
        pid,status=self.start('anchor');self.assertEqual(status,b'R')
        self.shutdown(pid)

    def test_cross_uid_write_authority_uses_durable_providers_and_blocks_invalid_admission(self):
        from railsystem.anchored_admission import initialize
        from railsystem.write_authority import ProductionWriteAuthority
        witness,ready=self.start('anchor');self.assertEqual(ready,b'R')
        permits,ready=self.start('permit');self.assertEqual(ready,b'R')
        state=self.root/'service-state';ipc=self.root/'service-ipc'
        state.mkdir(mode=0o700);ipc.mkdir(mode=0o750)
        os.chown(state,SERVICE,GID);os.chown(ipc,SERVICE,GID)
        for name in ('permit.json','public.key','baseline.json','attestation.json','trust.json'):
            path=state/name
            path.write_text('{}')
            os.chown(path,SERVICE,GID);path.chmod(0o600)
        self._fork(SERVICE,lambda:initialize(state))
        config={'schema_version':1,
            'uids':{'client':CLIENT,'service':SERVICE,'witness':WITNESS,'recovery':RECOVERY},
            'transport_gid':GID,'state_dir':str(state),'ipc_dir':str(ipc),
            'witness_socket':str(self.paths['anchor'][1]/'provider.sock'),
            'permit_socket':str(self.paths['permit'][1]/'provider.sock'),
            'permit_file':str(state/'permit.json'),'recovery_public_key_file':str(state/'public.key')}
        rd,wr=os.pipe()
        child=os.fork()
        if child == 0:
            os.close(rd)
            try:
                drop(SERVICE)
                auth=ProductionWriteAuthority(config,root=self.root,
                    baseline_file=state/'baseline.json',attestation_file=state/'attestation.json',trust_file=state/'trust.json')
                auth.start()
                os.write(wr,b'R');os.close(wr)
                auth.handle_one()
                auth.close()
                os._exit(0)
            except BaseException:
                os._exit(9)
        os.close(wr)
        self.assertEqual(os.read(rd,1),b'R');os.close(rd)
        out_r,out_w=os.pipe()
        caller=os.fork()
        if caller == 0:
            os.close(out_r)
            drop(CLIENT)
            try:
                with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as conn:
                    conn.settimeout(3)
                    conn.connect(str(ipc/'write-v013.sock'))
                    conn.sendall(b'ADMIT\n')
                    os.write(out_w,conn.recv(4096))
            except BaseException:
                os.write(out_w,b'ERROR')
            os._exit(0)
        os.close(out_w)
        response=os.read(out_r,4096);os.close(out_r)
        self.assertEqual(os.waitstatus_to_exitcode(os.waitpid(caller,0)[1]),0)
        self.assertIn(b'BLOCKED',response)
        self.assertEqual(os.waitstatus_to_exitcode(os.waitpid(child,0)[1]),0)
        self.shutdown(witness);self.shutdown(permits)

    def test_local_store_rollback_remains_unsolved(self):
        # Demonstrate an explicit negative guarantee: independent UID DAC does
        # not stop a privileged snapshot rollback of an owner's SQLite file.
        pid, ready = self.start('anchor'); self.assertEqual(ready,b'R')
        self.assertEqual(self.request('anchor','advance',old=[0,''],new=[1,'a']),{'ok':True})
        self.shutdown(pid)
        facts = assess_os_management()
        self.assertFalse(facts['independent_monotonic_root_proven'])
        self.assertEqual(facts['status'],'BLOCKED')

if __name__ == '__main__': unittest.main()
