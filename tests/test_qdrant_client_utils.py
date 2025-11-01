from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from packages.retrieval.qdrant_client import (
    EmbeddedDocument,
    EmbeddingVector,
    Distance,
    QdrantCollectionConfig,
    ensure_collection,
    ensure_collection_async,
    VectorParams,
    validate_embedded_document,
    validate_embedding_vector,
)


class _CollectionParams(SimpleNamespace):
    pass


class _CollectionConfig(SimpleNamespace):
    pass


@pytest.mark.parametrize("distance", [Distance.COSINE, "cosine"])
def test_collection_created_when_missing(distance):
    client = MagicMock()
    client.collection_exists.return_value = False
    config = QdrantCollectionConfig(
        name="tickets",
        vector_size=3,
        distance=distance,
        on_disk_payload=True,
    )

    ensure_collection(client, config)

    assert client.create_collection.call_count == 1
    kwargs = client.create_collection.call_args.kwargs
    assert kwargs["collection_name"] == "tickets"
    vector_params = kwargs["vectors_config"]
    assert isinstance(vector_params, VectorParams)
    assert vector_params.size == 3
    assert Distance(vector_params.distance) == Distance.COSINE
    assert kwargs["on_disk_payload"] is True


def test_collection_validation_is_performed():
    client = MagicMock()
    client.collection_exists.return_value = True
    config = QdrantCollectionConfig(name="tickets", vector_size=3, distance="cosine")
    vectors_config = VectorParams(size=3, distance=Distance.COSINE)
    info = SimpleNamespace(config=_CollectionConfig(params=_CollectionParams(vectors=vectors_config)))
    client.get_collection.return_value = info

    ensure_collection(client, config)

    client.get_collection.assert_called_once_with("tickets")


def test_collection_validation_mismatch():
    client = MagicMock()
    client.collection_exists.return_value = True
    config = QdrantCollectionConfig(name="tickets", vector_size=3, distance="cosine")
    vectors_config = VectorParams(size=8, distance=Distance.COSINE)
    info = SimpleNamespace(config=_CollectionConfig(params=_CollectionParams(vectors=vectors_config)))
    client.get_collection.return_value = info

    with pytest.raises(ValueError):
        ensure_collection(client, config)


@pytest.mark.asyncio
async def test_async_wrapper_delegates_to_sync(monkeypatch):
    client = MagicMock()
    client.collection_exists.return_value = False
    config = QdrantCollectionConfig(name="tickets", vector_size=3)

    captured = {}

    async def fake_to_thread(func, *args, **kwargs):
        captured["func"] = func
        captured["args"] = args
        captured["kwargs"] = kwargs
        return func(*args, **kwargs)

    monkeypatch.setattr("packages.retrieval.qdrant_client.asyncio.to_thread", fake_to_thread)

    await ensure_collection_async(client, config)

    assert captured["func"] is ensure_collection
    assert captured["args"] == (client, config)
    client.create_collection.assert_called_once()


def test_validate_embedding_vector_success():
    values = validate_embedding_vector([1, 2, 3], expected_size=3)
    assert values == [1.0, 2.0, 3.0]


def test_validate_embedding_vector_dimension_error():
    with pytest.raises(ValueError):
        validate_embedding_vector([1, 2], expected_size=3)


def test_validate_embedded_document(monkeypatch):
    document = validate_embedded_document("doc-1", [0, 1, 2], expected_size=3, metadata={"foo": "bar"})
    assert isinstance(document, EmbeddedDocument)
    assert isinstance(document.embedding, EmbeddingVector)
    assert document.vector == [0.0, 1.0, 2.0]
    assert document.payload() == {"foo": "bar"}
