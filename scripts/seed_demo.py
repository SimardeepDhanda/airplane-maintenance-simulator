"""Seed (or reset) the demo database. Idempotent: existing demo rows are replaced.

Requires the NASA data (`make data`) and a trained model (`make pipeline`).

Usage:
    uv run python scripts/seed_demo.py
    uv run python scripts/seed_demo.py --seed 7 --aircraft 20
"""

import argparse
import sys
from pathlib import Path

from aerofleet_ml.data.cmapss import DatasetError
from app.config import get_settings
from app.db import build_engine, build_session_factory
from app.simulation.airline import ScheduleConfig
from app.simulation.seed import SeedError, seed_database

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--data", type=Path, default=REPO_ROOT / "data" / "raw" / "cmapss")
    parser.add_argument("--artifacts", type=Path, default=REPO_ROOT / "ml" / "artifacts")
    parser.add_argument("--seed", type=int, default=ScheduleConfig.seed)
    parser.add_argument("--aircraft", type=int, default=ScheduleConfig.n_aircraft)
    parser.add_argument("--days", type=int, default=ScheduleConfig.days)
    args = parser.parse_args()

    latest = args.artifacts / "LATEST"
    if not latest.is_file():
        print(f"error: {latest} not found; run `make pipeline`", file=sys.stderr)
        return 1
    artifact_dir = args.artifacts / latest.read_text().strip()
    config = ScheduleConfig(seed=args.seed, n_aircraft=args.aircraft, days=args.days)

    settings = get_settings()
    engine = build_engine(settings)
    try:
        with build_session_factory(engine)() as session:
            report = seed_database(
                session,
                args.data,
                artifact_dir,
                config,
                planning_buffer=settings.planning_buffer_cycles,
            )
    except (SeedError, DatasetError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()

    print(f"model     {report.model_version} ({report.data_kind})")
    print(f"aircraft  {report.aircraft}   engines {report.engines}   flights {report.flights}")
    print(f"sensor rows {report.observations}   NASA FD001 test units {list(report.source_units)}")
    print(f"maintenance job cards {report.maintenance_jobs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
