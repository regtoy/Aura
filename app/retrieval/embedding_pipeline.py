from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from .types import RetrievalResult


@dataclass(slots=True)
class SentencePair:
    """Training example used during embedding fine-tuning."""

    text_a: str
    text_b: str
    score: float


@dataclass(slots=True)
class EmbeddingPipelineConfig:
    """Configuration for the embedding fine-tuning pipeline."""

    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    batch_size: int = 16
    epochs: int = 1
    learning_rate: float = 2e-5
    warmup_ratio: float = 0.1
    device: str | None = None


class EmbeddingPipeline:
    """End-to-end embedding pipeline with optional fine-tuning support."""

    def __init__(
        self,
        config: EmbeddingPipelineConfig | None = None,
        *,
        model_factory: Callable[[str, str | None], object] | None = None,
    ) -> None:
        self.config = config or EmbeddingPipelineConfig()
        self._model = None
        self._model_factory = model_factory

    def _ensure_model(self) -> object:
        if self._model is not None:
            return self._model

        if self._model_factory is not None:
            self._model = self._model_factory(self.config.model_name, self.config.device)
            return self._model

        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on optional dependency
            raise RuntimeError(
                "sentence-transformers is not installed. Provide a model_factory or install the dependency."
            ) from exc

        self._model = SentenceTransformer(self.config.model_name, device=self.config.device)
        return self._model

    def encode(self, texts: Sequence[str], *, normalize: bool = True) -> Sequence[Sequence[float]]:
        model = self._ensure_model()
        encode = getattr(model, "encode", None)
        if encode is None:
            raise RuntimeError("Model does not expose an encode method")

        return encode(texts, normalize_embeddings=normalize)

    def train(self, examples: Iterable[SentencePair], *, output_path: str | None = None) -> None:
        """Fine-tune the embedding model on similarity-labelled sentence pairs."""

        model = self._ensure_model()
        fit = getattr(model, "fit", None)
        if fit is None:
            raise RuntimeError("Model does not support fine-tuning via fit().")

        try:
            from sentence_transformers import losses
            from sentence_transformers.readers import InputExample
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "sentence-transformers training components are missing. Install sentence-transformers to fine-tune."
            ) from exc

        dataset = [InputExample(texts=[item.text_a, item.text_b], label=float(item.score)) for item in examples]
        if not dataset:
            raise ValueError("At least one training example is required for fine-tuning.")

        try:
            from torch.utils.data import DataLoader
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("torch is required to fine-tune sentence-transformers models.") from exc

        dataloader = DataLoader(dataset, shuffle=True, batch_size=self.config.batch_size)
        loss = losses.CosineSimilarityLoss(model)

        steps_per_epoch = max(len(dataloader), 1)
        warmup_steps = max(int(steps_per_epoch * self.config.epochs * self.config.warmup_ratio), 0)
        optimizer_params = {"lr": self.config.learning_rate}

        fit(
            train_objectives=[(dataloader, loss)],
            epochs=self.config.epochs,
            warmup_steps=warmup_steps,
            optimizer_params=optimizer_params,
            use_amp=True,
        )

        if output_path is not None:
            save = getattr(model, "save", None)
            if save is None:
                raise RuntimeError("Model does not support saving.")
            save(output_path)

    def to_retrieval_result(self, document_id: str, embedding: Sequence[float]) -> RetrievalResult:
        """Utility helper to wrap embeddings inside a RetrievalResult."""

        return RetrievalResult(document_id=document_id, score=1.0, metadata={"embedding": list(embedding)})
