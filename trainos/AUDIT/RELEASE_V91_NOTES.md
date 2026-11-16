# TrainOS v91 — BLOCKED / NO-GO

Base: v90. Bounded runner refactored to make process-group signaling and post-exit cleanup explicit, preserve legacy logs and atomic JSON evidence. Four existing runner contracts passed. Initial combined run exposed SQLite PytestUnraisableExceptionWarning; its parent was interrupted by an execution deadline and the orphaned pytest process was terminated manually. Three bounded strict combined runs timed out, as did the full suite. No suppression of warnings. No full SQLite leak fix or production readiness is claimed. No numeric Stage introduced.
