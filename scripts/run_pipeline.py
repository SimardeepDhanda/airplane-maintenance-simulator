"""Train, calibrate, evaluate, and save a RUL model in one reproducible run.

Usage:
    uv run python scripts/run_pipeline.py                 # FD001 from data/raw/cmapss
    uv run python scripts/run_pipeline.py --seed 7 --output /tmp/models
"""

import argparse
import sys
from pathlib import Path

from aerofleet_ml.data.cmapss import DatasetError
from aerofleet_ml.pipeline import PipelineConfig, run_pipeline

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--data", type=Path, default=REPO_ROOT / "data" / "raw" / "cmapss")
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "ml" / "artifacts")
    parser.add_argument("--subset", default="FD001")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.subset != "FD001":
        print("error: only FD001 is supported until multi-regime handling exists", file=sys.stderr)
        return 2
    try:
        result = run_pipeline(
            args.data, args.output, PipelineConfig(subset=args.subset, seed=args.seed)
        )
    except DatasetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    m = result.metrics
    sel = m["selection"]["selected"]
    print(f"model    {result.model_version}  ({m['data_kind']})")
    print(f"selected {sel['model']} target_cap={sel['target_cap']} by {m['selection']['metric']}")
    print(f"test, last observed cycle per engine (n={m['test']['n_engines']}):")
    print(f"  {'model':<13}{'cap':>5}{'RMSE':>8}{'MAE':>8}{'RMSE*':>8}{'PHM08':>10}")
    for row in m["test"]["comparison"]:
        s = row["last_cycle"]
        flag = " <" if row["selected"] else ""
        print(
            f"  {row['model']:<13}{row['target_cap'] or '-':>5}{s['rmse']:>8.2f}{s['mae']:>8.2f}"
            f"{s['rmse_vs_capped_truth']:>8.2f}{s['phm08_score']:>10.1f}{flag}"
        )
    iv = m["test"]["intervals"]
    print(
        f"interval nominal {iv['nominal_coverage']:.0%}: last-cycle coverage "
        f"{iv['last_cycle']['coverage']:.1%} (width {iv['last_cycle']['mean_width']:.1f}), "
        f"all-cycle coverage {iv['all_cycles']['coverage']:.1%}"
    )
    print(f"saved    {result.artifact_dir}")
    print("RMSE* = against true RUL capped at the target cap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
