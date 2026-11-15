"""Four distinct actual Linux UIDs; volatile test backends are NOT production providers."""
import base64
import json
import os
import signal
import socket
import stat
import tempfile
import time
import unittest
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from railsystem.trust import canonical
from railsystem.os_boundary import validate_production_config, DeploymentDenied
from railsystem.provider_ipc import RemoteProviderUnavailable
from railsystem.anchored_admission import initialize, _connect, _state
from railsystem.service_runtime import serve
from helpers_012 import GID, CLIENT, SERVICE, WITNESS, RECOVERY, drop, launch_provider, stop_provider

@unittest.skipUnless(os.geteuid() == 0 and hasattr(socket,'SO_PEERCRED'), 'requires Linux root and peer credential verification')
class Boundary012Tests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name); self.root.chmod(0o755)
        self.children=[]
        self.addCleanup(self.stop)
        self.anchor_pid, anchor=launch_provider(self.root, WITNESS, 'anchor'); self.children.append(self.anchor_pid)
        self.permit_pid, permit=launch_provider(self.root, RECOVERY, 'permit'); self.children.append(self.permit_pid)
        state=self.root/'state';state.mkdir(mode=0o700);os.chown(state,SERVICE,GID)
        ipc=self.root/'ipc';ipc.mkdir(mode=0o750);os.chown(ipc,SERVICE,GID)
        self.config={'schema_version':1,'uids':{'client':CLIENT,'service':SERVICE,'witness':WITNESS,'recovery':RECOVERY},
                     'transport_gid':GID,'state_dir':str(state),'ipc_dir':str(ipc),
                     'witness_socket':str(anchor),'permit_socket':str(permit),
                     'permit_file':str(state/'permit.json'),'recovery_public_key_file':str(state/'public.key')}
        key=Ed25519PrivateKey.generate()
        public=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        payload={'domain':'snowpiercer.railsystem.recovery.v1','sequence':1,'action':'reconcile','permit_id':'a'*25}
        permit_obj={'payload':payload,'signature':base64.b64encode(key.sign(canonical(payload))).decode()}
        for path,data in ((state/'permit.json',json.dumps(permit_obj)),(state/'public.key',base64.b64encode(public).decode()),
                          (state/'deployment.json',json.dumps(self.config))):
            path.write_text(data); path.chmod(0o600); os.chown(path,SERVICE,GID)
        self._fork_and_wait(self._initialize_state)
    def stop(self):
        for pid in self.children:stop_provider(pid)
        self.children=[]
    def _fork_and_wait(self,action):
        pid=os.fork()
        if pid==0:
            try:
                drop(SERVICE)
                action()
                os._exit(0)
            except BaseException:
                import traceback
                traceback.print_exc()
                os._exit(1)
        self.assertEqual(os.waitstatus_to_exitcode(os.waitpid(pid,0)[1]),0)
    def _initialize_state(self):
        state=Path(self.config['state_dir'])
        initialize(state)
        c=_connect(state)
        try:
            c.execute('BEGIN IMMEDIATE')
            c.execute("UPDATE state SET phase='PREPARED',pending_sequence=1,pending_nonce='pending-nonce' WHERE id=1")
            c.execute('COMMIT')
        finally:c.close()
    def test_four_uid_schema_rejects_collision_root_or_wrong_owner(self):
        def check():
            anchor,ledger=validate_production_config(self.config)
            self.assertEqual(anchor.read(),(0,''))
            self.assertTrue(ledger.check_ready())
            invalid=json.loads(json.dumps(self.config))
            invalid['uids']['witness']=SERVICE
            with self.assertRaises(DeploymentDenied):validate_production_config(invalid)
            invalid['uids']['witness']=0
            with self.assertRaises(DeploymentDenied):validate_production_config(invalid)
        self._fork_and_wait(check)
        with self.assertRaises(DeploymentDenied):validate_production_config(self.config)
    def test_providers_required_at_startup_and_absence_blocks(self):
        stop_provider(self.anchor_pid);self.children.remove(self.anchor_pid)
        self._fork_and_wait_blocked()
    def _fork_and_wait_blocked(self):
        pid=os.fork()
        if pid==0:
            drop(SERVICE)
            try:validate_production_config(self.config)
            except (RemoteProviderUnavailable, OSError):os._exit(0)
            os._exit(9)
        self.assertEqual(os.waitstatus_to_exitcode(os.waitpid(pid,0)[1]),0)
        self.assertFalse((Path(self.config['ipc_dir'])/'recovery-v011.sock').exists())
    def test_real_four_uid_recovery_and_isolation(self):
        ready_r, ready_w=os.pipe()
        pid=os.fork()
        if pid==0:
            os.close(ready_r)
            try:
                drop(SERVICE)
                # readiness is announced after production contract succeeds;
                # broker publication may follow shortly.
                validate_production_config(self.config)
                os.write(ready_w,b'R');os.close(ready_w)
                serve(self.config,once=True)
                os._exit(0)
            except BaseException:
                import traceback;traceback.print_exc()
                os._exit(1)
        self.children.append(pid)
        os.close(ready_w)
        self.assertEqual(os.read(ready_r,1),b'R');os.close(ready_r)
        path=Path(self.config['ipc_dir'])/'recovery-v011.sock'
        for _ in range(100):
            if path.exists():break
            time.sleep(0.02)
        self.assertTrue(path.exists())
        read_r,read_w=os.pipe()
        client_pid=os.fork()
        if client_pid==0:
            os.close(read_r)
            try:
                drop(CLIENT)
                denied=not os.access(self.config['state_dir'],os.R_OK|os.X_OK)
                with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
                    sock.settimeout(3)
                    sock.connect(str(path));sock.sendall(b'RECONCILE\n')
                    answer=json.loads(sock.recv(4096))
                os.write(read_w,json.dumps({'denied':denied,'response':answer}).encode())
            except BaseException as exc:
                os.write(read_w,json.dumps({'error':repr(exc)}).encode())
            os.close(read_w);os._exit(0)
        os.close(read_w)
        answer=json.loads(os.read(read_r,4096));os.close(read_r)
        self.assertEqual(os.waitstatus_to_exitcode(os.waitpid(client_pid,0)[1]),0)
        self.assertNotIn('error',answer)
        self.assertTrue(answer['denied'])
        self.assertEqual(answer['response']['status'],'RECOVERED')
        self.assertEqual(os.waitstatus_to_exitcode(os.waitpid(pid,0)[1]),0)
        self.children.remove(pid)
        # Authorized service UID sees committed reconciliation; client UID cannot.
        self._fork_and_wait(lambda: self.assertEqual(self._state_phase(), 'IDLE'))
    def _state_phase(self):
        conn=_connect(Path(self.config['state_dir']))
        try:return _state(conn)[2]
        finally:conn.close()
    def test_config_tamper_and_missing_credential_denied(self):
        def check():
            invalid=json.loads(json.dumps(self.config))
            invalid['ipc_dir']=str(self.root)
            with self.assertRaises(DeploymentDenied):validate_production_config(invalid)
            invalid=json.loads(json.dumps(self.config))
            invalid['permit_file']=str(self.root/'does-not-exist')
            with self.assertRaises(OSError):validate_production_config(invalid)
        self._fork_and_wait(check)
    def test_service_sigkill_stale_socket_blocks_restart(self):
        ready_r,ready_w=os.pipe()
        pid=os.fork()
        if pid==0:
            os.close(ready_r)
            try:
                drop(SERVICE)
                from railsystem.privileged_recovery import PrivilegedRecoveryBroker
                anchor,ledger=validate_production_config(self.config)
                broker=PrivilegedRecoveryBroker(self.config['state_dir'],self.config['ipc_dir'],
                    transport_gid=GID,allowed_uids=frozenset({CLIENT}),provider=anchor,permit_store=ledger)
                broker.start();os.write(ready_w,b'R');signal.pause()
            except BaseException:
                os._exit(11)
            os._exit(0)
        os.close(ready_w)
        self.assertEqual(os.read(ready_r,1),b'R');os.close(ready_r)
        os.kill(pid,signal.SIGKILL)
        self.assertEqual(os.waitstatus_to_exitcode(os.waitpid(pid,0)[1]),-signal.SIGKILL)
        path=Path(self.config['ipc_dir'])/'recovery-v011.sock'
        self.assertTrue(stat.S_ISSOCK(path.lstat().st_mode))
        def check():
            from railsystem.privileged_recovery import PrivilegedRecoveryBroker,PrivilegedBrokerDenied
            a,l=validate_production_config(self.config)
            b=PrivilegedRecoveryBroker(self.config['state_dir'],self.config['ipc_dir'],
                transport_gid=GID,allowed_uids=frozenset({CLIENT}),provider=a,permit_store=l)
            with self.assertRaises(PrivilegedBrokerDenied):b.start()
        self._fork_and_wait(check)

    def test_sigkill_after_remote_cas_then_recover(self):
        """External UID witness advances; service dies before local commit.

        The production-relevant fact tested is PREPARED fencing, not
        durability of the deliberately volatile provider implementation.
        """
        from unittest.mock import patch
        from railsystem.unified_admission import admit, recover
        from railsystem.provider_ipc import UnixAnchorClient, UnixPermitLedgerClient
        from railsystem.provenance import candidate_baseline
        from railsystem.trust import canonical
        from railsystem.anchored_admission import _read_anchor
        import base64
        from pathlib import Path
        project=Path(__file__).resolve().parents[1]
        self._fork_and_wait(lambda:self._reset_idle())
        baseline=candidate_baseline(project,'rail012-sigkill-external')
        signer=Ed25519PrivateKey.generate()
        pub=base64.b64encode(signer.public_key().public_bytes(
            serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode()
        trust={'schema_version':1,'keys':{'test':{'revoked':False,'public_key':pub}}}
        payload={'domain':'snowpiercer.railsystem.release.v1',
                 'baseline_id':baseline['baseline_id'],'manifest_digest':baseline['manifest_digest'],
                 'key_id':'test','sequence':1,'nonce':'nonce-R012-123456789'}
        attestation={'schema_version':1,'payload':payload,
                     'signature':base64.b64encode(signer.sign(canonical(payload))).decode()}
        pid=os.fork()
        if pid==0:
            drop(SERVICE)
            with patch('railsystem.unified_admission.evaluate', return_value={'status':'PASS'}):
                admit(project,baseline=baseline,attestation=attestation,trust=trust,
                    state_dir=self.config['state_dir'],
                    provider=UnixAnchorClient(self.config['witness_socket'],
                        expected_uid=WITNESS,expected_gid=GID),
                    kill_at='after_external')
            os._exit(88)
        self.assertEqual(os.waitstatus_to_exitcode(os.waitpid(pid,0)[1]),-signal.SIGKILL)
        def check():
            from railsystem.production_fencing import inspect_fence
            from railsystem.anchored_admission import RecoveryRequired
            a=UnixAnchorClient(self.config['witness_socket'],expected_uid=WITNESS,expected_gid=GID)
            self.assertEqual(a.read(),(1,payload['nonce']))
            self.assertEqual(self._state_phase(),'PREPARED')
            with self.assertRaises(RecoveryRequired):inspect_fence(self.config['state_dir'],a)
            permit=json.loads(Path(self.config['permit_file']).read_text())
            key=Path(self.config['recovery_public_key_file']).read_text()
            ledger=UnixPermitLedgerClient(self.config['permit_socket'],expected_uid=RECOVERY,expected_gid=GID)
            self.assertEqual(recover(self.config['state_dir'],provider=a,
                permit=permit,recovery_public_key=key,permit_store=ledger)['status'],'RECOVERED')
            self.assertEqual(self._state_phase(),'IDLE')
        self._fork_and_wait(check)

    def _reset_idle(self):
        c=_connect(Path(self.config['state_dir']))
        try:
            c.execute("UPDATE state SET phase='IDLE',pending_sequence=NULL,pending_nonce=NULL WHERE id=1")
        finally:c.close()

    def test_sigkill_after_remote_permit_consumption_burns_permit(self):
        from railsystem.unified_admission import recover
        from railsystem.anchored_admission import RecoveryRequired
        from railsystem.provider_ipc import UnixAnchorClient,UnixPermitLedgerClient
        pid=os.fork()
        if pid==0:
            drop(SERVICE)
            a=UnixAnchorClient(self.config['witness_socket'],expected_uid=WITNESS,expected_gid=GID)
            l=UnixPermitLedgerClient(self.config['permit_socket'],expected_uid=RECOVERY,expected_gid=GID)
            recover(self.config['state_dir'],provider=a,
                permit=json.loads(Path(self.config['permit_file']).read_text()),
                recovery_public_key=Path(self.config['recovery_public_key_file']).read_text(),
                permit_store=l,kill_at='after_permit_consume')
            os._exit(88)
        self.assertEqual(os.waitstatus_to_exitcode(os.waitpid(pid,0)[1]),-signal.SIGKILL)
        def check():
            a=UnixAnchorClient(self.config['witness_socket'],expected_uid=WITNESS,expected_gid=GID)
            l=UnixPermitLedgerClient(self.config['permit_socket'],expected_uid=RECOVERY,expected_gid=GID)
            with self.assertRaises(RecoveryRequired):
                recover(self.config['state_dir'],provider=a,
                    permit=json.loads(Path(self.config['permit_file']).read_text()),
                    recovery_public_key=Path(self.config['recovery_public_key_file']).read_text(),
                    permit_store=l)
            self.assertEqual(self._state_phase(),'PREPARED')
        self._fork_and_wait(check)


    def test_sigterm_service_cleans_owned_socket(self):
        ready_r, ready_w=os.pipe()
        pid=os.fork()
        if pid==0:
            os.close(ready_r)
            try:
                drop(SERVICE)
                validate_production_config(self.config)
                os.write(ready_w,b'R');os.close(ready_w)
                serve(self.config)
                os._exit(0)
            except BaseException:
                os._exit(6)
        self.children.append(pid)
        os.close(ready_w);self.assertEqual(os.read(ready_r,1),b'R');os.close(ready_r)
        path=Path(self.config['ipc_dir'])/'recovery-v011.sock'
        for _ in range(100):
            if path.exists():break
            time.sleep(.02)
        self.assertTrue(path.exists())
        os.kill(pid,signal.SIGTERM)
        self.assertEqual(os.waitstatus_to_exitcode(os.waitpid(pid,0)[1]),0)
        self.children.remove(pid)
        self.assertFalse(path.exists())

    def test_unauthorized_real_uid_denied(self):
        rd, wr=os.pipe()
        pid=os.fork()
        if pid==0:
            os.close(rd)
            try:
                drop(SERVICE)
                validate_production_config(self.config)
                os.write(wr,b'R');os.close(wr)
                serve(self.config,once=True)
                os._exit(0)
            except BaseException:
                os._exit(7)
        self.children.append(pid)
        os.close(wr);self.assertEqual(os.read(rd,1),b'R');os.close(rd)
        path=Path(self.config['ipc_dir'])/'recovery-v011.sock'
        for _ in range(100):
            if path.exists():break
            time.sleep(.02)
        self.assertTrue(path.exists())
        result_r,result_w=os.pipe()
        child=os.fork()
        if child==0:
            os.close(result_r)
            drop(WITNESS)  # has transport GID, but NOT allowed UID
            try:
                with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as conn:
                    conn.settimeout(3);conn.connect(str(path));conn.sendall(b'RECONCILE\n')
                    answer=json.loads(conn.recv(4096))
                os.write(result_w,answer['status'].encode())
            except BaseException:os.write(result_w,b'ERROR')
            os.close(result_w);os._exit(0)
        os.close(result_w)
        self.assertEqual(os.read(result_r,256),b'BLOCKED');os.close(result_r)
        self.assertEqual(os.waitstatus_to_exitcode(os.waitpid(child,0)[1]),0)
        self.assertEqual(os.waitstatus_to_exitcode(os.waitpid(pid,0)[1]),0)
        self.children.remove(pid)
        self._fork_and_wait(lambda:self.assertEqual(self._state_phase(),'PREPARED'))

    def test_uid_legacy_direct_access_denied(self):
        pid=os.fork()
        if pid==0:
            drop(CLIENT)
            try:
                with open(Path(self.config['state_dir'])/'admission.sqlite3','rb'): pass
            except PermissionError:os._exit(0)
            os._exit(5)
        self.assertEqual(os.waitstatus_to_exitcode(os.waitpid(pid,0)[1]),0)
