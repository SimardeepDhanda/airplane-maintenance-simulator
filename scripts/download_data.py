"""Download (or import) NASA C-MAPSS and verify it.

Usage:
    uv run python scripts/download_data.py
    uv run python scripts/download_data.py --source ~/Downloads/CMAPSSData.zip
"""

import argparse
import sys
from pathlib import Path

from aerofleet_ml.data.cmapss import SOURCE_URL, DatasetError, acquire, validate_subset

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--source", default=SOURCE_URL, help="https URL or local .zip path")
    parser.add_argument("--destination", type=Path, default=REPO_ROOT / "data" / "raw")
    parser.add_argument("--subset", default="FD001", help="subset to validate after extraction")
    args = parser.parse_args()

    try:
        record = acquire(args.source, args.destination)
        stats = validate_subset(args.destination / "cmapss", args.subset)
    except DatasetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"archive  {record.archive_kind}  sha256={record.archive_sha256}")
    print(f"files    {len(record.files)} written to {args.destination / 'cmapss'}")
    print(
        f"{stats.subset}   train {stats.train_rows} rows / {stats.train_units} units; "
        f"test {stats.test_rows} rows / {stats.test_units} units; RUL {stats.rul_rows} rows"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
