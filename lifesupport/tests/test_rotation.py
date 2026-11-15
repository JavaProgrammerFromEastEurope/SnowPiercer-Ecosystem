import json, tempfile, unittest
from pathlib import Path
from lifesupport.core.registry import Registry
from lifesupport.core.rotation import RotatingLifecycle, RotationError, inspect_interrupted_rotation
from lifesupport.core.trust_anchor import TrustedLifecycle, AnchorError
ROOT=Path(__file__).resolve().parents[1]
class RotationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.db=Path(self.temp.name)/'db.sqlite';self.anchor=Path(self.temp.name)/'anchor.json'
        self.reg=Registry.from_dict(json.loads((ROOT/'data/registry.json').read_text()))
        self.old=b'o'*32;self.new=b'n'*32
        self.x=RotatingLifecycle(self.reg,self.db,anchor_path=self.anchor,secret=self.old,clock_ns=lambda:1000)
        self.addCleanup(self.x.close)
        self.token=self.x.acquire('operator',ttl_ns=100)
        self.x.protect(self.token);self.x.harden(self.token);self.x.establish_anchor(self.token)
    def test_prepare(self):
        self.x.prepare_rotation(self.token,self.new)
        self.assertEqual(inspect_interrupted_rotation(self.anchor,self.old,self.new),'OLD_ANCHOR')
    def test_pending_blocks_write(self):
        self.x.prepare_rotation(self.token,self.new)
        with self.assertRaises(RotationError):self.x.transition(next(iter(self.reg.components)),'INITIALIZING',event_id='e',actor='a',reason='r',token=self.token)
    def test_finalize(self):
        self.x.prepare_rotation(self.token,self.new);self.assertTrue(self.x.finalize_rotation(self.token,self.new))
        self.assertFalse(Path(str(self.anchor)+'.rotation').exists());self.x.verify_anchor()
    def test_new_key_reopens(self):
        self.x.prepare_rotation(self.token,self.new);self.x.finalize_rotation(self.token,self.new);self.x.close()
        y=TrustedLifecycle(self.reg,self.db,anchor_path=self.anchor,secret=self.new,clock_ns=lambda:1000);y.close()
    def test_old_key_rejected(self):
        self.x.prepare_rotation(self.token,self.new);self.x.finalize_rotation(self.token,self.new);self.x.close()
        with self.assertRaises(AnchorError):TrustedLifecycle(self.reg,self.db,anchor_path=self.anchor,secret=self.old,clock_ns=lambda:1000)
    def test_short_key(self):
        with self.assertRaises(RotationError):self.x.prepare_rotation(self.token,b'a')
    def test_same_key(self):
        with self.assertRaises(RotationError):self.x.prepare_rotation(self.token,self.old)
    def test_wrong_new_key(self):
        self.x.prepare_rotation(self.token,self.new)
        with self.assertRaises(RotationError):self.x.finalize_rotation(self.token,b'z'*32)
    def test_tamper_pending(self):
        self.x.prepare_rotation(self.token,self.new)
        p=Path(str(self.anchor)+'.rotation');d=json.loads(p.read_text());d['old_mac']='0'*64;p.write_text(json.dumps(d))
        with self.assertRaises(RotationError):inspect_interrupted_rotation(self.anchor,self.old,self.new)
    def test_tamper_anchor(self):
        self.x.prepare_rotation(self.token,self.new);self.anchor.write_text('{}')
        with self.assertRaises(RotationError):inspect_interrupted_rotation(self.anchor,self.old,self.new)
    def test_double_prepare(self):
        self.x.prepare_rotation(self.token,self.new)
        with self.assertRaises(RotationError):self.x.prepare_rotation(self.token,self.new)
    def test_pending_blocks_reopen(self):
        self.x.prepare_rotation(self.token,self.new)
        with self.assertRaises(RotationError):RotatingLifecycle(self.reg,self.db,anchor_path=self.anchor,secret=self.old,clock_ns=lambda:1000)
    def test_invalid_token(self):
        with self.assertRaises(Exception):self.x.prepare_rotation(None,self.new)
    def test_missing_pending(self):
        with self.assertRaises(RotationError):inspect_interrupted_rotation(self.anchor,self.old,self.new)
