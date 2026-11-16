"""v107 IPC broker replay and real Linux SO_PEERCRED cross-UID negative tests."""
import json
import os
from pathlib import Path
from contextlib import closing
import sqlite3
import subprocess
import sys
import tempfile
import time
import shutil

import pytest
from scripts.ci.uid_broker_v107 import decide, request, private_root


def test_nonce_replay_and_spoof_in_transaction(tmp_path):
    with closing(sqlite3.connect(tmp_path/'test.db')) as db:
        db.execute('CREATE TABLE requests(uid INTEGER,nonce TEXT,operation TEXT,decision TEXT,PRIMARY KEY(uid,nonce))')
        req=json.dumps({'operation':'start','nonce':'d'*32}).encode()
        assert decide(db,65534,65534,req)['reason']=='CONTAINMENT_NOT_CERTIFIED'
        assert decide(db,65534,65534,req)['reason']=='REPLAY'
        assert decide(db,65533,65534,req)['reason']=='INVALID_PEER'
        assert decide(db,65534,65534,json.dumps({'operation':'start','nonce':'e'*32,'uid':0}).encode())['reason']=='UID_SPOOF'
        assert db.execute('SELECT COUNT(*) FROM requests').fetchone()[0]==1


def test_invalid_frame_denied(tmp_path):
    with closing(sqlite3.connect(tmp_path/'test.db')) as db:
        db.execute('CREATE TABLE requests(uid INTEGER,nonce TEXT,operation TEXT,decision TEXT,PRIMARY KEY(uid,nonce))')
        assert decide(db,65534,65534,b'not json')['reason']=='BAD_JSON'
        assert decide(db,65534,65534,b'x'*2500)['reason']=='OVERSIZE'
        assert decide(db,65534,65534,b'{"operation":"shell","nonce":"' + b'a'*32+b'"}')['reason']=='BAD_REQUEST'


@pytest.mark.skipif(os.geteuid()!=0 or not sys.platform.startswith('linux'),reason='requires Linux root for real distinct UIDs')
def test_real_cross_uid_socket_and_persistent_replay():
    top=Path(tempfile.mkdtemp(prefix='trainos-v107-peer-',dir='/tmp'))
    os.chmod(top,0o711)
    root=top/'broker'; root.mkdir(mode=0o711)
    server=subprocess.Popen([sys.executable,'-m','scripts.ci.uid_broker_v107','serve',
            '--root',str(root),'--allowed-uid','65534','--max-requests','4','--report',str(top/'report.json')],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    def run(uid,nonce,claim=None):
        cmd=[sys.executable,'-m','scripts.ci.uid_broker_v107','request','--socket',str(root/'admission.sock'),'--nonce',nonce]
        if claim is not None:cmd.extend(['--claimed-uid',str(claim)])
        def drop():
            os.setgroups([]);os.setgid(uid);os.setuid(uid)
        return subprocess.run(cmd,capture_output=True,text=True,timeout=8,preexec_fn=drop)
    try:
        for _ in range(100):
            if (root/'admission.sock').exists():break
            if server.poll() is not None:raise RuntimeError(server.stderr.read())
            time.sleep(.02)
        a=run(65534,'a'*32)
        b=run(65534,'a'*32)
        c=run(65533,'b'*32)
        d=run(65534,'c'*32,claim=0)
        assert [a.returncode,b.returncode,c.returncode,d.returncode]==[125]*4
        assert [json.loads(r.stdout)['reason'] for r in (a,b,c,d)]==[
          'CONTAINMENT_NOT_CERTIFIED','REPLAY','INVALID_PEER','UID_SPOOF']
        out,err=server.communicate(timeout=8)
        assert server.returncode==0,(out,err)
        result=json.loads((top/'report.json').read_text())
        assert [x['uid'] for x in result['requests']]==[65534,65534,65533,65534]
        assert result['production_admitted'] is False
        assert os.stat(root/'broker-journal.sqlite').st_mode & 0o077==0
    finally:
        if server.poll() is None:
            server.kill();server.communicate(timeout=5)
        shutil.rmtree(top)
