from app.tickets.pipeline import TicketEmbeddingPipeline, normalize_ticket_text


class DummyEmbedder:
    def __init__(self):
        self.calls: list[tuple[tuple[str, ...], bool]] = []

    def encode(self, texts, **kwargs):
        normalize = kwargs.get("normalize")
        if normalize is None:
            normalize = kwargs.get("normalize_embeddings", True)
        self.calls.append((tuple(texts), normalize))
        return [[0.1, 0.2, 0.3] for _ in texts]


def test_normalize_ticket_text_cleans_input():
    assert normalize_ticket_text("  Merhaba\nDÜNYA!  ") == "merhaba dünya!"


def test_ticket_embedding_pipeline_runs_encode_on_normalized_text():
    embedder = DummyEmbedder()
    pipeline = TicketEmbeddingPipeline(embedder=embedder)

    result = pipeline.run("  Merhaba\nDÜNYA!  ")

    assert embedder.calls == [(("merhaba dünya!",), True)]
    assert result.normalized_text == "merhaba dünya!"
    assert result.embedding == [0.1, 0.2, 0.3]


def test_ticket_embedding_pipeline_handles_empty_text():
    embedder = DummyEmbedder()
    pipeline = TicketEmbeddingPipeline(embedder=embedder)

    result = pipeline.run("   \n  ")

    assert result.normalized_text == ""
    assert result.embedding == []
    assert embedder.calls == []
