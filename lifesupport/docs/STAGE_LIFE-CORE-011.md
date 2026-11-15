# Stage LIFE-CORE-011

Run from `lifesupport/`:

```sh
PYTHONPATH=src python -W error::ResourceWarning -m unittest discover -s tests -v
```

This is a cumulative package of LIFE-CORE-002 through LIFE-CORE-011. The Stage introduces a `<database>.rotation-fence` sentinel, created before the `.rotation` intent while holding the SQLite writer transaction. The admission UDF checks the sentinel on each event INSERT. A crashed rotation remains blocked. Do not manually delete the sentinel without an operator-approved recovery procedure and validation of both anchors and SQLite history. `inspect_interrupted_rotation` is read-only.

The sentinel is not a substitute for OS-level service isolation, mandatory access controls, independent key custody or hardware tests.
