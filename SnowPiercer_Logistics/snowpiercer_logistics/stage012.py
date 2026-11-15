"""Stage 012: privileged deployment plan and descriptor-based entrypoint guards.

No privilege escalation is attempted. Installation is an explicit root-only action;
production activation requires separately running the OS-level acceptance harness.
"""
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from .secure import AdmissionError
from .stage011 import DeploymentLayout, verify_deployment

@dataclass(frozen=True)
class DeploymentPlan:
    layout: DeploymentLayout
    def validate(self):
        p = self.layout.policy
        p.validate()
        roots = [Path(self.layout.service_root), Path(self.layout.witness_root), Path(self.layout.authority_root)]
        if len(set(map(str, roots))) != 3 or any(not x.is_absolute() or '..' in x.parts for x in roots):
            raise AdmissionError('invalid deployment roots')
        if any(str(x) in ('/', '/tmp', '/var/tmp') for x in roots):
            raise AdmissionError('unsafe deployment root')
        for sock, root in zip((self.layout.service_socket, self.layout.witness_socket, self.layout.authority_socket), roots):
            if Path(sock).parent != root:
                raise AdmissionError('socket must reside inside owned root')
        return True
    def installation_steps(self):
        self.validate()
        p = self.layout.policy
        return tuple((str(root), uid, 0o700) for root, uid in zip(
            (self.layout.service_root, self.layout.witness_root, self.layout.authority_root),
            (p.service_uid, p.witness_uid, p.authority_uid)))


def install_private_roots(plan):
    """Root-only, no-follow creation. Never recursively chown existing content."""
    if os.geteuid() != 0:
        raise AdmissionError('privileged installation requires root')
    for name, uid, mode in plan.installation_steps():
        path = Path(name)
        if path.is_symlink():
            raise AdmissionError('symlink root')
        if not path.exists():
            path.mkdir(mode=0o700)
        fd = os.open(str(path), os.O_RDONLY | os.O_DIRECTORY | getattr(os, 'O_NOFOLLOW', 0))
        try:
            info = os.fstat(fd)
            if not stat.S_ISDIR(info.st_mode):
                raise AdmissionError('not directory')
            if info.st_uid not in (0, uid):
                raise AdmissionError('unexpected existing owner')
            os.fchown(fd, uid, -1)
            os.fchmod(fd, mode)
        finally:
            os.close(fd)


def require_production_entrypoint(layout, *, acceptance_file):
    """Fail closed unless externally produced acceptance artifact exists.

    Artifact is NOT proof of cross-UID security: verifier must inspect signed evidence
    and independently execute cross-UID tests before enabling physical actuators.
    """
    verify_deployment(layout)
    path = Path(acceptance_file)
    if path.is_symlink():
        raise AdmissionError('acceptance symlink')
    try:
        fd = os.open(str(path), os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    except OSError as exc:
        raise AdmissionError('acceptance evidence missing') from exc
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_mode & 0o022 or st.st_uid != 0:
            raise AdmissionError('untrusted acceptance artifact')
        payload = os.read(fd, 1024)
        if payload != b'LOG-CORE-012:EXTERNAL-ACCEPTANCE-REQUIRED\n':
            raise AdmissionError('invalid acceptance artifact')
    finally:
        os.close(fd)
    # Deliberately not enabled: marker cannot independently attest OS isolation.
    raise AdmissionError('independent cross-UID end-to-end attestation unavailable')
