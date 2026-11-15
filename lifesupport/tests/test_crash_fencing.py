"""LIFE-CORE-011: fail-closed rotation marker and legacy admission regression."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from lifesupport.core.registry import Registry
from lifesupport.core.rotation import RotatingLifecycle, RotationError
from lifesupport.core.admission import AdmittedLifecycle

ROOT = Path(__file__).resolve().parents[1]

class CrashFencingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name)/'journal.sqlite'
        self.anchor = Path(self.tmp.name)/'anchor.json'
        self.registry = Registry.from_dict(json.loads((ROOT/'data/registry.json').read_text()))
        self.old, self.new = b'o'*32, b'n'*32
        self.writer = RotatingLifecycle(self.registry,self.db,anchor_path=self.anchor,secret=self.old,clock_ns=lambda:1000)
        self.addCleanup(self.writer.close)
        self.token = self.writer.acquire('operator',ttl_ns=100)
        self.writer.protect(self.token)
        self.writer.harden(self.token)
        self.writer.establish_anchor(self.token)
        self.legacy = AdmittedLifecycle(self.registry,self.db,clock_ns=lambda:1000)
        self.addCleanup(self.legacy.close)
        self.cid = next(iter(self.registry.components))

    def legacy_write(self, event='legacy'):
        return self.legacy.transition(self.cid,'INITIALIZING',event_id=event,reason='test',actor='test',token=self.token)

    def test_existing_legacy_writer_blocked_during_rotation(self):
        self.writer.prepare_rotation(self.token,self.new)
        with self.assertRaises(Exception): self.legacy_write()

    def test_legacy_writer_resumes_after_finalize(self):
        self.writer.prepare_rotation(self.token,self.new)
        self.writer.finalize_rotation(self.token,self.new)
        self.assertEqual(self.legacy_write().event_id,'legacy')

    def test_pending_marker_survives_close_and_reopen(self):
        self.writer.prepare_rotation(self.token,self.new)
        self.writer.close()
        with self.assertRaises(RotationError):
            RotatingLifecycle(self.registry,self.db,anchor_path=self.anchor,secret=self.old,clock_ns=lambda:1000)
        with self.assertRaises(Exception): self.legacy_write()

    def test_marker_without_intent_fails_closed(self):
        Path(str(self.db)+'.rotation-fence').write_text('orphan')
        with self.assertRaises(Exception): self.legacy_write()
        with self.assertRaises(RotationError):
            RotatingLifecycle(self.registry,self.db,anchor_path=self.anchor,secret=self.old,clock_ns=lambda:1000)

    def test_invalid_new_key_keeps_fence(self):
        self.writer.prepare_rotation(self.token,self.new)
        with self.assertRaises(RotationError): self.writer.finalize_rotation(self.token,b'z'*32)
        with self.assertRaises(Exception): self.legacy_write()

    def test_subprocess_sigkill_after_prepare(self):
        self.legacy.close(); self.writer.release(self.token); self.writer.close()
        script = '''import json,os,signal\nfrom pathlib import Path\nfrom lifesupport.core.registry import Registry\nfrom lifesupport.core.rotation import RotatingLifecycle\nroot=Path(os.environ["LIFE_ROOT"])\nreg=Registry.from_dict(json.loads((root/"data/registry.json").read_text()))\nx=RotatingLifecycle(reg,os.environ["LIFE_DB"],anchor_path=os.environ["LIFE_ANCHOR"],secret=b"o"*32,clock_ns=lambda:1000)\nt=x.acquire("crash",ttl_ns=100)\nx.prepare_rotation(t,b"n"*32)\nos.kill(os.getpid(),signal.SIGKILL)'''
        env=os.environ.copy(); env.update(LIFE_ROOT=str(ROOT),LIFE_DB=str(self.db),LIFE_ANCHOR=str(self.anchor),PYTHONPATH=str(ROOT/'src'))
        proc=subprocess.run([sys.executable,'-c',script],env=env,capture_output=True,text=True,timeout=15)
        self.assertEqual(proc.returncode,-9,proc.stderr)
        self.assertTrue(Path(str(self.db)+'.rotation-fence').exists())
        legacy=AdmittedLifecycle(self.registry,self.db,clock_ns=lambda:2000)
        try:
            token=legacy.acquire('post-crash',ttl_ns=100)
            with self.assertRaises(Exception):
                legacy.transition(self.cid,'INITIALIZING',event_id='afterkill',reason='test',actor='test',token=token)
        finally: legacy.close()

    def test_unprotected_database_not_affected_by_other_marker(self):
        other=Path(self.tmp.name)/'other.sqlite'
        y=AdmittedLifecycle(self.registry,other,clock_ns=lambda:1000)
        try:
            token=y.acquire('other',ttl_ns=100)
            self.assertEqual(y.transition(self.cid,'INITIALIZING',event_id='other',reason='test',actor='test',token=token).event_id,'other')
        finally:y.close()
