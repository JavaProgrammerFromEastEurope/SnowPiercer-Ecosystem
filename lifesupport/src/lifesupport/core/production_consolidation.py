"""LIFE-CORE-020: opt-in production profile and fail-closed legacy CLI admission.

A deployment control, NOT a mandatory kernel security boundary. Same-UID/root
can bypass this Python check; DB DAC and independent key are required.
"""
import json
import os
import stat
from pathlib import Path
from .service import ServiceError

PROFILE = '.life-production-profile.json'
LEGACY = frozenset(('production_write', 'reconciled_write'))


def _directory(db):
    path = Path(db).parent
    st = path.lstat()
    if not stat.S_ISDIR(st.st_mode) or stat.S_IMODE(st.st_mode) & 0o077 or st.st_uid != os.geteuid():
        raise ServiceError('production database directory must be service-owned 0700')
    return path


def read_profile(db):
    path = _directory(db) / PROFILE
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o600 or st.st_size > 4096:
            raise ServiceError('unsafe production profile')
        raw = os.read(fd, 4097)
        if len(raw) > 4096: raise ServiceError('oversized production profile')
        obj = json.loads(raw)
        if set(obj) != {'version','mode','anchor','key_file'} or obj['version'] != 1 or obj['mode'] != 'mandatory-ledger':
            raise ServiceError('unsupported production profile')
        for name in ('anchor','key_file'):
            if not isinstance(obj[name], str) or not os.path.isabs(obj[name]) or not obj[name]:
                raise ServiceError('invalid production profile path')
        return obj
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise ServiceError('corrupt production profile') from exc
    finally:
        os.close(fd)


def enforce_legacy_cli(db):
    """Legacy CLI is disabled once production profile is installed."""
    if read_profile(db) is not None:
        raise ServiceError('legacy production IPC disabled: mandatory ledger required')


def install_profile(db, *, anchor, key_file):
    """Explicit offline provisioning; caller must stop all service processes."""
    directory = _directory(db)
    for p in (anchor, key_file):
        if not os.path.isabs(str(p)): raise ServiceError('absolute paths required')
    payload = json.dumps({'version':1,'mode':'mandatory-ledger','anchor':str(anchor),'key_file':str(key_file)},sort_keys=True).encode()
    path = directory / PROFILE
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(payload); f.flush(); os.fsync(f.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    dfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(dfd)
    finally: os.close(dfd)
    return path


def production_supervisor(registry, db, socket_path, *, allowed_uids):
    from .mandatory_ledger import MandatoryLedgerSupervisor
    profile = read_profile(db)
    if profile is None: raise ServiceError('production profile required')
    return MandatoryLedgerSupervisor(registry,db,socket_path,allowed_uids=allowed_uids,
        anchor_path=profile['anchor'],key_file=profile['key_file'])
