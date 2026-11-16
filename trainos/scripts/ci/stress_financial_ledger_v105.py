"""Repeat concurrent WAL startup/idempotent append under strict warnings."""
from __future__ import annotations
from concurrent.futures import ProcessPoolExecutor,ThreadPoolExecutor
import json
import multiprocessing
from pathlib import Path
import sys
import tempfile
import time

from kernel.economy.ledger_contract import FinancialLedger,JournalEntry,Posting

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'AUDIT/evidence_v105'


def task(database, operation):
    entry=JournalEntry(operation,(Posting('customer','USD','debit',1),
                                  Posting('merchant','USD','credit',1)),'v105 concurrent startup')
    with FinancialLedger(database,timeout_seconds=6) as ledger:
        return ledger.append(entry)


def main():
    started=time.monotonic()
    evidence={'schema':'trainos.v105.wal-concurrent-stress','cases':[],'status':'FAIL'}
    try:
        with tempfile.TemporaryDirectory(prefix='trainos-v105-wal-') as tmp:
            for i in range(8):
                database=str(Path(tmp)/f'ledger_{i}.db')
                name=f'operation-{i}'
                with ThreadPoolExecutor(max_workers=16) as threads:
                    t_results=list(threads.map(task,[database]*32,[name]*32))
                with ProcessPoolExecutor(max_workers=4,mp_context=multiprocessing.get_context('spawn')) as pool:
                    p_results=list(pool.map(task,[database]*16,[name]*16))
                with FinancialLedger(database) as ledger:
                    ok=ledger.journal_count()==1 and ledger.verify_integrity()['ok']
                record={'iteration':i,'thread_true':t_results.count(True),
                        'thread_false':t_results.count(False),'process_true':p_results.count(True),
                        'process_false':p_results.count(False),'integrity':ok}
                evidence['cases'].append(record)
                if not (record['thread_true']==1 and record['thread_false']==31 and
                        record['process_true']==0 and record['process_false']==16 and ok):
                    raise AssertionError(record)
            evidence['status']='PASS'
    except Exception as exc:
        evidence['failure']=repr(exc)
    evidence['duration_seconds']=round(time.monotonic()-started,3)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'WAL_CONCURRENCY_STRESS_V105.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps({'status':evidence['status'],'cases':len(evidence['cases']),
                      'duration_seconds':evidence['duration_seconds']},indent=2))
    return 0 if evidence['status']=='PASS' else 1

if __name__ == '__main__':
    raise SystemExit(main())
