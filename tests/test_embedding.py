"""
Clarion — Unit tests for embedding service
Mock SentenceTransformer để không load model thật khi chạy CI.
"""
import importlib
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# ─── helpers ────────────────────────────────────────────────────

DIM = 1024  # BAAI/bge-m3 output dimension

def _make_mock_model(dim: int = DIM):
    """Tạo mock SentenceTransformer trả về vector đã normalize."""
    mock = MagicMock()
    mock.get_sentence_embedding_dimension.return_value = dim

    def fake_encode(texts, **kwargs):
        n = len(texts)
        raw = np.random.rand(n, dim).astype("float32")
        # L2-normalize như model thật khi normalize_embeddings=True
        norms = np.linalg.norm(raw, axis=1, keepdims=True)
        return raw / norms

    mock.encode.side_effect = fake_encode
    return mock


# ─── fixtures ───────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset _model singleton trước mỗi test để tránh state leak."""
    import app.services.embedding as emb_mod
    emb_mod._model = None
    yield
    emb_mod._model = None


# ─── embed_batch ────────────────────────────────────────────────

def test_embed_batch_returns_correct_shape():
    mock_model = _make_mock_model()
    with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
        import app.services.embedding as emb
        importlib.reload(emb)
        emb._model = None

        texts = ["AC1: user can login", "AC2: user can logout"]
        result = emb.embed_batch(texts)

    assert len(result) == 2
    assert len(result[0]) == DIM
    assert len(result[1]) == DIM


def test_embed_batch_vectors_are_normalized():
    """Dot product của vector normalized với chính nó phải gần bằng 1.0."""
    mock_model = _make_mock_model()
    with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
        import app.services.embedding as emb
        importlib.reload(emb)
        emb._model = None

        result = emb.embed_batch(["some text"])

    vec = np.array(result[0])
    norm = float(np.dot(vec, vec))
    assert abs(norm - 1.0) < 1e-5, f"Vector không được normalize, norm²={norm}"


def test_embed_batch_raises_on_empty_list():
    import app.services.embedding as emb
    with pytest.raises(ValueError, match="rỗng"):
        emb.embed_batch([])


def test_embed_batch_raises_on_empty_string():
    import app.services.embedding as emb
    with pytest.raises(ValueError, match="chuỗi rỗng"):
        emb.embed_batch(["valid text", ""])


def test_embed_batch_order_preserved():
    """Thứ tự output phải khớp với thứ tự input."""
    mock_model = _make_mock_model()
    # Trả về vector khác nhau cho từng input
    call_count = [0]

    def ordered_encode(texts, **kwargs):
        n = len(texts)
        # Tạo vector deterministic theo index
        vecs = np.zeros((n, DIM), dtype="float32")
        for i in range(n):
            vecs[i, 0] = float(i + 1)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        return vecs / norms

    mock_model.encode.side_effect = ordered_encode

    with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
        import app.services.embedding as emb
        importlib.reload(emb)
        emb._model = None

        texts = ["first", "second", "third"]
        result = emb.embed_batch(texts)

    # vec[i][0] tỉ lệ thuận với index → kiểm tra thứ tự
    assert result[0][0] < result[1][0] < result[2][0]


# ─── embed_single ────────────────────────────────────────────────

def test_embed_single_returns_flat_vector():
    mock_model = _make_mock_model()
    with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
        import app.services.embedding as emb
        importlib.reload(emb)
        emb._model = None

        result = emb.embed_single("hello world")

    assert isinstance(result, list)
    assert len(result) == DIM


def test_embed_single_raises_on_empty():
    import app.services.embedding as emb
    with pytest.raises(ValueError, match="rỗng"):
        emb.embed_single("")

    with pytest.raises(ValueError, match="rỗng"):
        emb.embed_single("   ")


# ─── get_embedding_dim ───────────────────────────────────────────

def test_get_embedding_dim():
    mock_model = _make_mock_model(dim=1024)
    with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
        import app.services.embedding as emb
        importlib.reload(emb)
        emb._model = None

        assert emb.get_embedding_dim() == 1024
