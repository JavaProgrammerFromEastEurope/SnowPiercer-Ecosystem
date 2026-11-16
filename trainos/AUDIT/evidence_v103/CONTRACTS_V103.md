# TrainOS v103 — Kernel Runner contracts

**Input:** `KernelTestRunner()` reads the bounded settings `TRAINOS_KERNEL_FILE_TIMEOUT` (default 120 seconds), `TRAINOS_KERNEL_KILL_GRACE` (default 2 seconds), and `TRAINOS_KERNEL_WORKERS` (default 1). Invalid values fail at construction with `ValueError`. `TRAINOS_KERNEL_BATCH=1` retains batch-per-stage behavior.

**Compatibility:** `run(): int`, `_run_test(path): int`, `_run_batch(paths): int`, `_expand(path): list[str]`, `_execute(argv): int`, `failed: list[str]`. `STAGES` remains a 24-domain registry; legacy assignment file and prior tests remain unchanged. Python 3.13-specific constructs exist in the inherited v101 code; support for Python 3.9 is not established.

**Default per-file mode:** Each configured `test_*.py` uses an isolated `python -m pytest PATH -q` process in configured file order; the first nonzero return halts the Runner and sets `failed`. The default Runner does not invoke batch mode or worker pool.

**Optional worker mode:** With `TRAINOS_KERNEL_WORKERS=N` (`N` in 2..16), processes remain per-file and domains retain sequence; tests within one domain may overlap. If any per-file invocation fails, the entire domain completes and the Runner returns 1 without advancing to the next domain. Concurrent tests sharing mutable external resources may have different results from serial execution.

**Timeout/exit:** Timeout returns 124; successful leader with an observed residual process group returns 125; nonzero leader retains nonzero exit code. On POSIX, signal cleanup is directed at the subprocess's dedicated process group and includes descendants sharing the group. A child that independently detaches into another session is outside this boundary. `SIGTERM` handling of the runner applies only when `_execute` runs in the main Python thread.

**Supervisor:** The optional Linux subreaper handles adopted zombie descendants in this container but is not PID 1, a cgroup controller, a privilege boundary or an independent production authority. `SIGKILL` of the runner is uncatchable and may leave live child sessions; the negative test demonstrates this explicitly.

**Warning contracts:** The verification harness uses `PYTHONWARNINGS=error::ResourceWarning,error::DeprecationWarning` and additional pytest CLI warnings including `PytestUnraisableExceptionWarning`. Explicit `PYTEST_ADDOPTS=-c PROJECT/pytest.ini` supplies existing plugin configuration to pytest commands whose test targets live in temporary directories. No warning category is suppressed.
