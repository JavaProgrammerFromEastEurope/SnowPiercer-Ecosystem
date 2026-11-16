#!/usr/bin/env python3
"""Run pytest with a hard timeout and preserve the last observed test in evidence."""
from __future__ import annotations
import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

TEST_LINE = re.compile(r"^(?P<node>tests/\S+?::\S+?)(?:\s+<-\s+\S+)?(?:\s+(?P<outcome>PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS))?(?:\s|$)")
PYTEST_SUMMARY = re.compile(r"(?P<count>\d+)\s+(?P<outcome>passed|failed|error|errors|skipped|xfailed|xpassed)\b", re.I)
OUTCOMES = ("PASSED", "FAILED", "ERROR", "SKIPPED", "XFAIL", "XPASS")
COLLECTED_LINE = re.compile(r"(?:(?P<before>\d+)\s+(?:items?|tests?)\s+collected|collected\s+(?P<after>\d+)\s+(?:items?|tests?))")


def summarize_log(text: str, *, tail_lines: int = 40) -> dict:
    """Extract conservative progress evidence from pytest -vv output."""
    if tail_lines < 1:
        raise ValueError("tail_lines must be >= 1")
    last_observed = None
    last_completed = None
    collected_tests = None
    completed_counts = {key: 0 for key in OUTCOMES}
    for line in text.splitlines():
        collection_match = COLLECTED_LINE.search(line)
        if collection_match:
            collected_tests = int(collection_match.group("before") or collection_match.group("after"))
        stripped = line.strip()
        if "::" not in stripped or not stripped.startswith("tests/"):
            continue
        match = TEST_LINE.match(stripped)
        if not match:
            continue
        node, outcome = match.group("node"), match.group("outcome")
        last_observed = node
        if outcome:
            completed_counts[outcome] += 1
            last_completed = node
    lines = text.splitlines()
    summary_counts = {key: 0 for key in OUTCOMES}
    summary_seen = False
    for line in lines:
        # Pytest terminal summaries are independent corroboration, not a substitute
        # for individual test-node evidence. Parse only the short-summary footer.
        if re.search(r"(?:^|\s)in\s+\d+(?:\.\d+)?s\s*$", line.strip()):
            matches = list(PYTEST_SUMMARY.finditer(line))
            if matches:
                summary_seen = True
                for match in matches:
                    key = match.group("outcome").upper()
                    if key == "ERRORS":
                        key = "ERROR"
                    if key == "XFAILED":
                        key = "XFAIL"
                    if key == "XPASSED":
                        key = "XPASS"
                    summary_counts[key] += int(match.group("count"))
    completed_total = sum(completed_counts.values())
    remaining = None if collected_tests is None else max(0, collected_tests - completed_total)
    return {
        "collected_tests": collected_tests,
        "last_observed_test": last_observed,
        "last_completed_test": last_completed,
        "observed_outcome_counts": completed_counts,
        "log_tail": lines[-tail_lines:],
        "observed_completed_tests": completed_total,
        "unobserved_or_incomplete_tests": remaining,
        "terminal_summary_present": summary_seen,
        "terminal_summary_counts": summary_counts if summary_seen else None,
        "observed_vs_summary_mismatch": (any(completed_counts[key] > summary_counts[key] for key in OUTCOMES) if summary_seen else None),
    }


def build_report(*, command: list[str], result: str, exit_code: int,
                 elapsed_seconds: float, timeout_seconds: int, log_path: Path,
                 log_text: str) -> dict:
    report = {
        "schema_version": 1,
        "result": result,
        "exit_code": exit_code,
        "timeout_seconds": timeout_seconds,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "command": command,
        "log_path": str(log_path),
        "progress": summarize_log(log_text),
    }
    report["evidence_complete"] = result in ("PASS", "FAIL")
    if result == "INCOMPLETE_TIMEOUT":
        report["note"] = "A timeout is incomplete evidence, not a test-suite pass or assertion failure."
    return report


def atomic_json(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--log", type=Path, default=Path("test-logs/full-suite-verbose.log"))
    parser.add_argument("--report", type=Path, default=Path("test-logs/full-suite-diagnostic.json"))
    parser.add_argument("--tail-lines", type=int, default=40, help="number of log lines kept in the JSON report")
    parser.add_argument("pytest_args", nargs="*", help="additional pytest arguments")
    args = parser.parse_args()
    if args.timeout_seconds < 1:
        parser.error("--timeout-seconds must be >= 1")
    if args.tail_lines < 1:
        parser.error("--tail-lines must be >= 1")
    root = args.root.resolve()
    log_path = args.log if args.log.is_absolute() else root / args.log
    report_path = args.report if args.report.is_absolute() else root / args.report
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", "pytest", "-vv", "--durations=20", *args.pytest_args]
    started = time.monotonic()
    result_name, exit_code = "FAIL", 1
    with log_path.open("w", encoding="utf-8", buffering=1) as log:
        process = subprocess.Popen(command, cwd=root,
            env={**os.environ, "PYTHONPATH": str(root)}, stdout=log,
            stderr=subprocess.STDOUT, start_new_session=True)
        try:
            exit_code = process.wait(timeout=args.timeout_seconds)
            result_name = "PASS" if exit_code == 0 else "FAIL"
        except subprocess.TimeoutExpired:
            result_name, exit_code = "INCOMPLETE_TIMEOUT", 124
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
            except ProcessLookupError:
                process.wait()
    elapsed = time.monotonic() - started
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    report = build_report(command=command, result=result_name, exit_code=exit_code,
        elapsed_seconds=elapsed, timeout_seconds=args.timeout_seconds,
        log_path=log_path, log_text=log_text)
    report["progress"] = summarize_log(log_text, tail_lines=args.tail_lines)
    atomic_json(report_path, report)
    print(f"Full pytest: {result_name} | elapsed={report['elapsed_seconds']}s | "
          f"collected={report['progress']['collected_tests']} "
          f"last_observed={report['progress']['last_observed_test']}")
    print(f"Log: {log_path}\nReport: {report_path}")
    return exit_code

if __name__ == "__main__":
    raise SystemExit(main())
