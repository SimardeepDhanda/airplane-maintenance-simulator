# Trains a remaining-useful-life model on NASA's C-MAPSS FD001 data and writes
# web/public/fleet.json, which is everything the website needs.
#
#   pip install -r model/requirements.txt
#   python model/train.py

import io
import json
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "model" / "data"
OUT_FILE = ROOT / "web" / "public" / "fleet.json"
DATA_URL = "https://phm-datasets.s3.amazonaws.com/NASA/6.+Turbofan+Engine+Degradation+Simulation+Data+Set.zip"

COLUMNS = ["unit", "cycle", "op1", "op2", "op3"] + [f"s{i}" for i in range(1, 22)]
# These sensors barely move in FD001, so they don't help.
SENSORS = ["s2", "s3", "s4", "s7", "s8", "s9", "s11", "s12", "s13", "s14", "s15", "s17", "s20", "s21"]
RUL_CAP = 125  # early in life the engine looks healthy, so cap the target here
WINDOW = 30  # picked by 4-fold validation on the training engines (10, 20, 30)
FLEET_SIZE = 20
SEED = 7


def download():
    if (DATA_DIR / "train_FD001.txt").exists():
        return
    print("downloading C-MAPSS...")
    outer = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(DATA_URL).read()))
    inner_name = next(n for n in outer.namelist() if n.endswith("CMAPSSData.zip"))
    inner = zipfile.ZipFile(io.BytesIO(outer.read(inner_name)))
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name in ["train_FD001.txt", "test_FD001.txt", "RUL_FD001.txt"]:
        (DATA_DIR / name).write_bytes(inner.read(name))


def load(name):
    return pd.read_csv(DATA_DIR / name, sep=r"\s+", header=None, names=COLUMNS)


def add_features(df):
    # Rolling mean/slope over the last few cycles, per engine. Only looks backwards.
    df = df.sort_values(["unit", "cycle"]).copy()
    grouped = df.groupby("unit")[SENSORS]
    means = grouped.rolling(WINDOW, min_periods=1).mean().reset_index(level=0, drop=True)
    diffs = grouped.diff(WINDOW - 1).fillna(0)
    for s in SENSORS:
        df[f"{s}_mean"] = means[s]
        df[f"{s}_diff"] = diffs[s]
    return df


def feature_cols():
    return ["cycle"] + SENSORS + [f"{s}_mean" for s in SENSORS] + [f"{s}_diff" for s in SENSORS]


def rmse(a, b):
    return float(np.sqrt(np.mean((np.asarray(a) - np.asarray(b)) ** 2)))


def main():
    download()
    train = add_features(load("train_FD001.txt"))
    test = add_features(load("test_FD001.txt"))
    true_rul = pd.read_csv(DATA_DIR / "RUL_FD001.txt", header=None)[0].to_numpy()

    train["rul"] = train.groupby("unit")["cycle"].transform("max") - train["cycle"]
    y = train["rul"].clip(upper=RUL_CAP)
    X = train[feature_cols()]

    model = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, random_state=SEED)
    model.fit(X, y)
    baseline = LinearRegression().fit(X, y)

    # Score on the last observed cycle of each test engine, like the original challenge.
    last = test.groupby("unit").tail(1).sort_values("unit")
    pred = model.predict(last[feature_cols()])
    base_pred = baseline.predict(last[feature_cols()])
    truth = np.minimum(true_rul, RUL_CAP)
    scores = {
        "model_rmse": round(rmse(pred, truth), 1),
        "model_mae": round(float(np.mean(np.abs(pred - truth))), 1),
        "baseline_rmse": round(rmse(base_pred, truth), 1),
        "test_engines": len(truth),
    }
    print(f"gradient boosting  RMSE {scores['model_rmse']}  MAE {scores['model_mae']}")
    print(f"linear baseline    RMSE {scores['baseline_rmse']}")

    # Build a made-up fleet out of test engines. Each plane flies a few legs a day,
    # and one leg = one engine cycle.
    rng = np.random.default_rng(SEED)
    units = sorted(rng.choice(last["unit"].to_numpy(), size=FLEET_SIZE, replace=False))
    engines = []
    for i, unit in enumerate(units):
        rows = test[test["unit"] == unit]
        history = np.clip(model.predict(rows[feature_cols()]), 0, None)
        final_cycle = int(rows["cycle"].max())
        actual_final = int(true_rul[unit - 1])
        engines.append({
            "tail": f"N{201 + i}AF",
            "engine": f"FD001-{unit:03d}",
            "cycles_flown": final_cycle,
            "flights_per_day": int(rng.integers(3, 7)),
            "predicted_rul": round(float(history[-1])),
            "actual_rul": actual_final,
            "history": [
                {
                    "cycle": int(c),
                    "predicted": round(float(p)),
                    "actual": min(actual_final + final_cycle - int(c), RUL_CAP),
                }
                for c, p in zip(rows["cycle"], history)
            ],
        })

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps({"scores": scores, "rul_cap": RUL_CAP, "engines": engines}))
    print(f"wrote {OUT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
