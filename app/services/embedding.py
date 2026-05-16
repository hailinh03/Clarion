"""
Clarion — Embedding Service
Dùng BAAI/bge-m3 chạy local (không cần API key).

Rules (từ RULES.md):
  - Luôn dùng embed_batch(), không embed từng item một.
  - normalize_embeddings=True để cosine similarity luôn đúng.
  - Không bao giờ mix embedding model — chỉ 1 model cho toàn bộ hệ thống.
  - Mọi external call đều có try/except + log lỗi rõ ràng.
"""
import os
import threading
from typing import List

from loguru import logger

# ─────────────────────────────────────────────────────────────────
# Singleton — lazy-load model 1 lần, thread-safe
# ─────────────────────────────────────────────────────────────────
_model = None
_model_lock = threading.Lock()


def _get_model():
    """
    Lazy-load SentenceTransformer model (singleton, thread-safe).
    Model name đọc từ env EMBEDDING_MODEL (default: BAAI/bge-m3).
    """
    global _model
    if _model is None:
        with _model_lock:
            # Double-checked locking — tránh race condition khi nhiều
            # request đồng thời gọi lần đầu.
            if _model is None:
                from sentence_transformers import SentenceTransformer

                model_name = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
                logger.info(f"Loading embedding model: {model_name} …")
                _model = SentenceTransformer(model_name)
                logger.info(
                    f"Embedding model loaded ✓  "
                    f"(dim={_model.get_sentence_embedding_dimension()})"
                )
    return _model


# ─────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────

def embed_batch(texts: List[str]) -> List[List[float]]:
    """
    Embed một batch văn bản, trả về list of normalized float vectors.

    Args:
        texts: Danh sách chuỗi cần embed. Không được rỗng.

    Returns:
        List[List[float]] — mỗi vector đã được L2-normalize
        (cosine similarity = dot product khi vector đã normalize).

    Raises:
        ValueError: Nếu texts rỗng hoặc chứa string rỗng.
        RuntimeError: Nếu model không load được.
    """
    if not texts:
        raise ValueError("embed_batch: texts không được rỗng.")

    # Lọc chuỗi rỗng để tránh trả về vector vô nghĩa
    cleaned = [t.strip() for t in texts]
    if any(t == "" for t in cleaned):
        raise ValueError(
            "embed_batch: phát hiện chuỗi rỗng trong texts. "
            "Hãy lọc dữ liệu trước khi embed."
        )

    try:
        model = _get_model()
        # normalize_embeddings=True → L2-normalize, cosine sim = dot product
        # show_progress_bar=False → tắt tqdm để log sạch hơn trong server
        vectors = model.encode(
            cleaned,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=32,          # safe default; chỉnh theo VRAM/RAM
            convert_to_numpy=True,
        )
        logger.debug(f"embed_batch: embedded {len(texts)} texts, dim={vectors.shape[1]}")
        # Chuyển numpy array → list[list[float]] để serialize JSON / Qdrant
        return vectors.tolist()

    except Exception as exc:
        logger.error(f"embed_batch failed: {exc}")
        raise RuntimeError(f"Embedding thất bại: {exc}") from exc


def embed_single(text: str) -> List[float]:
    """
    Embed 1 văn bản — wrapper của embed_batch.

    Args:
        text: Chuỗi cần embed. Không được rỗng.

    Returns:
        List[float] — vector đã normalize, độ dài = EMBEDDING_DIM (1024 với bge-m3).
    """
    if not text or not text.strip():
        raise ValueError("embed_single: text không được rỗng.")

    return embed_batch([text])[0]


# ─────────────────────────────────────────────────────────────────
# Utility
# ─────────────────────────────────────────────────────────────────

def get_embedding_dim() -> int:
    """Trả về số chiều của embedding model hiện tại."""
    return _get_model().get_sentence_embedding_dimension()
