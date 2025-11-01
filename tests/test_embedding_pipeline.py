import sys
import types

import pytest

from apps.api.retrieval.embedding_pipeline import EmbeddingPipeline, EmbeddingPipelineConfig, SentencePair


class DummyModel:
    def __init__(self):
        self.encoded_inputs = []
        self.fit_calls = []
        self.saved_paths = []

    def encode(self, texts, normalize_embeddings=True):
        self.encoded_inputs.append((tuple(texts), normalize_embeddings))
        return [[float(len(text))] for text in texts]

    def fit(self, train_objectives, epochs, warmup_steps, optimizer_params, use_amp):
        self.fit_calls.append(
            {
                "train_objectives": train_objectives,
                "epochs": epochs,
                "warmup_steps": warmup_steps,
                "optimizer_params": optimizer_params,
                "use_amp": use_amp,
            }
        )

    def save(self, path):
        self.saved_paths.append(path)


class FakeDataLoader(list):
    def __init__(self, dataset, shuffle, batch_size):
        super().__init__([dataset])
        self._dataset = dataset
        self.shuffle = shuffle
        self.batch_size = batch_size

    def __len__(self):
        step = max(self.batch_size, 1)
        return max((len(self._dataset) + step - 1) // step, 1)


class FakeLoss:
    def __init__(self, model):
        self.model = model


class FakeInputExample:
    def __init__(self, texts, label):
        self.texts = texts
        self.label = label


@pytest.fixture(autouse=True)
def setup_sentence_transformers(monkeypatch):
    module = types.ModuleType("sentence_transformers")
    losses_module = types.ModuleType("sentence_transformers.losses")
    losses_module.CosineSimilarityLoss = FakeLoss
    readers_module = types.ModuleType("sentence_transformers.readers")
    readers_module.InputExample = FakeInputExample

    module.losses = losses_module
    module.readers = readers_module

    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    monkeypatch.setitem(sys.modules, "sentence_transformers.losses", losses_module)
    monkeypatch.setitem(sys.modules, "sentence_transformers.readers", readers_module)

    data_module = types.ModuleType("torch.utils.data")
    data_module.DataLoader = FakeDataLoader
    torch_module = types.ModuleType("torch")
    torch_module.utils = types.SimpleNamespace(data=data_module)

    monkeypatch.setitem(sys.modules, "torch", torch_module)
    monkeypatch.setitem(sys.modules, "torch.utils", types.SimpleNamespace(data=data_module))
    monkeypatch.setitem(sys.modules, "torch.utils.data", data_module)


def test_embedding_pipeline_encode_and_to_result():
    model = DummyModel()
    pipeline = EmbeddingPipeline(model_factory=lambda *_: model)
    vectors = pipeline.encode(["hello", "world"], normalize=False)
    assert vectors == [[5.0], [5.0]]
    assert model.encoded_inputs[0][1] is False

    result = pipeline.to_retrieval_result("doc-1", vectors[0])
    assert result.metadata["embedding"] == [5.0]


def test_embedding_pipeline_train(monkeypatch):
    model = DummyModel()
    pipeline = EmbeddingPipeline(
        EmbeddingPipelineConfig(batch_size=2, epochs=2, warmup_ratio=0.5, learning_rate=1e-5),
        model_factory=lambda *_: model,
    )

    dataset = [SentencePair("a", "b", 0.9), SentencePair("c", "d", 0.8)]
    pipeline.train(dataset, output_path="/tmp/model")

    assert model.fit_calls
    assert model.saved_paths == ["/tmp/model"]
