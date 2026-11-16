"""ISLAND-GEO-018: fail-closed deployment verification, not a privilege boundary.

This checks OS-provisioned file isolation and pins socket inodes at inspection.
Root and other privileged principals remain outside the threat model.
"""
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from .anchored_admission import AdmissionDenied

@dataclass(frozen=True)
class EndpointIdentity:
    device: int
    inode: int
    owner: int
    group: int


def inspect_endpoint(path, *, owner, group, directory):
    """Reject symlink, foreign owner, world-writable endpoints, hardlinks."""
    path = Path(path)
    parent = path.parent.lstat()
    if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != 0 or not parent.st_mode & stat.S_ISVTX:
        raise AdmissionDenied('IPC parent must be root-owned sticky directory')
    if parent.st_mode & 0o022 != 0o022:
        raise AdmissionDenied('IPC parent missing expected sticky namespace permissions')
    st = path.lstat()
    if not stat.S_ISSOCK(st.st_mode) or st.st_uid != owner or st.st_gid != group:
        raise AdmissionDenied('endpoint type or identity mismatch')
    if st.st_mode & 0o007 or st.st_mode & 0o111:
        raise AdmissionDenied('endpoint exposes world or executable access')
    if st.st_nlink != 1:
        raise AdmissionDenied('endpoint hardlink rejected')
    return EndpointIdentity(st.st_dev, st.st_ino, st.st_uid, st.st_gid)


def assert_endpoint_unchanged(path, identity):
    try:
        st = Path(path).lstat()
    except OSError as exc:
        raise AdmissionDenied('endpoint missing or inaccessible') from exc
    if (st.st_dev, st.st_ino, st.st_uid, st.st_gid) != (identity.device, identity.inode, identity.owner, identity.group) or not stat.S_ISSOCK(st.st_mode):
        raise AdmissionDenied('endpoint replaced')
    return True


def verify_legacy_fence(path, forbidden_uid):
    """Perform actual write-open probe while already running as forbidden UID."""
    if os.geteuid() != forbidden_uid or forbidden_uid == 0:
        raise AdmissionDenied('untrusted probe principal')
    try:
        fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
    except PermissionError:
        return True
    except OSError as exc:
        raise AdmissionDenied('unproven legacy fence') from exc
    else:
        os.close(fd)
        raise AdmissionDenied('legacy write bypass exists')


def verify_storage_owner(path, uid):
    st = Path(path).lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_uid != uid or st.st_nlink != 1 or st.st_mode & 0o077:
        raise AdmissionDenied('private storage integrity mismatch')
    return True
