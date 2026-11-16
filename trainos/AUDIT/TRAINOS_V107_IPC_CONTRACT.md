# TrainOS v107 — Cross-UID broker wire/API contract

**Security status:** broker is **deny-only**. It does not execute, spawn,
release admission gates, or authorize legacy API operations.

- Transport: Linux AF_UNIX SOCK_SEQPACKET; frame upper limit 2048 bytes.
- Identity: `SO_PEERCRED` yields `(pid, uid, gid)` from the kernel. A user
  supplied `uid` field cannot grant access and must match kernel UID if present.
- Allowlist: exactly one separately configured, non-root client UID for this
  version; server UID must be distinct. Unauthorized UIDs receive `INVALID_PEER`.
- Request schema: `{"operation":"start","nonce":"<32-64 lowercase hexadecimal>"}`.
  No executable path, shell text, filesystem path or privileged command accepted.
- Response schema: `{"status":"DENIED","reason":"<code>"}`. Codes:
  `INVALID_PEER`, `BAD_JSON`, `OVERSIZE`, `BAD_REQUEST`, `UID_SPOOF`,
  `JOURNAL_UNAVAILABLE`, `REPLAY`, `CONTAINMENT_NOT_CERTIFIED`.
- Replay journal: root/service-owned protected SQLite file, uniqueness
  `PRIMARY KEY(uid,nonce)`. `BEGIN IMMEDIATE` + COMMIT persists the first
  processed attempt; a repeated nonce is denied even after broker restart.
- Confidentiality/integrity of transport: local kernel authentication, not
  network TLS. Parent directory owned by server and not client-writable; socket
  client-accessible for connection only. Filesystem and IPC permissions must
  be independently validated in a target deployment.
- Fail closed: no authorized operation when journal is unavailable, invalid
  payload, unauthorized peer, or authority not certified. No fallback to
  direct `KernelTestRunner` or `os.kill(pid)`.
- v107 does **not** issue a positive permit. Future authorization must bind
  nonce to exact state, launch type, monotonic generation, designated UID,
  deadline, validated watchdog identity and committed cgroup membership.

Library compatibility: all pre-existing Python library callable names remain
present; they are *not* a security boundary by themselves.
