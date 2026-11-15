"""Stage 014: disposable four-UID kernel IPC acceptance harness.

This is a deliberately separate test protocol, NOT a production Logistics API.
It proves cross-UID process/socket reachability and kernel credential checks,
not witness CAS, recovery correctness, or production certification.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from .secure import AdmissionError
from .stage013 import _drop_to, run_as_uid
from .stage010 import IsolationPolicy

_SERVER = r'''
import json, os, socket, struct, sys
path, role, expected = sys.argv[1], sys.argv[2], int(sys.argv[3])
s=socket.socket(socket.AF_UNIX)
s.bind(path)
os.chmod(path, 0o666)
s.listen(4)
print('READY',flush=True)
for _ in range(2):
 c,_=s.accept()
 with c:
  uid=struct.unpack('3i',c.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))[1]
  ok=(uid==expected)
  c.sendall((json.dumps({'ok':ok,'role':role,'peer_uid':uid,'server_uid':os.geteuid()})+'\n').encode())
s.close()
'''

def four_uid_ipc_probe(policy, *, timeout=5):
    """Real kernel UIDs in four subprocess roles, with negative identity probes.

    Never modifies host accounts; uses disposable paths, drops supplementary groups.
    Linux/root only. No persistent daemon is launched.
    """
    policy.validate()
    if not sys.platform.startswith('linux') or os.geteuid()!=0 or not hasattr(socket,'SO_PEERCRED'):
        raise AdmissionError('Linux root and SO_PEERCRED required')
    with tempfile.TemporaryDirectory(prefix='log014_',dir='/tmp') as root:
        os.chmod(root,0o777)
        roles=(('witness',policy.witness_uid,policy.service_uid),
               ('authority',policy.authority_uid,policy.client_uids[0]),
               ('service',policy.service_uid,policy.client_uids[0]))
        procs=[]
        try:
            for role,uid,expected in roles:
                path=str(Path(root)/(role+'.sock'))
                p=subprocess.Popen([sys.executable,'-u','-c',_SERVER,path,role,str(expected)],
                    preexec_fn=_drop_to(uid),stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                    text=True,close_fds=True)
                procs.append((p,path,role,uid,expected))
                # A blocking readiness line is bounded by process watchdog below.
                import select
                if not select.select([p.stdout],[],[],timeout)[0] or p.stdout.readline().strip()!='READY':
                    raise AdmissionError('role failed startup')
            results=[]
            for p,path,role,uid,expected in procs:
                for caller in (expected, policy.authority_uid if expected!=policy.authority_uid else policy.witness_uid):
                    script='import json,socket,sys; s=socket.socket(socket.AF_UNIX); s.settimeout(2); s.connect(sys.argv[1]); print(s.recv(4096).decode().strip()); s.close()'
                    r=run_as_uid(caller,script,path,timeout=timeout)
                    if r['returncode']!=0: raise AdmissionError('client IPC failed: '+r['stderr'])
                    reply=json.loads(r['stdout'].strip())
                    if reply['peer_uid']!=caller or reply['server_uid']!=uid or reply['ok']!=(caller==expected):
                        raise AdmissionError('kernel credential mismatch')
                    results.append({'role':role,'caller_uid':caller,'accepted':reply['ok'],'server_uid':uid})
            for p,*_ in procs:
                if p.wait(timeout=timeout)!=0: raise AdmissionError('role exited abnormally')
            return results
        finally:
            for p,*_ in procs:
                if p.poll() is None:
                    p.kill()
                try: p.communicate(timeout=timeout)
                except subprocess.TimeoutExpired: p.kill(); p.communicate()

def production_admission(*args, **kwargs):
    """No test harness result is accepted as a production authorization token."""
    raise AdmissionError('LOG-CORE-014 production BLOCKED: independent E2E evidence absent')
