"""RAIL-TRUST-015: environment/entrypoint negative tests, fail-closed only."""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock
from railsystem.os_boundary import DeploymentDenied
from railsystem.os_managed_fencing import assess_os_management, require_production_isolation


class MACConfinementTests(unittest.TestCase):
    def test_real_environment_is_not_independently_attested(self):
        facts = assess_os_management()
        self.assertEqual(facts['status'], 'BLOCKED')
        self.assertFalse(facts['same_uid_legacy_fenced'])
        self.assertFalse(facts['independent_monotonic_root_proven'])
        self.assertFalse(facts['independent_service_manager_verified'])
        self.assertGreaterEqual(len(facts['blockers']), 5)
        with self.assertRaises(DeploymentDenied): require_production_isolation()

    def test_fake_enforcing_label_and_systemd_comm_never_authorize(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            for name, data in [('pid1','systemd\n'), ('label','railsystem-write (enforce)\n'),
                               ('lsm','apparmor,selinux,landlock\n'),
                               ('status','NoNewPrivs:\t1\nSeccomp:\t2\nCapEff:\t0000000000000000\n')]:
                (p / name).write_text(data)
            facts = assess_os_management(pid1_comm=p/'pid1',lsm_label=p/'label',
                                          lsm_inventory=p/'lsm', proc_status=p/'status')
            self.assertTrue(facts['dedicated_systemd_pid1'])
            self.assertEqual(facts['no_new_privileges'], '1')
            self.assertEqual(facts['seccomp_mode'], '2')
            self.assertFalse(facts['mac_profile_proven'])
            self.assertEqual(facts['status'], 'BLOCKED')

    def test_missing_procfs_unsafe_not_permissive(self):
        f = assess_os_management(pid1_comm='/nonexistent/pid1',
                                 lsm_label='/nonexistent/label',
                                 lsm_inventory='/nonexistent/lsm',
                                 proc_status='/nonexistent/status')
        self.assertIsNone(f['pid1'])
        self.assertEqual(f['status'], 'BLOCKED')

    def test_mocked_positive_diagnostics_cannot_authorize(self):
        with mock.patch('railsystem.os_managed_fencing.assess_os_management',
                        return_value={'status':'PASS', 'reason':'fake'}):
            with self.assertRaises(DeploymentDenied): require_production_isolation()

    def test_environment_flags_do_not_override_kernel_gate(self):
        with mock.patch.dict(os.environ, {'RAIL_ALLOW_PRODUCTION':'true',
                                         'RAIL_MAC_ATTESTED':'true',
                                         'RAIL_INDEPENDENT_ROOT':'true'}):
            with self.assertRaises(DeploymentDenied): require_production_isolation()

    def test_write_entrypoint_does_not_call_service_when_unattested(self):
        from railsystem.write_authority import main
        argv = ['--config','/untrusted/config','--root','/untrusted/root',
                '--baseline','/untrusted/baseline','--attestation','/untrusted/attestation',
                '--trust','/untrusted/trust']
        with mock.patch('railsystem.write_authority.serve', side_effect=AssertionError('bypass')):
            with redirect_stderr(io.StringIO()): self.assertEqual(main(argv), 2)

    def test_recovery_entrypoint_does_not_run_without_isolation(self):
        from railsystem.service_runtime import main
        with mock.patch('railsystem.service_runtime.serve', side_effect=AssertionError('bypass')):
            with redirect_stderr(io.StringIO()): self.assertEqual(main(['--config','/untrusted']), 2)

    def test_release_cli_even_with_provider_mock_is_blocked(self):
        from railsystem.release_cli import main
        with tempfile.TemporaryDirectory() as d:
            output = Path(d)/'report.json'
            argv = ['release-cli','--state-dir',d,'--baseline',d+'/b',
                    '--attestation',d+'/a','--trust',d+'/t','--output',str(output)]
            with mock.patch.object(sys, 'argv', argv), \
                 mock.patch('railsystem.release_cli.read_protected_json', return_value={}), \
                 mock.patch('railsystem.release_cli.admit_unified', side_effect=AssertionError('bypass')):
                with redirect_stderr(io.StringIO()):
                    self.assertEqual(main(), 2)
            report = json.loads(output.read_text())
            self.assertEqual(report['status'], 'BLOCKED')
            self.assertEqual(report['stage'], 'RAIL-TRUST-015')

    def test_legacy_importable_but_production_never_enabled(self):
        # Explicitly record compatibility versus unresolved same-UID library bypass.
        from railsystem import unified_admission, release_gate
        self.assertTrue(callable(unified_admission.admit))
        self.assertTrue(callable(release_gate.evaluate))
        self.assertFalse(assess_os_management()['same_uid_legacy_fenced'])

    def test_concurrent_prod_fencing_is_stably_blocked(self):
        import concurrent.futures
        def check(_):
            try: require_production_isolation()
            except DeploymentDenied: return 'BLOCKED'
            return 'UNSAFE'
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(list(pool.map(check,range(20))), ['BLOCKED']*20)
