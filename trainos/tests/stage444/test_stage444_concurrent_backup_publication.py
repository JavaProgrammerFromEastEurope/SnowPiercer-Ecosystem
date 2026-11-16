from concurrent.futures import ThreadPoolExecutor
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_concurrent_backup_publishers_do_not_clobber(tmp_path):
    db=tmp_path/'ledger.db'; target=tmp_path/'backup.db'; store=CommandIdempotencyStore(db)
    try: store.claim('k','noop',{})
    finally: store.close()
    stores=[CommandIdempotencyStore(db),CommandIdempotencyStore(db)]
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(s.backup_to,target) for s in stores]
            results=[]
            for future in futures:
                try: results.append(('ok',future.result()))
                except FileExistsError: results.append(('exists',None))
        assert sorted(kind for kind,_ in results)==['exists','ok']
        assert CommandIdempotencyStore.validate_backup(target)==()
    finally:
        for s in stores: s.close()
