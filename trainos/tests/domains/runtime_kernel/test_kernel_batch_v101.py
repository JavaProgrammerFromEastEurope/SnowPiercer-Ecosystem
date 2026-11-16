"""Opt-in kernel runner batching preserves the default per-file contract."""
from tests.kernel_runner import runner as kernel_runner
from tests.kernel_runner.config import StageConfig


def test_opt_in_batch_runs_all_files_once(monkeypatch):
    monkeypatch.setattr(kernel_runner, 'STAGES', [StageConfig('diagnostics', ['a.py', 'b.py'])])
    monkeypatch.setenv('TRAINOS_KERNEL_BATCH', '1')
    runner = kernel_runner.KernelTestRunner()
    calls = []
    monkeypatch.setattr(runner, '_run_batch', lambda files: calls.append(files) or 0)
    assert runner.run() == 0
    assert calls == [['a.py', 'b.py']]


def test_default_runner_retains_per_file_execution(monkeypatch):
    monkeypatch.setattr(kernel_runner, 'STAGES', [StageConfig('diagnostics', ['a.py', 'b.py'])])
    monkeypatch.delenv('TRAINOS_KERNEL_BATCH', raising=False)
    runner = kernel_runner.KernelTestRunner()
    calls = []
    monkeypatch.setattr(runner, '_run_test', lambda file: calls.append(file) or 0)
    assert runner.run() == 0
    assert calls == ['a.py', 'b.py']
