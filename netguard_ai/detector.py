from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


NUMERIC_COLUMNS = ["port", "bytes_sent", "duration", "packets"]


def load_logs(csv_path: str | Path) -> pd.DataFrame:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Traffic log CSV not found: {path}")

    dataframe = pd.read_csv(path)
    missing = [column for column in NUMERIC_COLUMNS if column not in dataframe.columns]
    if missing:
        raise ValueError(f"CSV is missing required numeric columns: {', '.join(missing)}")

    return dataframe


def _normalize_outlier_scores(raw_scores: np.ndarray) -> np.ndarray:
    outlier_strength = -raw_scores
    minimum = float(outlier_strength.min())
    maximum = float(outlier_strength.max())

    if maximum == minimum:
        return np.zeros_like(outlier_strength)

    return ((outlier_strength - minimum) / (maximum - minimum)) * 100.0


def score_logs(dataframe: pd.DataFrame, contamination: float = 0.08, random_state: int = 42) -> pd.DataFrame:
    features = dataframe[NUMERIC_COLUMNS].copy()
    features = features.apply(pd.to_numeric, errors="coerce").fillna(0)

    scaler = StandardScaler()
    scaled_features = scaler.fit_transform(features)

    model = IsolationForest(contamination=contamination, random_state=random_state, n_estimators=150)
    model.fit(scaled_features)

    result = dataframe.copy()
    result["anomaly_score"] = _normalize_outlier_scores(model.decision_function(scaled_features)).round(2)
    result["model_prediction"] = model.predict(scaled_features)
    return result


def detect_anomalies(
    csv_path: str | Path,
    threshold: float = 70.0,
    contamination: float = 0.08,
    random_state: int = 42,
) -> pd.DataFrame:
    logs = load_logs(csv_path)
    scored = score_logs(logs, contamination=contamination, random_state=random_state)
    flagged = scored[scored["anomaly_score"] >= threshold].sort_values("anomaly_score", ascending=False)
    return flagged.reset_index(drop=True)


def row_to_description(row: pd.Series | dict[str, Any]) -> str:
    data = dict(row)
    return (
        f"Network anomaly from {data.get('src_ip')} to {data.get('dst_ip')} using "
        f"{data.get('protocol')} port {data.get('port')}. Observed {data.get('bytes_sent')} bytes, "
        f"{data.get('packets')} packets, duration {data.get('duration')} seconds, "
        f"anomaly score {data.get('anomaly_score')}."
    )

