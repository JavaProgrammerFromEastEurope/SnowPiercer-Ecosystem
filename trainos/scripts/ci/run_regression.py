#!/usr/bin/env python3
"""Run a deterministic regression selection across stage directories.

The selector includes only test files under tests/stageN for the inclusive range,
plus optional explicit test paths. It emits a machine-readable evidence report.
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, time
from pathlib import Path

def select(root: Path, start: int, end: int) -> list[str]:
    """Select legacy stage ranges, resolving physically migrated test paths."""
    selected = set()
    for number in range(start, end + 1):
        directory = root / 'tests' / f'stage{number}'
        if directory.is_dir():
            selected.update(p.relative_to(root).as_posix() for p in directory.rglob('test_*.py') if p.is_file())
    for manifest in sorted((root / 'AUDIT').glob('FUNCTIONAL_STAGE_PHYSICAL_MIGRATION_V*.json')):
        data = json.loads(manifest.read_text(encoding='utf-8'))
        moved = data.get('moved', {})
        entries = moved.items() if isinstance(moved, dict) else ((entry['from'], entry['to']) for entry in moved)
        for old, new in entries:
            parts = Path(old).parts
            if len(parts) < 3 or parts[0] != 'tests' or not parts[1].startswith('stage'):
                continue
            stage_number = parts[1][5:]
            if stage_number.isdecimal() and start <= int(stage_number) <= end:
                if (root / new).is_file():
                    selected.add(new)
    return sorted(selected)

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--start', type=int, required=True)
    parser.add_argument('--end', type=int, required=True)
    parser.add_argument('--include', action='append', default=[], help='additional explicit pytest path (repeatable)')
    parser.add_argument('--report', type=Path, help='write JSON evidence report')
    parser.add_argument('--timeout-seconds', type=int, default=1800, help='hard timeout for pytest (default: 1800 seconds)')
    parser.add_argument('--dry-run', action='store_true', help='print selection without executing pytest')
    args=parser.parse_args()
    root=args.root.resolve()
    if args.start < 1 or args.end < args.start:
        parser.error('require 1 <= start <= end')
    if args.timeout_seconds < 1:
        parser.error('--timeout-seconds must be >= 1')
    selected=select(root,args.start,args.end)
    for raw in args.include:
        path=(root / raw).resolve()
        try:
            relative = path.relative_to(root)
        except ValueError:
            parser.error(f'included path must stay inside --root: {raw}')
        if not path.is_file():
            parser.error(f'included path is not a file: {raw}')
        if not relative.parts or relative.parts[0] != 'tests':
            parser.error(f'included path must be inside tests/: {raw}')
        if path.suffix != '.py' or not path.name.startswith('test_'):
            parser.error(f'included path must be a test_*.py file: {raw}')
        selected.append(relative.as_posix())
    selected=sorted(dict.fromkeys(selected))
    if not selected:
        print('error: selection contains no test files', file=sys.stderr); return 2
    if args.dry_run:
        print(json.dumps({'start':args.start,'end':args.end,'test_file_count':len(selected),'files':selected},indent=2))
        return 0
    started=time.monotonic()
    command=[sys.executable,'-m','pytest','-q',*selected]
    try:
        result=subprocess.run(command,cwd=root,env={**os.environ,'PYTHONPATH':str(root)},timeout=args.timeout_seconds)
        exit_code=result.returncode
        outcome='PASS' if exit_code==0 else 'FAIL'
        timeout_detail=None
    except subprocess.TimeoutExpired as exc:
        exit_code=124
        outcome='TIMEOUT'
        timeout_detail={'timeout_seconds':args.timeout_seconds,'partial_stdout':_as_text(exc.stdout),'partial_stderr':_as_text(exc.stderr)}
    elapsed=round(time.monotonic()-started,3)
    report={'schema_version':1,'selection_policy':'all test_*.py files recursively under tests/stageN for inclusive stage range; sorted unique paths', 'start_stage':args.start,'end_stage':args.end,'test_files_selected':len(selected),'selected_files':selected,'command':command,'timeout_seconds':args.timeout_seconds,'exit_code':exit_code,'result':outcome,'elapsed_seconds':elapsed}
    if timeout_detail is not None:
        report['timeout_details']=timeout_detail
    if args.report:
        report_path = args.report if args.report.is_absolute() else root / args.report
        report_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = report_path.with_name(report_path.name + '.tmp')
        temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        temporary.replace(report_path)
    print(f"Regression stages {args.start}-{args.end}: {report['result']} | files={len(selected)} | {elapsed}s")
    if args.report:
        report_path = args.report if args.report.is_absolute() else root / args.report
        print(f"Evidence report: {report_path}")
    return exit_code

def _as_text(value):
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    return str(value)

if __name__=='__main__': raise SystemExit(main())
