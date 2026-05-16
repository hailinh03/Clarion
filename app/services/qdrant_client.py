"""
Clarion — Qdrant Client Service
Kết nối Qdrant local (URL đọc từ .env, không cần API key khi self-host).

Collections (từ ARCHITECTURE.md):
  brd_chunks       — BRD chunks, metadata: source, filename, page, section, project_id
  approved_tickets — Ticket đã approve, metadata: ticket_id, project_id, created_at, sprint
  test_cases       — Test case đã sinh, metadata: ticket_id, ac_ref, type

Rules (từ RULES.md):
  - Luôn filter theo project_id khi search → tránh lẫn data giữa các project.
  - Mọi external call đều có try/except + log lỗi rõ ràng.
  - Metadata payload bắt buộc đầy đủ khi upsert.
"""
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.http.exceptions import UnexpectedResponse

# ─────────────────────────────────────────────────────────────────
# Constants — đọc từ .env
# ─────────────────────────────────────────────────────────────────

QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY: Optional[str] = os.getenv("QDRANT_API_KEY") or None  # None nếu self-host
VECTOR_SIZE: int = int(os.getenv("QDRANT_VECTOR_SIZE", "1024"))       # bge-m3 = 1024

# Tên collection — đọc từ .env để dễ override trong test
COL_BRD: str = os.getenv("QDRANT_COLLECTION_BRD", "brd_chunks")
COL_TICKETS: str = os.getenv("QDRANT_COLLECTION_TICKETS", "approved_tickets")
COL_TESTCASES: str = os.getenv("QDRANT_COLLECTION_TESTCASES", "test_cases")

# Distance metric — Cosine phù hợp với normalized vector từ bge-m3
DISTANCE = qmodels.Distance.COSINE

# ─────────────────────────────────────────────────────────────────
# Singleton client
# ─────────────────────────────────────────────────────────────────

_client: Optional[QdrantClient] = None


def get_client() -> QdrantClient:
    """
    Trả về singleton QdrantClient.
    Lazy-init: chỉ kết nối khi lần đầu gọi.
    """
    global _client
    if _client is None:
        logger.info(f"Connecting to Qdrant at {QDRANT_URL} …")
        _client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,   # None → không gửi header, dùng cho local
            timeout=10,
        )
        logger.info("Qdrant connected ✓")
    return _client


# ─────────────────────────────────────────────────────────────────
# Collection init — idempotent (safe to call nhiều lần)
# ─────────────────────────────────────────────────────────────────

def _ensure_collection(client: QdrantClient, name: str) -> None:
    """
    Tạo collection nếu chưa tồn tại.
    Nếu đã tồn tại thì kiểm tra vector size có khớp không.
    Idempotent — safe to call on every startup.
    """
    try:
        info = client.get_collection(name)
        existing_size = info.config.params.vectors.size  # type: ignore[union-attr]
        if existing_size != VECTOR_SIZE:
            raise RuntimeError(
                f"Collection '{name}' tồn tại với vector size={existing_size}, "
                f"nhưng config yêu cầu size={VECTOR_SIZE}. "
                f"Hãy xóa collection cũ rồi restart: "
                f"DELETE {QDRANT_URL}/collections/{name}"
            )
        logger.info(f"Collection '{name}' already exists (size={existing_size}) ✓")

    except UnexpectedResponse as exc:
        if exc.status_code == 404:
            # Collection chưa tồn tại → tạo mới
            client.create_collection(
                collection_name=name,
                vectors_config=qmodels.VectorParams(
                    size=VECTOR_SIZE,
                    distance=DISTANCE,
                ),
            )
            logger.info(f"Collection '{name}' created (size={VECTOR_SIZE}, distance=COSINE) ✓")
        else:
            logger.error(f"Qdrant error when checking collection '{name}': {exc}")
            raise


def init_collections() -> None:
    """
    Tạo (hoặc xác nhận) toàn bộ 3 collections cho Clarion.
    Gọi 1 lần lúc startup trong FastAPI lifespan.

    Collections:
      brd_chunks       → BRD được chunk + embed
      approved_tickets → Ticket đã approve
      test_cases       → Test case đã sinh
    """
    client = get_client()
    try:
        for col in (COL_BRD, COL_TICKETS, COL_TESTCASES):
            _ensure_collection(client, col)
        logger.info("All Qdrant collections ready ✓")
    except Exception as exc:
        logger.error(f"init_collections failed: {exc}")
        raise


# ─────────────────────────────────────────────────────────────────
# Upsert helpers — mỗi collection có payload schema riêng
# ─────────────────────────────────────────────────────────────────

def upsert_brd_chunk(
    *,
    chunk_id: str,
    vector: List[float],
    source: str,
    filename: str,
    page: int,
    section: str,
    project_id: str,
    text: str,  # lưu raw text để có thể hiển thị lại khi retrieve
) -> None:
    """
    Upsert 1 BRD chunk vào collection brd_chunks.

    Metadata bắt buộc (từ ARCHITECTURE.md):
      source, filename, page, section, project_id
    """
    client = get_client()
    try:
        client.upsert(
            collection_name=COL_BRD,
            points=[
                qmodels.PointStruct(
                    id=_to_uuid(chunk_id),
                    vector=vector,
                    payload={
                        "source": source,
                        "filename": filename,
                        "page": page,
                        "section": section,
                        "project_id": project_id,
                        "text": text,                        # raw content để retrieve
                        "source_type": "brd_chunk",
                        "created_at": _utcnow(),
                    },
                )
            ],
        )
        logger.debug(f"Upserted BRD chunk id={chunk_id} project={project_id}")
    except Exception as exc:
        logger.error(f"upsert_brd_chunk failed (id={chunk_id}): {exc}")
        raise


def upsert_approved_ticket(
    *,
    ticket_id: str,
    vector: List[float],
    project_id: str,
    sprint: str,
    text: str,  # full ticket text đã chuẩn hóa
    extra_payload: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Upsert ticket đã approve vào collection approved_tickets.

    Metadata bắt buộc (từ ARCHITECTURE.md):
      ticket_id, project_id, created_at, sprint
    """
    client = get_client()
    payload: Dict[str, Any] = {
        "ticket_id": ticket_id,
        "project_id": project_id,
        "created_at": _utcnow(),
        "sprint": sprint,
        "text": text,
        "source": "approved_ticket",
    }
    if extra_payload:
        payload.update(extra_payload)

    try:
        client.upsert(
            collection_name=COL_TICKETS,
            points=[
                qmodels.PointStruct(
                    id=_to_uuid(ticket_id),
                    vector=vector,
                    payload=payload,
                )
            ],
        )
        logger.debug(f"Upserted approved ticket id={ticket_id} project={project_id}")
    except Exception as exc:
        logger.error(f"upsert_approved_ticket failed (id={ticket_id}): {exc}")
        raise


def upsert_test_case(
    *,
    tc_id: str,
    vector: List[float],
    ticket_id: str,
    ac_ref: str,
    tc_type: str,   # happy | negative | edge
    title: str,
    project_id: str,
) -> None:
    """
    Upsert test case vào collection test_cases.

    Metadata bắt buộc (từ ARCHITECTURE.md):
      ticket_id, ac_ref, type
    """
    if tc_type not in {"happy", "negative", "edge"}:
        raise ValueError(f"tc_type phải là happy|negative|edge, nhận: {tc_type!r}")

    client = get_client()
    try:
        client.upsert(
            collection_name=COL_TESTCASES,
            points=[
                qmodels.PointStruct(
                    id=_to_uuid(tc_id),
                    vector=vector,
                    payload={
                        "tc_id": tc_id,
                        "ticket_id": ticket_id,
                        "ac_ref": ac_ref,
                        "type": tc_type,
                        "title": title,
                        "project_id": project_id,
                        "created_at": _utcnow(),
                    },
                )
            ],
        )
        logger.debug(f"Upserted test case id={tc_id} ac_ref={ac_ref} type={tc_type}")
    except Exception as exc:
        logger.error(f"upsert_test_case failed (id={tc_id}): {exc}")
        raise


# ─────────────────────────────────────────────────────────────────
# Search helpers — luôn filter theo project_id (RULES.md)
# ─────────────────────────────────────────────────────────────────

def search_brd_chunks(
    *,
    vector: List[float],
    project_id: str,
    top_k: int = 5,
) -> List[qmodels.ScoredPoint]:
    """
    Tìm BRD chunks tương đồng nhất với vector truy vấn.
    Luôn filter theo project_id — tránh lẫn data giữa các project.
    """
    return _search(
        collection=COL_BRD,
        vector=vector,
        project_id=project_id,
        top_k=top_k,
    )


def search_approved_tickets(
    *,
    vector: List[float],
    project_id: str,
    top_k: int = 5,
) -> List[qmodels.ScoredPoint]:
    """
    Tìm ticket đã approve tương đồng nhất.
    Dùng để cung cấp context khi phân tích ticket mới.
    """
    return _search(
        collection=COL_TICKETS,
        vector=vector,
        project_id=project_id,
        top_k=top_k,
    )


def search_test_cases(
    *,
    vector: List[float],
    project_id: str,
    ticket_id: Optional[str] = None,
    top_k: int = 10,
) -> List[qmodels.ScoredPoint]:
    """
    Tìm test case tương đồng — dùng cho coverage check.
    Có thể filter thêm theo ticket_id nếu muốn coverage trong 1 ticket.
    """
    extra_filter: Optional[qmodels.Filter] = None
    if ticket_id:
        extra_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="project_id",
                    match=qmodels.MatchValue(value=project_id),
                ),
                qmodels.FieldCondition(
                    key="ticket_id",
                    match=qmodels.MatchValue(value=ticket_id),
                ),
            ]
        )

    return _search(
        collection=COL_TESTCASES,
        vector=vector,
        project_id=project_id,
        top_k=top_k,
        override_filter=extra_filter,
    )


def _search(
    *,
    collection: str,
    vector: List[float],
    project_id: str,
    top_k: int,
    override_filter: Optional[qmodels.Filter] = None,
) -> List[qmodels.ScoredPoint]:
    """
    Internal search với project_id filter bắt buộc.

    Args:
        override_filter: Nếu truyền vào, dùng filter này thay vì filter mặc định.
                         Caller phải đảm bảo override_filter vẫn include project_id.
    """
    client = get_client()

    query_filter = override_filter or qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="project_id",
                match=qmodels.MatchValue(value=project_id),
            )
        ]
    )

    try:
        results = client.search(
            collection_name=collection,
            query_vector=vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )
        logger.debug(
            f"search '{collection}' project={project_id}: "
            f"got {len(results)} results (top_k={top_k})"
        )
        return results
    except Exception as exc:
        logger.error(f"search failed collection='{collection}' project={project_id}: {exc}")
        raise


# ─────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────

def _utcnow() -> str:
    """ISO-8601 UTC timestamp."""
    return datetime.now(tz=timezone.utc).isoformat()


def _to_uuid(raw_id: str) -> str:
    """
    Qdrant point ID phải là UUID hoặc unsigned int.
    Chuyển ticket_id / chunk_id dạng string thành UUID5 deterministc.
    Cùng input → cùng UUID → upsert idempotent.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, raw_id))
