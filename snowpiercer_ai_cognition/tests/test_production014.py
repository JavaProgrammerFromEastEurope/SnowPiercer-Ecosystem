import os
import tempfile
import unittest
from pathlib import Path
from ai_cognition.production014 import PhaseJournal
from ai_cognition.lifecycle import RecoveryRequired

class JournalTests(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            j=PhaseJournal(Path(d)/'phase',b'k'*32)
            j.write('PREPARED',0,'0'*64)
            self.assertEqual(j.read()['phase'],'PREPARED')
            j.write('CLEAN',1,'a'*64)
            self.assertEqual(j.read()['seq'],1)
    def test_tamper(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'phase'; j=PhaseJournal(p,b'k'*32)
            j.write('CLEAN',0,'0'*64)
            p.write_bytes(p.read_bytes().replace(b'CLEAN',b'XXXXX'))
            with self.assertRaises(RecoveryRequired): j.read()
    def test_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'phase'; target=Path(d)/'target'; target.write_text('x')
            p.symlink_to(target)
            with self.assertRaises(RecoveryRequired): PhaseJournal(p,b'k'*32).read()
    def test_missing(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RecoveryRequired): PhaseJournal(Path(d)/'missing',b'k'*32).read()
