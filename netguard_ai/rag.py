from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np


DEFAULT_INCIDENTS_PATH = Path(__file__).resolve().parent.parent / "data" / "historical_incidents.json"
DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


@dataclass(frozen=True)
class IncidentMatch:
    incident_type: str
    description: str
    resolution: str
    similarity: float


class IncidentRetriever:
    def __init__(self, incidents_path: Path = DEFAULT_INCIDENTS_PATH, model_name: str = DEFAULT_MODEL_NAME) -> None:
        self.incidents_path = incidents_path
        self.model_name = model_name
        self.incidents = self._load_incidents()
        self.model = self._load_model()
        self.index, self.embeddings = self._build_index()

    def _load_incidents(self) -> list[dict[str, str]]:
        with self.incidents_path.open("r", encoding="utf-8") as incidents_file:
            incidents: list[dict[str, str]] = json.load(incidents_file)

        if not incidents:
            raise ValueError("Historical incident store is empty.")
        return incidents

    def _load_model(self) -> Any:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("Install sentence-transformers before running RAG retrieval.") from exc

        try:
            return SentenceTransformer(self.model_name)
        except Exception as exc:
            raise RuntimeError(
                f"Unable to load embedding model '{self.model_name}'. "
                "Check internet access for the first download or verify the model exists in the local cache."
            ) from exc

    def _embed(self, texts: list[str]) -> np.ndarray:
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return np.asarray(embeddings, dtype="float32")

    def _build_index(self) -> tuple[Any, np.ndarray]:
        try:
            import faiss
        except ImportError as exc:
            raise RuntimeError("Install faiss-cpu before running RAG retrieval.") from exc

        descriptions = [incident["description"] for incident in self.incidents]
        embeddings = self._embed(descriptions)
        index = faiss.IndexFlatIP(embeddings.shape[1])
        index.add(embeddings)
        return index, embeddings

    def search(self, anomaly_description: str) -> IncidentMatch:
        query_embedding = self._embed([anomaly_description])
        similarities, indices = self.index.search(query_embedding, 1)

        incident = self.incidents[int(indices[0][0])]
        return IncidentMatch(
            incident_type=incident["incident_type"],
            description=incident["description"],
            resolution=incident["resolution"],
            similarity=round(float(similarities[0][0]), 4),
        )


@lru_cache(maxsize=1)
def get_retriever() -> IncidentRetriever:
    return IncidentRetriever()
