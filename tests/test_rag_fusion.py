import pytest

from app.retrieval.pipeline import RAGFusionPipeline, RetrieverConfig
from app.retrieval.query_expansion import (
    KeywordSynonymExpansionStrategy,
    LLMQueryExpansionStrategy,
    QueryContext,
    QueryExpander,
)
from app.retrieval.rrf import ScoredDocument, reciprocal_rank_fusion
from app.retrieval.types import RetrievalResult


class DummyRetriever:
    def __init__(self, mapping):
        self.mapping = mapping

    async def retrieve(self, query: str, *, top_k: int):
        return self.mapping.get(query, [])[:top_k]


@pytest.mark.asyncio
async def test_query_expander_combines_and_limits():
    keyword = KeywordSynonymExpansionStrategy({"öğrenci": ["student", "öğrenciler"]})

    async def generator(query: str, context):
        return [f"{query} detayları", "öğrenci bursları"]

    expander = QueryExpander(
        strategies=[
            keyword,
            LLMQueryExpansionStrategy(generator, max_suggestions=2),
        ],
        max_expansions=3,
        include_original=False,
    )

    expansions = await expander.expand("öğrenci burs", QueryContext(language="tr"))
    assert len(expansions) == 3
    assert all(expansion != "öğrenci burs" for expansion in expansions)


def test_rrf_prioritises_documents_with_better_ranks():
    list_a = [
        ScoredDocument("doc-1", score=0.1, metadata={"source": "dense"}),
        ScoredDocument("doc-2", score=0.05, metadata={"source": "dense"}),
    ]
    list_b = [
        ScoredDocument("doc-2", score=0.2, metadata={"source": "sparse"}),
        ScoredDocument("doc-3", score=0.15, metadata={"source": "sparse"}),
    ]

    fused = reciprocal_rank_fusion([list_a, list_b], k=50)
    assert [doc.document_id for doc in fused[:2]] == ["doc-2", "doc-1"]
    assert any("sparse" in contrib.metadata.get("source", "") for contrib in fused[0].contributions)


@pytest.mark.asyncio
async def test_rag_fusion_pipeline_aggregates_retrievers():
    dense_results = {
        "öğrenci burs": [
            RetrievalResult("doc-1", 0.9, {"source": "dense"}),
            RetrievalResult("doc-2", 0.8, {"source": "dense"}),
        ],
        "öğrenci burs detayları": [RetrievalResult("doc-3", 0.85, {"source": "dense"})],
    }

    sparse_results = {
        "öğrenci burs": [RetrievalResult("doc-2", 0.7, {"source": "sparse"})],
        "öğrenci burs detayları": [RetrievalResult("doc-4", 0.65, {"source": "sparse"})],
    }

    expander = QueryExpander(
        strategies=[
            KeywordSynonymExpansionStrategy({}),
            LLMQueryExpansionStrategy(lambda q, _: [f"{q} detayları"], max_suggestions=1),
        ],
        max_expansions=2,
    )

    pipeline = RAGFusionPipeline(
        query_expander=expander,
        retrievers=[
            RetrieverConfig(name="dense", retriever=DummyRetriever(dense_results), weight=1.2),
            RetrieverConfig(name="sparse", retriever=DummyRetriever(sparse_results), weight=1.0),
        ],
        per_retriever_limit=2,
    )

    fused = await pipeline.retrieve("öğrenci burs", top_k=3)
    assert fused[0].document_id == "doc-2"
    assert any(contrib.metadata["retriever"] == "dense" for contrib in fused[0].contributions)
    assert any(contrib.metadata["query_variant"].endswith("detayları") for contrib in fused)
