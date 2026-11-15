"""Command line entrypoint for local RailSystem verification."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
from .verification import write_evidence

def main():
    parser = argparse.ArgumentParser(description='RailSystem local regression evidence')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    report = write_evidence(root, args.output, timestamp=timestamp)
    print(f"Tests: {report['regression']['tests_run']}, successful: {report['regression']['successful']}")
    return 0 if report['regression']['successful'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
