# Exact Source Recovery — three complete TrainOS v107 regressions (16 November 2026)

**Validation:** TrainOS v107 original ZIP `661c0346721f7aa3ace1572430f4259d78bba722c3c4eab540de05eaa36ac284`. All 5,206 ZIP file manifest digests, CRC, and 3,165 Python AST checks passed. **Three complete strict pytest runs each passed 1,533 tests (4,599 test executions, zero failures).**

Run results: 
| Run | Exit | PASS | FAIL | Duration (s) | stdout SHA-256 |
|---|---:|---:|---:|---:|---|
| 1 | 0 | 1533 | 0 | 108.53 | `02fa9ef58b011cb9944d520bc5781c6405c6de338d89f300822496c4f98c96f3` |
| 2 | 0 | 1533 | 0 | 105.31 | `b082720881fedca798d7e870702b8756916611da153495603e334c5c83025569` |
| 3 | 0 | 1533 | 0 | 106.69 | `7a6e79115477f3c23130f77196db731600440c5d68ed71f3f9087be159b091b1` |

The corrected pristine ZIP extractor restored only POSIX file permissions and made the isolated temporary extraction root traversable for Linux cross-UID tests; source bytes were not changed. Warning filters: ResourceWarning, DeprecationWarning, PytestUnraisableExceptionWarning as errors. Two earlier **completed FAILs** with 1,531 PASS / 2 FAIL each and a third **interrupted** diagnostic attempt were retained, not concealed.

Island ISLAND-GEO-022 source ZIP SHA-256 `e71d3d78c79dcea71e151c9d34d10b460a61b0a782eb927042f1c286dab42ce9`; CRC and 967/967 manifest entries passed; three previously completed strict regressions each passed 200 tests.

RailSystem RAIL-TRUST-016 exact source absent. RAIL-TRUST-015 must not be substituted.

**This GitHub commit updates audit evidence and repository metadata ONLY.** No TrainOS, Island or RailSystem module source import completed. The three module branches remain at `0331a2b91762bbe29fcfdeb6b4704a82182b0b75` at the last pre-publication read. No module CAS performed. No force push. No numerical Stage created.

Offline complete source/evidence bundle: `SnowPiercer_Exact_Source_Recovery_Complete_Enrollment_2026-11-16.zip`, SHA-256 `33dfa035323d7d4de9042d2cf0fdc031234023904d671e72abbf689f2980d263`; 88 entries, 11,779,027 bytes. Contains original ZIPs, all PASS and FAIL stdout/stderr/exitcodes/hashes, and corrected staging-for-CAS helper. The bundle is **not** stored on GitHub.

**Release admission and production status remain BLOCKED / NO-GO** until verified source Git tree publication, external isolation/root/LSM evidence, and relevant physical end-to-end safety tests.
