import unittest
from ai_cognition import assess

BASE = {'event_id': 'event-001', 'source': 'trainos', 'severity': 'info', 'description': 'nominal'}

class CognitiveCoreTests(unittest.TestCase):
    def test_severity_matrix(self):
        for severity, expected in [('info', 'OBSERVE'), ('warning', 'INVESTIGATE'), ('critical', 'ESCALATE')]:
            with self.subTest(severity=severity):
                self.assertEqual(assess({**BASE, 'severity': severity}).decision.value, expected)

    def test_non_actionable(self):
        for severity in ('info', 'warning', 'critical'):
            self.assertFalse(assess({**BASE, 'severity': severity}).actionable)

    def test_deterministic_evidence(self):
        self.assertEqual(assess(BASE).evidence_sha256, assess(dict(reversed(list(BASE.items())))).evidence_sha256)

    def test_input_is_not_modified(self):
        original = BASE.copy()
        assess(BASE)
        self.assertEqual(BASE, original)

    def test_reject_invalid(self):
        bad = [None, {}, {**BASE, 'source': 'unknown'}, {**BASE, 'severity': 'fatal'},
               {**BASE, 'event_id': '../escape'}, {**BASE, 'description': ''},
               {**BASE, 'description': 'a'*2049}, {**BASE, 'description': 'bad\nline'},
               {**BASE, 'severity': 1}, {**BASE, 'command': 'shutdown'}]
        for item in bad:
            with self.subTest(item=item):
                with self.assertRaises(ValueError):
                    assess(item)

    def test_all_sources(self):
        for source in ('trainos', 'rail', 'energy', 'life_support', 'logistics', 'security', 'island', 'operations'):
            self.assertEqual(assess({**BASE, 'source': source}).decision.value, 'OBSERVE')

if __name__ == '__main__':
    unittest.main()
