"""RAIL-TRUST-013: real Linux four-UID *negative* boundary tests.

Witness/ledger servers are volatile test doubles, not production authorities.
"""
import json
import os
import signal
import socket
import stat
import tempfile
import time
import unittest
from pathlib import Path

from railsystem.anchored_admission import initialize, _connect
from railsystem.write_authority import ProductionWriteAuthority, WriteDenied
from railsystem.os_boundary import DeploymentDenied
from helpers_012 import GID, CLIENT, SERVICE, WITNESS, RECOVERY, drop, launch_provider, stop_provider

@unittest.skipUnless(os.geteuid() == 0 and hasattr(socket,'SO_PEERCRED'), 'needs Linux root for real four-UID fork test')
class WriteAuthorityTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.root.chmod(0o755)
        self.children=[]
        self.addCleanup(self.clean)
        self.a_pid, a = launch_provider(self.root, WITNESS, 'anchor')
        self.children.append(self.a_pid)
        self.p_pid, p = launch_provider(self.root, RECOVERY, 'permit')
        self.children.append(self.p_pid)
        state = self.root/'state'; state.mkdir(mode=0o700);os.chown(state,SERVICE,GID)
        ipc = self.root/'ipc'; ipc.mkdir(mode=0o750);os.chown(ipc,SERVICE,GID)
        self.state = state; self.ipc=ipc
        self.config={'schema_version':1,'uids':{'client':CLIENT,'service':SERVICE,'witness':WITNESS,'recovery':RECOVERY},
                     'transport_gid':GID, 'state_dir':str(state),'ipc_dir':str(ipc),
                     'witness_socket':str(a), 'permit_socket':str(p),
                     'permit_file':str(state/'permit.json'), 'recovery_public_key_file':str(state/'public.key')}
        self.paths={}
        for name in ('permit.json','public.key','baseline.json','attestation.json','trust.json'):
            f=state/name
            f.write_text('{}')
            os.chown(f,SERVICE,GID); f.chmod(0o600)
            self.paths[name]=f
        self.fork_wait(SERVICE,lambda:initialize(state))

    def clean(self):
        for pid in self.children:
            try:os.kill(pid,signal.SIGKILL)
            except ProcessLookupError:pass
            try:os.waitpid(pid,0)
            except ChildProcessError:pass
        self.children=[]

    def fork_wait(self,uid,fn):
        pid=os.fork()
        if pid==0:
            try:
                drop(uid)
                fn()
                os._exit(0)
            except BaseException:
                import traceback;traceback.print_exc();os._exit(1)
        code=os.waitstatus_to_exitcode(os.waitpid(pid,0)[1])
        self.assertEqual(code,0)

    def authority(self):
        return ProductionWriteAuthority(self.config, root=self.root,
            baseline_file=self.paths['baseline.json'],
            attestation_file=self.paths['attestation.json'],
            trust_file=self.paths['trust.json'])

    def spawn_service(self, *, linger=4):
        rd,wr=os.pipe()
        pid=os.fork()
        if pid==0:
            os.close(rd)
            try:
                drop(SERVICE)
                auth=self.authority();auth.start()
                os.write(wr,b'R');os.close(wr)
                auth.sock.settimeout(linger)
                try:auth.handle_one()
                except TimeoutError:pass
                auth.close()
                os._exit(0)
            except BaseException:
                try:os.write(wr,b'E')
                except OSError:pass
                os._exit(2)
        os.close(wr)
        import select
        r,_,_=select.select([rd],[],[],4)
        status=os.read(rd,1) if r else b''
        os.close(rd)
        self.children.append(pid)
        return pid,status

    def request(self, uid, command):
        rd,wr=os.pipe()
        pid=os.fork()
        if pid==0:
            os.close(rd)
            try:
                drop(uid)
                with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
                    client.settimeout(3)
                    client.connect(str(self.ipc/'write-v013.sock'))
                    client.sendall(command)
                    reply=client.recv(4096)
                os.write(wr,reply)
                os._exit(0)
            except BaseException:
                os._exit(8)
        os.close(wr)
        status=os.waitpid(pid,0)[1]
        reply=os.read(rd,4096)
        os.close(rd)
        return os.waitstatus_to_exitcode(status),reply

    def test_unauthorized_uid_denied_with_kernel_credentials(self):
        pid,status=self.spawn_service()
        self.assertEqual(status,b'R')
        code,data=self.request(WITNESS,b'ADMIT\n')
        self.assertEqual(code,0)
        self.assertIn(b'BLOCKED',data)

    def test_authorized_uid_cannot_submit_legacy_write(self):
        pid,status=self.spawn_service()
        self.assertEqual(status,b'R')
        code,data=self.request(CLIENT,b'LEGACY_WRITE\n')
        self.assertEqual(code,0)
        self.assertIn(b'BLOCKED',data)

    def test_authorized_uid_cannot_supply_policy_and_unapproved_admission_fails(self):
        pid,status=self.spawn_service()
        self.assertEqual(status,b'R')
        code,data=self.request(CLIENT,b'ADMIT\n')
        self.assertEqual(code,0)
        self.assertIn(b'BLOCKED',data) # empty, invalid attestation; not granted

    def test_client_cannot_directly_open_or_replace_protected_state(self):
        def reject():
            for path in (self.state/'admission.sqlite3',self.state/'anchor.json',self.paths['trust.json']):
                try: path.open('rb')
                except PermissionError: continue
                raise AssertionError('legacy direct write/read bypass permitted')
        self.fork_wait(CLIENT,reject)

    def test_two_simultaneous_startups_one_rejected(self):
        pid,status=self.spawn_service()
        self.assertEqual(status,b'R')
        def reject():
            try:self.authority().start()
            except WriteDenied:return
            raise AssertionError('second listener published')
        self.fork_wait(SERVICE,reject)

    def test_managed_sigterm_closes_owned_socket(self):
        rd,wr=os.pipe()
        pid=os.fork()
        if pid==0:
            os.close(rd)
            try:
                drop(SERVICE)
                from railsystem.write_authority import serve
                # tell the parent when the service is known to have started
                # via the socket path, then exercise the signal handler.
                os.close(wr)
                serve(self.config, root=self.root,
                      baseline_file=self.paths['baseline.json'],
                      attestation_file=self.paths['attestation.json'],
                      trust_file=self.paths['trust.json'])
                os._exit(0)
            except BaseException:
                os._exit(3)
        os.close(wr);os.close(rd)
        self.children.append(pid)
        path=self.ipc/'write-v013.sock'
        for _ in range(300):
            if path.exists():break
            time.sleep(0.01)
        self.assertTrue(path.exists())
        os.kill(pid,signal.SIGTERM)
        # Service handles SIGTERM without unlinking an unrelated socket.
        waited=os.waitpid(pid,0)[1]
        self.children.remove(pid)
        self.assertEqual(os.waitstatus_to_exitcode(waited),0)
        self.assertFalse(path.exists())

    def test_stale_socket_after_sigkill_blocks_restart(self):
        pid,status=self.spawn_service(linger=10)
        self.assertEqual(status,b'R')
        os.kill(pid,signal.SIGKILL)
        os.waitpid(pid,0)
        self.children.remove(pid)
        def reject():
            try:self.authority().start()
            except WriteDenied:return
            raise AssertionError('SIGKILL socket auto-unlinked')
        self.fork_wait(SERVICE,reject)
        self.assertTrue((self.ipc/'write-v013.sock').exists())

    def test_socket_substitution_is_detected_and_not_removed(self):
        pid,status=self.spawn_service(linger=10)
        self.assertEqual(status,b'R')
        path=self.ipc/'write-v013.sock'
        path.unlink()
        path.symlink_to(self.state/'anchor.json')
        def reject():
            auth=self.authority()
            auth.identity=(0,0)
            try:auth._verify_path()
            except WriteDenied:return
            raise AssertionError('substituted IPC socket was trusted')
        self.fork_wait(SERVICE,reject)
        os.kill(pid,signal.SIGKILL)
        os.waitpid(pid,0);self.children.remove(pid)
        self.assertTrue(path.is_symlink())

    def test_missing_witness_or_ledger_blocks_publication(self):
        os.kill(self.a_pid,signal.SIGKILL)
        os.waitpid(self.a_pid,0);self.children.remove(self.a_pid)
        def reject():
            try:self.authority().start()
            except Exception:return
            raise AssertionError('unresponsive witness accepted')
        self.fork_wait(SERVICE,reject)
        self.assertFalse((self.ipc/'write-v013.sock').exists())

    def test_permit_provider_crash_during_live_ipc_fails_closed(self):
        pid,status=self.spawn_service()
        self.assertEqual(status,b'R')
        os.kill(self.p_pid, signal.SIGKILL)
        os.waitpid(self.p_pid,0); self.children.remove(self.p_pid)
        code,data=self.request(CLIENT,b'ADMIT\n')
        self.assertEqual(code,0)
        self.assertIn(b'BLOCKED',data)

    def test_ipc_sigkill_mid_request_leaves_stale_path(self):
        pid,status=self.spawn_service(linger=10)
        self.assertEqual(status,b'R')
        path=self.ipc/'write-v013.sock'
        # Client keeps a partial command; killed service must not admit or
        # automatically unlink a path after the signal.
        rd,wr=os.pipe()
        client=os.fork()
        if client==0:
            os.close(rd)
            try:
                drop(CLIENT)
                with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
                    s.connect(str(path));s.sendall(b'ADM');os.write(wr,b'R');os.close(wr)
                    time.sleep(0.5)
                os._exit(0)
            except BaseException:os._exit(1)
        os.close(wr)
        import select
        readable,_,_=select.select([rd],[],[],2)
        self.assertTrue(readable)
        self.assertEqual(os.read(rd,1),b'R');os.close(rd)
        os.kill(pid,signal.SIGKILL)
        os.waitpid(pid,0);self.children.remove(pid)
        os.waitpid(client,0)
        self.assertTrue(path.exists())
        def reject():
            try:self.authority().start()
            except WriteDenied:return
            raise AssertionError('unsafe automatic restart after IPC SIGKILL')
        self.fork_wait(SERVICE,reject)

    def test_credential_directory_permissions_denied(self):
        self.state.chmod(0o750)
        def reject():
            try:self.authority().start()
            except (WriteDenied,DeploymentDenied,ValueError):return
            raise AssertionError('unsafe credential parent accepted')
        self.fork_wait(SERVICE,reject)

    def test_credential_symlink_and_permissions_are_denied(self):
        f=self.paths['trust.json']
        f.unlink();f.symlink_to(self.paths['baseline.json'])
        def reject():
            try:self.authority().start()
            except (WriteDenied,DeploymentDenied,ValueError):return
            raise AssertionError('symlink credentials accepted')
        self.fork_wait(SERVICE,reject)
        self.assertFalse((self.ipc/'write-v013.sock').exists())

    def test_wrong_role_uid_denied(self):
        def reject():
            try:self.authority().start()
            except DeploymentDenied:return
            raise AssertionError('client became write authority')
        self.fork_wait(CLIENT,reject)

    def test_prepared_recovery_blocks_publication(self):
        def prepared():
            c=_connect(self.state)
            try:
                c.execute('BEGIN IMMEDIATE')
                c.execute("UPDATE state SET phase='PREPARED', pending_sequence=1, pending_nonce='x' WHERE id=1")
                c.execute('COMMIT')
            finally:c.close()
        self.fork_wait(SERVICE,prepared)
        def reject():
            try:self.authority().start()
            except Exception:return
            raise AssertionError('recovery PREPARED bypassed')
        self.fork_wait(SERVICE,reject)
        self.assertFalse((self.ipc/'write-v013.sock').exists())

    def test_os_owner_tampering_detected(self):
        self.ipc.chmod(0o777)
        def reject():
            try:self.authority().start()
            except DeploymentDenied:return
            raise AssertionError('world-writable IPC directory trusted')
        self.fork_wait(SERVICE,reject)

if __name__ == '__main__': unittest.main()
