"""Placement readiness model (scikit-learn).

A logistic regression predicts the probability that a student gets placed from seven
profile factors, each scaled 0..1. The readiness score shown in the app is that
probability times 100.

Training data
-------------
The app trains on data/placement_history.csv. If that file does not exist, a SYNTHETIC
history is generated so the project runs out of the box. Synthetic data only demonstrates
the pipeline; replace the CSV with your college's real records and retrain:

    python readiness_model.py                 # retrain on data/placement_history.csv
    python readiness_model.py path/to/my.csv  # train on another file

CSV columns: market, acad, skills, proj, exp, cert, resume, placed
  market  average of the student's three best match scores, 0..1
  acad    (CGPA - 5) / 4, less 0.1 per active backlog, clipped to 0..1
  skills  number of skills / 10, capped at 1
  proj    number of projects / 3, capped at 1
  exp     0 for no internship, 0.8 for one, 1 for two or more
  cert    number of certifications / 2, capped at 1
  resume  1 if a resume is on file, else 0
  placed  1 if the student received an offer, else 0
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from config import DATA_DIR

CSV_PATH = DATA_DIR / "placement_history.csv"
MODEL_PATH = DATA_DIR / "readiness_model.joblib"
SYNTHETIC_FLAG = DATA_DIR / "placement_history.SYNTHETIC"

FEATURES = ["market", "acad", "skills", "proj", "exp", "cert", "resume"]
# Assumed importance of each factor, used ONLY to generate the synthetic history.
_SYNTHETIC_WEIGHTS = np.array([0.25, 0.20, 0.20, 0.12, 0.10, 0.08, 0.05])


def synthetic_history(n: int = 1500, seed: int = 42) -> pd.DataFrame:
    """Generate a plausible placement history. Not real data."""
    rng = np.random.default_rng(seed)
    ability = rng.beta(2.2, 2.2, n)                               # shared latent strength
    mix = lambda spread: np.clip(0.45 * ability + 0.55 * rng.beta(2, 2, n) + rng.normal(0, spread, n), 0, 1)
    market, acad, skills = mix(0.08), mix(0.10), mix(0.10)
    proj = np.round(mix(0.12) * 3) / 3
    e = mix(0.15)
    exp = np.where(e > 0.72, 1.0, np.where(e > 0.48, 0.8, 0.0))
    cert = np.round(mix(0.15) * 2) / 2
    resume = (rng.random(n) < 0.35 + 0.55 * ability).astype(float)
    X = np.column_stack([market, acad, skills, proj, exp, cert, resume])
    p = 1 / (1 + np.exp(-6.0 * (X @ _SYNTHETIC_WEIGHTS - 0.5)))
    df = pd.DataFrame(X.round(3), columns=FEATURES)
    df["placed"] = (rng.random(n) < p).astype(int)
    return df


class ReadinessModel:
    def __init__(self, pipeline: Pipeline, meta: dict) -> None:
        self.pipeline = pipeline
        self.meta = meta

    def predict(self, parts: dict) -> float:
        x = np.array([[float(parts[f]) for f in FEATURES]])
        return float(self.pipeline.predict_proba(x)[0, 1])


def train(csv_path: Path = CSV_PATH, model_path: Path = MODEL_PATH) -> ReadinessModel:
    df = pd.read_csv(csv_path)
    missing = [c for c in [*FEATURES, "placed"] if c not in df.columns]
    if missing:
        raise ValueError(f"{csv_path} is missing columns: {', '.join(missing)}")
    df = df.dropna(subset=[*FEATURES, "placed"])
    X, y = df[FEATURES].to_numpy(dtype=float), df["placed"].to_numpy(dtype=int)
    if len(np.unique(y)) < 2 or len(df) < 30:
        raise ValueError("Need at least 30 rows with both placed and unplaced students to train.")
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    pipeline = Pipeline([("scale", StandardScaler()), ("clf", LogisticRegression(max_iter=1000))])
    pipeline.fit(X_tr, y_tr)
    proba = pipeline.predict_proba(X_te)[:, 1]
    meta = {
        "algorithm": "Logistic regression (scikit-learn)",
        "rows": int(len(df)),
        "accuracy": round(float(accuracy_score(y_te, proba >= 0.5)), 3),
        "auc": round(float(roc_auc_score(y_te, proba)), 3),
        "synthetic": SYNTHETIC_FLAG.exists() and Path(csv_path).resolve() == CSV_PATH.resolve(),
        "source": str(Path(csv_path).name),
        "trainedOn": date.today().isoformat(),
        "coefficients": {f: round(float(c), 3) for f, c in zip(FEATURES, pipeline.named_steps["clf"].coef_[0])},
    }
    pipeline.fit(X, y)                                            # final fit on every row
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": pipeline, "meta": meta}, model_path)
    return ReadinessModel(pipeline, meta)


def load_or_train() -> ReadinessModel:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not CSV_PATH.exists():
        synthetic_history().to_csv(CSV_PATH, index=False)
        SYNTHETIC_FLAG.write_text("placement_history.csv was generated by readiness_model.synthetic_history(). Delete this file after replacing the CSV with real records.\n")
    if MODEL_PATH.exists() and MODEL_PATH.stat().st_mtime >= CSV_PATH.stat().st_mtime:
        try:
            saved = joblib.load(MODEL_PATH)
            return ReadinessModel(saved["pipeline"], saved["meta"])
        except Exception:
            pass                                                   # e.g. saved by a different scikit-learn version
    return train()


if __name__ == "__main__":
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) > 1:
        source = Path(sys.argv[1])
    else:
        if not CSV_PATH.exists():
            load_or_train()
        source = CSV_PATH
    model = train(source)
    print("Trained readiness model")
    for key, value in model.meta.items():
        print(f"  {key}: {value}")
