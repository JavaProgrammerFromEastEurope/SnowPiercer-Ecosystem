import os
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock
from ai_cognition import AdmissionSupervisor, production_admission, verified_socket, IsolationError

class OrchestrationTests(unittest.TestCase):
    def test_legacy_library_compatible(self):
        obj=Mock(); self.assertIs(production_admission(obj),obj)
        with self.assertRaises(IsolationError): production_admission(obj,production=True)

    def test_root_forbidden(self):
        with self.assertRaises(IsolationError): AdmissionSupervisor(['echo'], '/tmp/unused',service_uid=0)

    def test_regular_file_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'sock'; p.write_text('tamper')
            with self.assertRaises(IsolationError): verified_socket(p,owner_uid=os.geteuid())

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'sock'; p.symlink_to('/tmp/anything')
            with self.assertRaises(IsolationError): verified_socket(p,owner_uid=os.geteuid())

    @unittest.skipUnless(sys.platform.startswith('linux') and os.geteuid()==0,'root Linux required for cross-UID')
    def test_real_cross_uid_sigkill_restart_and_fence(self):
        import pwd
        uid=pwd.getpwnam('nobody').pw_uid
        with tempfile.TemporaryDirectory() as d:
            os.chown(d,uid,-1); os.chmod(d,0o710)
            path=Path(d)/'service.sock'; script=Path(d)/'server.py'
            script.write_text('''import os,socket,json,sys,time\np=sys.argv[1]\ntry: os.unlink(p)\nexcept FileNotFoundError: pass\ns=socket.socket(socket.AF_UNIX); s.bind(p); os.chmod(p,0o666); s.listen(4); s.settimeout(.1)\nwhile True:\n try: c,_=s.accept()\n except socket.timeout: continue\n with c:\n  b=c.recv(4096)\n  if b: c.sendall(b'{"ok":true,"seq":0,"head":"'+b'0'*64+b'"}\\n')\n''')
            os.chmod(script,0o644)
            sup=AdmissionSupervisor([sys.executable,str(script),str(path)],path,service_uid=uid,max_restarts=2,startup_timeout=3)
            stop=threading.Event(); errors=[]
            t=threading.Thread(target=lambda: _run(sup,stop,errors)); t.start()
            try:
                deadline=time.monotonic()+5
                while sup.process is None or not sup.ready:
                    if time.monotonic()>deadline: self.fail('startup timeout '+str(errors))
                    time.sleep(.02)
                first=sup.process.pid
                os.kill(first,signal.SIGKILL)
                deadline=time.monotonic()+5
                while sup.process is None or sup.process.pid==first or sup.process.poll() is not None:
                    if time.monotonic()>deadline: self.fail('restart timeout '+str(errors))
                    time.sleep(.02)
                self.assertEqual(verified_socket(path,owner_uid=uid)[0]>=0,True)
                self.assertEqual(sup.restarts,1)
            finally:
                stop.set(); t.join(5)
            self.assertFalse(errors,errors)


def _run(sup,stop,errors):
    try: sup.run(stop_event=stop)
    except Exception as exc: errors.append(str(exc))


def _ready(path):
    try:
        from ai_cognition import ipc_request
        return ipc_request(path, {'op':'verify'},timeout=.2).get('ok') is True
    except (OSError, RuntimeError): return False

class AdditionalFencingTests(unittest.TestCase):
    def test_invalid_command(self):
        with self.assertRaises(ValueError): AdmissionSupervisor([], '/tmp/s',service_uid=65534)

    def test_invalid_restart_budget(self):
        with self.assertRaises(ValueError): AdmissionSupervisor(['x'],'/tmp/s',service_uid=65534,max_restarts=-1)

    @unittest.skipUnless(sys.platform.startswith('linux') and os.geteuid()==0,'root Linux required')
    def test_untrusted_directory_rejected_before_launch(self):
        with tempfile.TemporaryDirectory() as d:
            sup=AdmissionSupervisor(['/bin/false'],Path(d)/'sock',service_uid=65534)
            with self.assertRaises(IsolationError): sup._start()
            self.assertIsNone(sup.process)
