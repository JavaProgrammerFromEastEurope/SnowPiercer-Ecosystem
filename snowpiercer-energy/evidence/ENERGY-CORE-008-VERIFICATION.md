# ENERGY-CORE-008 evidence

Three full pytest runs, each 120/120 PASS (360/360 executions), with ResourceWarning and DeprecationWarning configured as errors, and third-party pytest autoload disabled. See three raw regression logs.

Confirmed: opt-in mandatory IPC controller path, Linux peer UID allowlist in same-UID tests, basic socket inode replacement detection, duplicate operation rejection, startup failure on missing anchor, competing socket binder rejection, and compatibility with existing test suite.

Not confirmed: actual distinct-UID test, exhaustive crash-point matrix, SIGKILL across new IPC phases, global legacy production bypass closure, adversarial same-UID file substitution, independent trust root, power-loss durability, hardware control safety. Security readiness BLOCKED; physical deployment NO-GO.
