# LIFE-CORE-011 — Crash fencing design

The protected SQLite INSERT trigger invokes connection-local `ls_admitted()`. For all `AdmittedLifecycle` connections the function now also checks for the absence of `<db>.rotation-fence` at INSERT time. The rotation writer holds SQLite BEGIN IMMEDIATE while creating and fsyncing the marker and rotation intent. This closes the normal race between a previously opened admitted writer and preparation of rotation: a concurrent transaction is serialized by SQLite's writer lock.

Finalization authenticates the dual-MAC intent and verifies the old anchor, writes the new anchor, commits, then removes intent and fence with directory fsync. A crash after the new anchor replacement can leave a pending intent and marker; reopening the rotating writer fails closed. `inspect_interrupted_rotation` classifies the old/new anchor but never automatically removes the fence.

**Limits:** File marker is not authenticated and can be removed by a privileged filesystem actor. A privileged SQLite writer can remove the triggers. Other API implementations can still bypass the marker where they do not use `ls_admitted`. No distributed coordination, power-loss proof, hardware root of trust, or automatic recovery is claimed. On failed preparation, a created marker is retained deliberately, requiring manual investigation. Key custody remains external.
