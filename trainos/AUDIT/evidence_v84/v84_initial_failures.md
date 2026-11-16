# v84 failed attempts (retained)

1. First new SQLite ownership test failed because its instrumentation proxy did not forward `row_factory`. Corrected proxy and verified PASS.
2. First strict combined attempt completed `329 passed, 5 failed` because the new migration audit encoded `moved` as a list, while historical regression selector expects a mapping. Fixed audit format to `old_path: new_path`. The failed attempt was observed in the local execution output; full original log was overwritten by the subsequent run and is not claimed as preserved.
3. v83 combined warning evidence is copied for comparison; its failures are not reclassified as v84 failures.
