"""Retrieval utilities for the Aura project."""

from .embedding_pipeline import (
    EmbeddingPipeline,
    EmbeddingPipelineConfig,
    SentencePair,
)
from .pipeline import RAGFusionPipeline
from .query_expansion import (
    KeywordSynonymExpansionStrategy,
    build_default_synonym_strategy,
    LLMQueryExpansionStrategy,
    QueryContext,
    QueryExpander,
    QueryExpansionStrategy,
)
from .rrf import FusedDocument, ScoredDocument, reciprocal_rank_fusion
from .types import RetrievalResult

__all__ = [
    "EmbeddingPipeline",
    "EmbeddingPipelineConfig",
    "FusedDocument",
    "KeywordSynonymExpansionStrategy",
    "build_default_synonym_strategy",
    "LLMQueryExpansionStrategy",
    "QueryContext",
    "QueryExpander",
    "QueryExpansionStrategy",
    "RAGFusionPipeline",
    "RetrievalResult",
    "ScoredDocument",
    "SentencePair",
    "reciprocal_rank_fusion",
]
