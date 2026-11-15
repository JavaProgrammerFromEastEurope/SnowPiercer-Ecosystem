"""AI-CORE-018 deterministic process-local crash points for isolated test harnesses.

Never install this hook in a production process. No environment-variable trigger.
"""
import os
import signal

POINTS = frozenset({'after_prepare', 'before_sqlite_commit', 'after_sqlite_commit',
                    'before_checkpoint', 'after_checkpoint', 'before_clean'})


class CrashInjector:
    def __init__(self, point, *, enabled=False):
        if point not in POINTS:
            raise ValueError('unknown crash point')
        if enabled is not True:
            raise PermissionError('test-only injector must be explicitly enabled')
        self.point = point

    def hit(self, point):
        if point == self.point:
            os.kill(os.getpid(), signal.SIGKILL)


def inject_admission(journaled, envelope, injector):
    """Run the real admission path, injecting SIGKILL at exact write boundaries.

    The SQLite commit and checkpoint hooks are installed on the owned gateway
    instance and restored in finally on nonfatal exits. Not concurrency-safe;
    only use in a dedicated isolated child with no other admissions.
    """
    from .production014 import JournaledAdmissionGateway
    if not isinstance(journaled, JournaledAdmissionGateway) or not isinstance(injector, CrashInjector):
        raise TypeError('journaled gateway and injector required')
    gateway = journaled.gateway
    original_checkpoint = gateway.checkpoint.write
    original_base_admit = gateway.__class__.__mro__[1].admit
    # Use a narrow per-instance subclass to instrument the actual SQLite commit.
    original_class = gateway.__class__
    class Instrumented(original_class):
        def admit(self, env, *, fault=None):
            with self.manager.lock, self.store._lock:
                self.verify()
                if injector.point == 'before_sqlite_commit':
                    self.store._db.set_trace_callback(lambda sql: injector.hit('before_sqlite_commit') if sql.strip().upper() == 'COMMIT' else None)
                try:
                    result = original_base_admit(self, env)
                finally:
                    if injector.point == 'before_sqlite_commit':
                        self.store._db.set_trace_callback(None)
                injector.hit('after_sqlite_commit')
                injector.hit('before_checkpoint')
                seq, head = self._audit_check()
                self.checkpoint.write(seq, head)
                injector.hit('after_checkpoint')
                return result
    gateway.__class__ = Instrumented
    try:
        # The PREPARED journal is durably persisted by the regular adapter.
        if injector.point == 'after_prepare':
            original_write = journaled.journal.write
            def wrapped_write(phase, seq, head):
                original_write(phase, seq, head)
                if phase == 'PREPARED': injector.hit('after_prepare')
            journaled.journal.write = wrapped_write
        if injector.point == 'before_clean':
            original_write = journaled.journal.write
            def wrapped_write(phase, seq, head):
                if phase == 'CLEAN': injector.hit('before_clean')
                original_write(phase, seq, head)
            journaled.journal.write = wrapped_write
        return journaled.admit(envelope)
    finally:
        gateway.__class__ = original_class
        journaled.journal.write = original_write if injector.point in ('after_prepare', 'before_clean') else journaled.journal.write
