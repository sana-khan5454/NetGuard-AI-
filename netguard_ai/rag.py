from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np


DEFAULT_INCIDENTS_PATH = Path(__file__).resolve().parent.parent / "data" / "historical_incidents.json"
DEFAULT_VECTOR_STORE_DIR = Path(__file__).resolve().parent.parent / "vector_store"
DEFAULT_INDEX_PATH = DEFAULT_VECTOR_STORE_DIR / "faiss_index.bin"
DEFAULT_MAP_PATH = DEFAULT_VECTOR_STORE_DIR / "incidents_map.json"
DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


@dataclass(frozen=True)
class IncidentMatch:
    incident_type: str
    description: str
    resolution: str
    similarity: float


class IncidentRetriever:
    def __init__(
        self,
        incidents_path: Path = DEFAULT_INCIDENTS_PATH,
        model_name: str = DEFAULT_MODEL_NAME,
        index_path: Path = DEFAULT_INDEX_PATH,
        map_path: Path = DEFAULT_MAP_PATH,
    ) -> None:
        self.incidents_path = incidents_path
        self.model_name = model_name
        self.index_path = index_path
        self.map_path = map_path
        self.model = self._load_model()
        if not self.index_path.exists() or not self.map_path.exists():
            build_vector_store(self.incidents_path, self.index_path, self.map_path, self.model)
        self.index, self.incidents_map = self._load_vector_store()

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
            if self.index_path.exists() and self.map_path.exists():
                return SentenceTransformer(self.model_name, local_files_only=True)
            return SentenceTransformer(self.model_name)
        except Exception as exc:
            raise RuntimeError(
                f"Unable to load embedding model '{self.model_name}'. "
                "Check internet access for the first download or verify the model exists in the local cache."
            ) from exc

    def _embed(self, texts: list[str]) -> np.ndarray:
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return np.asarray(embeddings, dtype="float32")

    def _load_vector_store(self) -> tuple[Any, dict[str, dict[str, str]]]:
        try:
            import faiss
        except ImportError as exc:
            raise RuntimeError("Install faiss-cpu before running RAG retrieval.") from exc

        index = faiss.read_index(str(self.index_path))
        with self.map_path.open("r", encoding="utf-8") as map_file:
            incidents_map: dict[str, dict[str, str]] = json.load(map_file)
        return index, incidents_map

    def search(self, anomaly_description: str) -> IncidentMatch:
        query_embedding = self._embed([anomaly_description])
        distances, indices = self.index.search(query_embedding, 1)

        incident = self.incidents_map[str(int(indices[0][0]))]
        return IncidentMatch(
            incident_type=incident["incident_type"],
            description=incident["description"],
            resolution=incident["resolution"],
            similarity=round(1.0 / (1.0 + float(distances[0][0])), 4),
        )


def build_vector_store(
    incidents_path: Path = DEFAULT_INCIDENTS_PATH,
    index_path: Path = DEFAULT_INDEX_PATH,
    map_path: Path = DEFAULT_MAP_PATH,
    model: Any | None = None,
    model_name: str = DEFAULT_MODEL_NAME,
) -> tuple[Path, Path]:
    print("Loading historical incidents...", end=" ")
    with incidents_path.open("r", encoding="utf-8") as incidents_file:
        incidents: list[dict[str, str]] = json.load(incidents_file)
    print(f"{len(incidents)} incidents found")

    if not incidents:
        raise ValueError("Historical incident store is empty.")

    if model is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("Install sentence-transformers before building the FAISS index.") from exc
        model = SentenceTransformer(model_name)

    print("Embedding descriptions using all-MiniLM-L6-v2...")
    descriptions = [incident["description"] for incident in incidents]
    embeddings = np.asarray(model.encode(descriptions), dtype="float32")
    print(f"Embedding complete. Shape: {embeddings.shape}")

    try:
        import faiss
    except ImportError as exc:
        raise RuntimeError("Install faiss-cpu before building the FAISS index.") from exc

    print("Building FAISS index...")
    index = faiss.IndexFlatL2(embeddings.shape[1])
    index.add(embeddings)
    print(f"Index built. Total vectors: {index.ntotal}")

    index_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Saving {index_path.name}...")
    faiss.write_index(index, str(index_path))

    print(f"Saving {map_path.name}...")
    incidents_map = {str(position): incident for position, incident in enumerate(incidents)}
    with map_path.open("w", encoding="utf-8") as map_file:
        json.dump(incidents_map, map_file, indent=2)

    print("Done. Index ready.")
    return index_path, map_path


@lru_cache(maxsize=1)
def get_retriever() -> IncidentRetriever:
    return IncidentRetriever()
