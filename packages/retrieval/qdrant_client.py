"""Helper utilities for interacting with Qdrant."""
from __future__ import annotations

import asyncio
from typing import Any, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator
from qdrant_client import QdrantClient

try:  # pragma: no cover - fallback when qdrant_client stubs are used in tests
    from qdrant_client.http.models import CollectionInfo, Distance, VectorParams
except Exception:  # pragma: no cover - minimal fallback for test doubles
    from dataclasses import dataclass
    from enum import Enum

    class Distance(str, Enum):  # type: ignore[no-redef]
        COSINE = "Cosine"
        EUCLID = "Euclid"
        DOT = "Dot"
        MANHATTAN = "Manhattan"

    @dataclass
    class VectorParams:  # type: ignore[no-redef]
        size: int
        distance: str | Distance

    CollectionInfo = Any  # type: ignore[assignment]


class EmbeddingVector(BaseModel):
    """Validated embedding vector container."""

    model_config = ConfigDict(extra="forbid")

    values: list[float] = Field(..., min_length=1)

    @field_validator("values", mode="before")
    @classmethod
    def _coerce_values(cls, value: Any) -> list[float]:
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            try:
                return [float(item) for item in value]
            except (TypeError, ValueError) as exc:  # pragma: no cover - defensive guard
                raise ValueError("Embedding vector must contain numeric values") from exc
        raise TypeError("Embedding vector must be a sequence of floats")


class EmbeddedDocument(BaseModel):
    """Structured representation of an embedded document."""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(..., min_length=1)
    embedding: EmbeddingVector
    metadata: Mapping[str, Any] | None = None

    @property
    def vector(self) -> list[float]:
        """Return the validated embedding values as a list of floats."""

        return list(self.embedding.values)

    def payload(self) -> Mapping[str, Any]:
        """Return normalized payload metadata."""

        return dict(self.metadata or {})


class QdrantCollectionConfig(BaseModel):
    """Configuration options used when creating/validating collections."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    vector_size: PositiveInt = Field(..., description="Embedding dimensionality")
    distance: Distance = Field(default=Distance.COSINE)
    on_disk_payload: bool = Field(default=True)
    shard_number: PositiveInt | None = Field(default=None)
    replication_factor: PositiveInt | None = Field(default=None)
    write_consistency_factor: PositiveInt | None = Field(default=None)

    @field_validator("distance", mode="before")
    @classmethod
    def _normalize_distance(cls, value: Any) -> Distance:
        if isinstance(value, Distance):
            return value
        if isinstance(value, str):
            key = value.upper()
            try:
                return Distance[key]
            except KeyError as exc:  # pragma: no cover - validation guard
                raise ValueError(
                    f"Unsupported distance metric '{value}'. Expected one of: {', '.join(Distance.__members__.keys())}"
                ) from exc
        raise TypeError("Distance must be provided as a Distance enum value or string name")


def _coerce_vector_params(value: Any) -> VectorParams:
    if isinstance(value, VectorParams):
        return value
    model_validate = getattr(VectorParams, "model_validate", None)
    if callable(model_validate):  # pragma: no branch - depends on real qdrant client
        return model_validate(value)
    if isinstance(value, Mapping):
        return VectorParams(**value)
    return VectorParams(**{k: getattr(value, k) for k in ("size", "distance")})


def _extract_vector_params(info: CollectionInfo) -> VectorParams:
    """Return the vector configuration from a collection response."""

    vectors_config = info.config.params.vectors
    if isinstance(vectors_config, dict):
        if len(vectors_config) != 1:
            raise ValueError("Collections with multiple vector configurations are not supported")
        vector_params = next(iter(vectors_config.values()))
        return _coerce_vector_params(vector_params)
    return _coerce_vector_params(vectors_config)


def _assert_collection_compatible(info: CollectionInfo, config: QdrantCollectionConfig) -> None:
    vector_params = _extract_vector_params(info)
    distance = Distance(vector_params.distance)
    if vector_params.size != config.vector_size:
        raise ValueError(
            f"Existing collection '{config.name}' has vector size {vector_params.size}, expected {config.vector_size}."
        )
    if distance is not config.distance:
        raise ValueError(
            f"Existing collection '{config.name}' uses distance {distance.name}, expected {config.distance.name}."
        )


def _build_create_kwargs(config: QdrantCollectionConfig) -> dict[str, Any]:
    params: dict[str, Any] = {
        "collection_name": config.name,
        "vectors_config": VectorParams(size=config.vector_size, distance=config.distance),
        "on_disk_payload": config.on_disk_payload,
    }
    if config.shard_number is not None:
        params["shard_number"] = config.shard_number
    if config.replication_factor is not None:
        params["replication_factor"] = config.replication_factor
    if config.write_consistency_factor is not None:
        params["write_consistency_factor"] = config.write_consistency_factor
    return params


def ensure_collection(client: QdrantClient, config: QdrantCollectionConfig) -> None:
    """Ensure the configured collection exists with the expected parameters."""

    if not client.collection_exists(config.name):
        client.create_collection(**_build_create_kwargs(config))
        return

    info = client.get_collection(config.name)
    _assert_collection_compatible(info, config)


async def ensure_collection_async(client: QdrantClient, config: QdrantCollectionConfig) -> None:
    """Async wrapper around :func:`ensure_collection` for use inside async code."""

    await asyncio.to_thread(ensure_collection, client, config)


def validate_embedding_vector(values: Sequence[float], *, expected_size: int | None = None) -> list[float]:
    """Validate an embedding vector and optionally enforce its dimensionality."""

    model = EmbeddingVector(values=values)
    if expected_size is not None and len(model.values) != expected_size:
        raise ValueError(
            f"Embedding dimension mismatch: expected {expected_size}, received {len(model.values)} values."
        )
    return model.values


def validate_embedded_document(
    document_id: str,
    embedding: Sequence[float],
    *,
    metadata: Mapping[str, Any] | None = None,
    expected_size: int | None = None,
) -> EmbeddedDocument:
    """Construct an :class:`EmbeddedDocument` after validating the embedding payload."""

    vector = validate_embedding_vector(embedding, expected_size=expected_size)
    return EmbeddedDocument(document_id=document_id, embedding=EmbeddingVector(values=vector), metadata=metadata)
