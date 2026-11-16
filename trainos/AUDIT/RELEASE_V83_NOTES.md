# TrainOS v83

SQLite context-manager semantics: `with sqlite3.connect(...)` manages transaction only, not connection lifetime. Test fixtures now explicitly close these connections via `contextlib.closing`.

Ten legacy recovery modules moved into the named recovery domain; numeric Stage directories not created.

Three complete strict recovery-domain passes: 178/178 each. Combined run status recorded separately in evidence. Full suite and hosted CI remain unverified.
