"""Embedding providers. All providers return 1024-dimensional unit-length vectors."""

from __future__ import annotations

import hashlib
import math
import re
import time
from abc import ABC, abstractmethod

import httpx

from .config import get_settings
from .util import with_retries

DIM = 1024


class Embedder(ABC):
    name: str

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def embed_query(self, text: str) -> list[float]: ...


class CohereEmbedder(Embedder):
    """Cohere multilingual embeddings (1024 dimensions, English and French)."""

    URL = "https://api.cohere.com/v2/embed"
    BATCH = 96

    def __init__(self, api_key: str, model: str = "embed-multilingual-v3.0") -> None:
        if not api_key:
            raise RuntimeError("COHERE_API_KEY is not set")
        self.api_key = api_key
        self.model = model
        self.name = f"cohere:{model}"

    def _call(self, texts: list[str], input_type: str) -> list[list[float]]:
        payload = {
            "model": self.model,
            "texts": texts,
            "input_type": input_type,
            "embedding_types": ["float"],
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        for attempt in range(6):
            response = with_retries(lambda: httpx.post(self.URL, json=payload, headers=headers, timeout=60))
            if response.status_code == 429 or response.status_code >= 500:
                time.sleep(min(2 ** attempt * 2, 30))
                continue
            response.raise_for_status()
            return response.json()["embeddings"]["float"]
        raise RuntimeError("Embedding service unavailable after repeated retries")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.BATCH):
            out.extend(self._call(texts[i:i + self.BATCH], "search_document"))
        return out

    def embed_query(self, text: str) -> list[float]:
        return self._call([text], "search_query")[0]


class FastEmbedEmbedder(Embedder):
    """Local multilingual-e5-large through ONNX (no API key; about 2 GB download)."""

    def __init__(self, model: str = "intfloat/multilingual-e5-large") -> None:
        from fastembed import TextEmbedding  # imported lazily: optional dependency

        self._model = TextEmbedding(model_name=model)
        self.name = f"fastembed:{model}"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [list(map(float, v)) for v in self._model.embed([f"passage: {t}" for t in texts])]

    def embed_query(self, text: str) -> list[float]:
        return [float(x) for x in next(iter(self._model.embed([f"query: {text}"])))]


class HashEmbedder(Embedder):
    """Deterministic bag-of-words hashing. Used by automated tests only; not a semantic model."""

    name = "hash:v1"

    @staticmethod
    def _vector(text: str) -> list[float]:
        vec = [0.0] * DIM
        tokens = re.findall(r"\w+", text.lower())
        grams = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:], strict=False)]
        for token in grams:
            digest = hashlib.md5(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "little") % DIM
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[index] += sign
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


_cached: Embedder | None = None


def get_embedder() -> Embedder:
    global _cached
    if _cached is not None:
        return _cached
    s = get_settings()
    provider = s.embedding_provider.lower()
    if provider == "cohere":
        _cached = CohereEmbedder(s.cohere_api_key, s.embedding_model or "embed-multilingual-v3.0")
    elif provider == "fastembed":
        _cached = FastEmbedEmbedder(s.embedding_model or "intfloat/multilingual-e5-large")
    elif provider == "hash":
        _cached = HashEmbedder()
    else:
        raise RuntimeError(f"Unknown EMBEDDING_PROVIDER: {s.embedding_provider}")
    return _cached
