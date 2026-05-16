"""
Clarion — Unit tests for qdrant_client service
Mock QdrantClient hoàn toàn, không cần Qdrant server khi chạy CI.
"""
import uuid
from unittest.mock import MagicMock, call, patch

import pytest
from qdrant_client.http import models as qmodels
from qdrant_client.http.exceptions import UnexpectedResponse

import app.services.qdrant_client as qc


# ─────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_client():
    """Reset singleton trước mỗi test."""
    qc._client = None
    yield
    qc._client = None


@pytest.fixture()
def mock_qdrant():
    """Patch QdrantClient constructor, trả về MagicMock."""
    with patch("app.services.qdrant_client.QdrantClient") as MockCls:
        client = MagicMock()
        MockCls.return_value = client
        yield client


# ─────────────────────────────────────────────────────────────────
# get_client
# ─────────────────────────────────────────────────────────────────

def test_get_client_returns_singleton(mock_qdrant):
    c1 = qc.get_client()
    c2 = qc.get_client()
    assert c1 is c2, "get_client() phải trả về cùng 1 instance"


def test_get_client_uses_env_url(monkeypatch, mock_qdrant):
    monkeypatch.setenv("QDRANT_URL", "http://custom-host:9999")
    qc._client = None
    with patch("app.services.qdrant_client.QdrantClient") as MockCls:
        MockCls.return_value = MagicMock()
        qc.get_client()
        MockCls.assert_called_once_with(
            url="http://custom-host:9999",
            api_key=None,
            timeout=10,
        )


# ─────────────────────────────────────────────────────────────────
# _ensure_collection
# ─────────────────────────────────────────────────────────────────

def test_ensure_collection_creates_when_not_exists(mock_qdrant):
    """404 → tạo collection mới."""
    mock_qdrant.get_collection.side_effect = UnexpectedResponse(
        status_code=404, reason_phrase="Not Found", content=b"", headers={}
    )
    qc._ensure_collection(mock_qdrant, "test_col")
    mock_qdrant.create_collection.assert_called_once_with(
        collection_name="test_col",
        vectors_config=qmodels.VectorParams(size=qc.VECTOR_SIZE, distance=qmodels.Distance.COSINE),
    )


def test_ensure_collection_skips_if_exists_same_size(mock_qdrant):
    """Collection đã tồn tại đúng size → không tạo lại."""
    info = MagicMock()
    info.config.params.vectors.size = qc.VECTOR_SIZE
    mock_qdrant.get_collection.return_value = info

    qc._ensure_collection(mock_qdrant, "brd_chunks")

    mock_qdrant.create_collection.assert_not_called()


def test_ensure_collection_raises_on_size_mismatch(mock_qdrant):
    """Vector size khác → phải raise RuntimeError ngay, không tạo lại."""
    info = MagicMock()
    info.config.params.vectors.size = 999   # sai
    mock_qdrant.get_collection.return_value = info

    with pytest.raises(RuntimeError, match="vector size"):
        qc._ensure_collection(mock_qdrant, "brd_chunks")

    mock_qdrant.create_collection.assert_not_called()


def test_ensure_collection_re_raises_non_404(mock_qdrant):
    """Lỗi Qdrant không phải 404 → vẫn phải propagate."""
    mock_qdrant.get_collection.side_effect = UnexpectedResponse(
        status_code=500, reason_phrase="Server Error", content=b"", headers={}
    )
    with pytest.raises(UnexpectedResponse):
        qc._ensure_collection(mock_qdrant, "brd_chunks")


# ─────────────────────────────────────────────────────────────────
# init_collections
# ─────────────────────────────────────────────────────────────────

def test_init_collections_creates_all_three(mock_qdrant):
    """init_collections() phải đảm bảo cả 3 collection tồn tại."""
    mock_qdrant.get_collection.side_effect = UnexpectedResponse(
        status_code=404, reason_phrase="Not Found", content=b"", headers={}
    )
    qc.init_collections()
    created = [c.kwargs["collection_name"] for c in mock_qdrant.create_collection.call_args_list]
    assert set(created) == {qc.COL_BRD, qc.COL_TICKETS, qc.COL_TESTCASES}


# ─────────────────────────────────────────────────────────────────
# upsert_brd_chunk
# ─────────────────────────────────────────────────────────────────

def test_upsert_brd_chunk_calls_qdrant(mock_qdrant):
    qc.upsert_brd_chunk(
        chunk_id="chunk-001",
        vector=[0.1] * qc.VECTOR_SIZE,
        source="brd_v2.pdf",
        filename="brd_v2.pdf",
        page=3,
        section="Authentication",
        project_id="PROJ",
        text="User must login with email and password.",
    )
    mock_qdrant.upsert.assert_called_once()
    args = mock_qdrant.upsert.call_args
    assert args.kwargs["collection_name"] == qc.COL_BRD
    payload = args.kwargs["points"][0].payload
    assert payload["project_id"] == "PROJ"
    assert payload["section"] == "Authentication"
    assert payload["page"] == 3


# ─────────────────────────────────────────────────────────────────
# upsert_approved_ticket
# ─────────────────────────────────────────────────────────────────

def test_upsert_approved_ticket_calls_qdrant(mock_qdrant):
    qc.upsert_approved_ticket(
        ticket_id="PROJ-42",
        vector=[0.2] * qc.VECTOR_SIZE,
        project_id="PROJ",
        sprint="Sprint 5",
        text="As a user I want to login...",
    )
    mock_qdrant.upsert.assert_called_once()
    payload = mock_qdrant.upsert.call_args.kwargs["points"][0].payload
    assert payload["ticket_id"] == "PROJ-42"
    assert payload["sprint"] == "Sprint 5"
    assert "created_at" in payload


# ─────────────────────────────────────────────────────────────────
# upsert_test_case
# ─────────────────────────────────────────────────────────────────

def test_upsert_test_case_calls_qdrant(mock_qdrant):
    qc.upsert_test_case(
        tc_id="TC-001",
        vector=[0.3] * qc.VECTOR_SIZE,
        ticket_id="PROJ-42",
        ac_ref="AC1",
        tc_type="happy",
        title="Login thành công với email hợp lệ",
        project_id="PROJ",
    )
    mock_qdrant.upsert.assert_called_once()
    payload = mock_qdrant.upsert.call_args.kwargs["points"][0].payload
    assert payload["ac_ref"] == "AC1"
    assert payload["type"] == "happy"


def test_upsert_test_case_rejects_invalid_type(mock_qdrant):
    with pytest.raises(ValueError, match="happy|negative|edge"):
        qc.upsert_test_case(
            tc_id="TC-001",
            vector=[0.0] * qc.VECTOR_SIZE,
            ticket_id="PROJ-42",
            ac_ref="AC1",
            tc_type="invalid_type",
            title="bad",
            project_id="PROJ",
        )
    mock_qdrant.upsert.assert_not_called()


# ─────────────────────────────────────────────────────────────────
# search — project_id filter bắt buộc
# ─────────────────────────────────────────────────────────────────

def test_search_brd_chunks_passes_project_filter(mock_qdrant):
    mock_qdrant.search.return_value = []
    qc.search_brd_chunks(vector=[0.1] * qc.VECTOR_SIZE, project_id="PROJ")

    call_kwargs = mock_qdrant.search.call_args.kwargs
    assert call_kwargs["collection_name"] == qc.COL_BRD
    # Kiểm tra filter có project_id
    must_conditions = call_kwargs["query_filter"].must
    keys = [c.key for c in must_conditions]
    assert "project_id" in keys


def test_search_approved_tickets_passes_project_filter(mock_qdrant):
    mock_qdrant.search.return_value = []
    qc.search_approved_tickets(vector=[0.2] * qc.VECTOR_SIZE, project_id="PROJ-X")

    call_kwargs = mock_qdrant.search.call_args.kwargs
    must_conditions = call_kwargs["query_filter"].must
    keys = [c.key for c in must_conditions]
    assert "project_id" in keys


def test_search_test_cases_with_ticket_id_filter(mock_qdrant):
    """Khi có ticket_id, filter phải có cả project_id lẫn ticket_id."""
    mock_qdrant.search.return_value = []
    qc.search_test_cases(
        vector=[0.3] * qc.VECTOR_SIZE,
        project_id="PROJ",
        ticket_id="PROJ-42",
    )
    call_kwargs = mock_qdrant.search.call_args.kwargs
    must_conditions = call_kwargs["query_filter"].must
    keys = [c.key for c in must_conditions]
    assert "project_id" in keys
    assert "ticket_id" in keys


# ─────────────────────────────────────────────────────────────────
# _to_uuid — deterministic
# ─────────────────────────────────────────────────────────────────

def test_to_uuid_is_deterministic():
    u1 = qc._to_uuid("PROJ-123")
    u2 = qc._to_uuid("PROJ-123")
    assert u1 == u2


def test_to_uuid_is_different_for_different_ids():
    assert qc._to_uuid("PROJ-1") != qc._to_uuid("PROJ-2")


def test_to_uuid_is_valid_uuid_format():
    raw = qc._to_uuid("any-string")
    parsed = uuid.UUID(raw)   # raise nếu không phải UUID hợp lệ
    assert str(parsed) == raw
