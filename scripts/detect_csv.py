from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from netguard_ai.detector import detect_anomalies, row_to_description
from netguard_ai.rag import get_retriever


def main() -> None:
    parser = argparse.ArgumentParser(description="Run NetGuard AI anomaly detection against a CSV.")
    parser.add_argument("--csv", type=Path, default=Path("fake_logs.csv"))
    parser.add_argument("--threshold", type=float, default=70.0)
    parser.add_argument("--max-incidents", type=int, default=20)
    args = parser.parse_args()

    flagged = detect_anomalies(args.csv, threshold=args.threshold).head(args.max_incidents)
    retriever = get_retriever()
    incidents = []

    for _, row in flagged.iterrows():
        description = row_to_description(row)
        match = retriever.search(description)
        incidents.append(
            {
                "anomaly_score": float(row["anomaly_score"]),
                "row_details": row.drop(labels=["model_prediction"], errors="ignore").to_dict(),
                "matched_incident": match.incident_type,
                "remediation": match.resolution,
            }
        )

    print(json.dumps({"incident_count": len(incidents), "incidents": incidents}, indent=2, default=str))


if __name__ == "__main__":
    main()
