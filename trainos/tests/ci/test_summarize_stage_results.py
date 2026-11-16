import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ci" / "summarize_stage_results.py"
spec = importlib.util.spec_from_file_location("summarize_stage_results", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SummarizeStageResultsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.summary = self.root / "summary.tsv"
        self.header = "stage\tstatus\texit_code\tseconds\tlog\n"

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, body):
        self.summary.write_text(self.header + body, encoding="utf-8")

    def test_aggregates_pass_fail_timeout_and_checks_logs(self):
        self.write("1\tPASS\t0\t2\tstage1.log\n2\tFAIL\t1\t3\tstage2.log\n3\tTIMEOUT\t124\t5\tstage3.log\n")
        for name in ("stage1.log", "stage2.log", "stage3.log"):
            (self.root / name).touch()
        report = module.summarize(self.summary, check_logs=True)
        self.assertEqual(report["counts"], {"PASS": 1, "FAIL": 1, "TIMEOUT": 1})
        self.assertEqual(report["total_seconds"], 10)
        self.assertFalse(report["successful"])

    def test_empty_summary_rejected(self):
        self.write("")
        with self.assertRaises(module.SummaryError):
            module.summarize(self.summary)

    def test_duplicate_stage_rejected(self):
        self.write("1\tPASS\t0\t1\tstage1.log\n1\tPASS\t0\t1\tstage1.log\n")
        with self.assertRaisesRegex(module.SummaryError, "duplicate stage"):
            module.summarize(self.summary)

    def test_inconsistent_status_and_exit_code_rejected(self):
        self.write("1\tPASS\t1\t1\tstage1.log\n")
        with self.assertRaisesRegex(module.SummaryError, "non-zero exit code"):
            module.summarize(self.summary)

    def test_missing_log_rejected_when_requested(self):
        self.write("1\tPASS\t0\t1\tstage1.log\n")
        with self.assertRaisesRegex(module.SummaryError, "missing log"):
            module.summarize(self.summary, check_logs=True)

    def test_json_report_is_machine_readable(self):
        self.write("1\tPASS\t0\t1\tstage1.log\n")
        report = module.summarize(self.summary)
        self.assertTrue(report["successful"])
        self.assertEqual(json.loads(json.dumps(report))["stage_count"], 1)


if __name__ == "__main__":
    unittest.main()
