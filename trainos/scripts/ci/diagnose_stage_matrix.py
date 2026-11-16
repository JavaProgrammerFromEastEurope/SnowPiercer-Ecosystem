#!/usr/bin/env python3
"""Diagnose stage-matrix summaries and rank slow, failed, and timed-out stages."""
from __future__ import annotations
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

EXPECTED_HEADER = ["stage", "status", "exit_code", "seconds", "log"]
VALID_STATUSES = {"PASS", "FAIL", "TIMEOUT"}


class DiagnosticError(ValueError):
    """Raised when a stage summary is malformed or contradictory."""


def diagnose(path: Path, *, top: int = 10, slow_seconds: int = 30,
             expected_start: int | None = None, expected_end: int | None = None,
             check_logs: bool = False) -> dict:
    if top < 1:
        raise DiagnosticError("top must be >= 1")
    if slow_seconds < 0:
        raise DiagnosticError("slow_seconds must be >= 0")
    if (expected_start is None) != (expected_end is None):
        raise DiagnosticError("expected_start and expected_end must be supplied together")
    if expected_start is not None and (expected_start < 1 or expected_end < expected_start):
        raise DiagnosticError("expected stage range must satisfy 1 <= start <= end")
    if not path.is_file():
        raise DiagnosticError(f"summary file does not exist: {path}")

    rows = []
    seen = set()
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames != EXPECTED_HEADER:
            raise DiagnosticError("invalid summary header")
        for line, row in enumerate(reader, start=2):
            if None in row or any(row.get(key) is None for key in EXPECTED_HEADER):
                raise DiagnosticError(f"malformed row at line {line}")
            try:
                stage, code, seconds = int(row["stage"]), int(row["exit_code"]), int(row["seconds"])
            except ValueError as exc:
                raise DiagnosticError(f"non-integer numeric field at line {line}") from exc
            if stage < 1 or seconds < 0:
                raise DiagnosticError(f"invalid stage or seconds at line {line}")
            if stage in seen:
                raise DiagnosticError(f"duplicate stage {stage}")
            seen.add(stage)
            status = row["status"]
            if status not in VALID_STATUSES:
                raise DiagnosticError(f"invalid status {status!r} at line {line}")
            if status == "PASS" and code != 0:
                raise DiagnosticError(f"PASS stage {stage} has non-zero exit code")
            if status == "FAIL" and code == 0:
                raise DiagnosticError(f"FAIL stage {stage} has zero exit code")
            if status == "TIMEOUT" and code not in (124, 137):
                raise DiagnosticError(f"TIMEOUT stage {stage} has unexpected exit code")
            log = row["log"]
            if not log or Path(log).name != log or log in {".", ".."}:
                raise DiagnosticError(f"invalid log filename at line {line}")
            if check_logs and not (path.parent / log).is_file():
                raise DiagnosticError(f"missing log for stage {stage}: {log}")
            rows.append({"stage": stage, "status": status, "exit_code": code,
                         "seconds": seconds, "log": log})
    if not rows:
        raise DiagnosticError("summary contains no stage results")

    missing = []
    if expected_start is not None:
        missing = sorted(set(range(expected_start, expected_end + 1)) - seen)
    counts = Counter(r["status"] for r in rows)
    slow = sorted((r for r in rows if r["seconds"] >= slow_seconds),
                  key=lambda r: (-r["seconds"], r["stage"]))
    failed = sorted((r for r in rows if r["status"] == "FAIL"), key=lambda r: r["stage"])
    timed_out = sorted((r for r in rows if r["status"] == "TIMEOUT"), key=lambda r: r["stage"])
    return {
        "schema_version": 1,
        "source": path.name,
        "stage_count": len(rows),
        "counts": {s: counts.get(s, 0) for s in ("PASS", "FAIL", "TIMEOUT")},
        "total_seconds": sum(r["seconds"] for r in rows),
        "slow_threshold_seconds": slow_seconds,
        "slow_stages": slow,
        "slowest_stages": sorted(rows, key=lambda r: (-r["seconds"], r["stage"]))[:top],
        "failed_stages": failed,
        "timed_out_stages": timed_out,
        "expected_range": None if expected_start is None else {"start": expected_start, "end": expected_end},
        "missing_stages": missing,
        "coverage_complete": not missing if expected_start is not None else None,
        "successful": all(r["status"] == "PASS" for r in rows) and not missing,
        "stages": sorted(rows, key=lambda r: r["stage"]),
    }


def _atomic_json(path: Path, report: dict) -> None:
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
    parser.add_argument("summary", type=Path)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--slow-seconds", type=int, default=30)
    parser.add_argument("--expect-start", type=int)
    parser.add_argument("--expect-end", type=int)
    parser.add_argument("--check-logs", action="store_true")
    parser.add_argument("--json", dest="json_path", type=Path)
    parser.add_argument("--require-complete", action="store_true",
                        help="return non-zero if expected stages are missing or any stage is not PASS")
    args = parser.parse_args()
    try:
        report = diagnose(args.summary, top=args.top, slow_seconds=args.slow_seconds,
                          expected_start=args.expect_start, expected_end=args.expect_end,
                          check_logs=args.check_logs)
        if args.json_path:
            _atomic_json(args.json_path, report)
    except (OSError, csv.Error, DiagnosticError) as exc:
        print(f"diagnostic error: {exc}", file=sys.stderr)
        return 2
    print(f"Stages: {report['stage_count']} | PASS: {report['counts']['PASS']} | "
          f"FAIL: {report['counts']['FAIL']} | TIMEOUT: {report['counts']['TIMEOUT']} | "
          f"slow: {len(report['slow_stages'])} | missing: {len(report['missing_stages'])}")
    if args.json_path:
        print(f"JSON report: {args.json_path}")
    return 1 if args.require_complete and not report["successful"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
