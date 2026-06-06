from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from netguard_ai.detector import detect_anomalies, row_to_description
from netguard_ai.rag import get_retriever


app = FastAPI(
    title="NetGuard AI",
    description="Network anomaly detection and RAG-based incident response API.",
    version="1.0.0",
)


class DetectRequest(BaseModel):
    run_detection: bool = Field(default=True)
    csv_path: str = Field(default="fake_logs.csv", description="Path to a NetFlow-style CSV file.")
    threshold: float = Field(default=70.0, ge=0.0, le=100.0)
    contamination: float = Field(default=0.08, gt=0.0, lt=0.5)
    max_incidents: int = Field(default=20, ge=1, le=100)


class HealthResponse(BaseModel):
    status: str


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/detect")
def detect(request: DetectRequest) -> dict[str, Any]:
    if not request.run_detection:
        return {"flagged_count": 0, "incident_count": 0, "incidents": []}

    try:
        flagged = detect_anomalies(
            csv_path=Path(request.csv_path),
            threshold=request.threshold,
            contamination=request.contamination,
        ).head(request.max_incidents)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if flagged.empty:
        return {
            "flagged_count": 0,
            "threshold": request.threshold,
            "incident_count": 0,
            "incidents": [],
        }

    try:
        retriever = get_retriever()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    incidents: list[dict[str, Any]] = []

    for _, row in flagged.iterrows():
        description = row_to_description(row)
        match = retriever.search(description)
        row_details = row.drop(labels=["model_prediction"], errors="ignore").to_dict()

        incidents.append(
            {
                "timestamp": row_details.get("timestamp"),
                "src_ip": row_details.get("src_ip"),
                "dst_ip": row_details.get("dst_ip"),
                "port": int(row_details.get("port")),
                "protocol": row_details.get("protocol"),
                "bytes_sent": int(row_details.get("bytes_sent")),
                "duration": float(row_details.get("duration")),
                "packets": int(row_details.get("packets")),
                "anomaly_score": float(row["anomaly_score"]),
                "row_details": row_details,
                "anomaly_description": description,
                "matched_incident": match.incident_type,
                "remediation": match.resolution,
                "matched_incident_details": {
                    "incident_type": match.incident_type,
                    "description": match.description,
                    "similarity": match.similarity,
                },
            }
        )

    return {
        "flagged_count": len(incidents),
        "threshold": request.threshold,
        "incident_count": len(incidents),
        "incidents": incidents,
    }
