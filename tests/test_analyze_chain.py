"""
Clarion — Unit tests for analyze_chain
Mock LangChain chain hoàn toàn — không gọi Groq API khi chạy CI.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.chains.analyze_chain import (
    _join_list,
    format_context_chunks,
    run_analyze_chain,
    get_analyze_chain,
)
from app.schemas.analysis import AnalysisResult
from app.schemas.ticket import TicketInput

# ─────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_chain_singleton():
    """Reset singleton chain trước mỗi test."""
    import app.chains.analyze_chain as mod
    mod._chain = None
    yield
    mod._chain = None


@pytest.fixture()
def ticket() -> TicketInput:
    return TicketInput(
        ticket_id="PROJ-99",
        title="Người dùng đăng nhập bằng email",
        user_story="As a user, I want to login with email so that I can access the system.",
        acceptance_criteria=["AC1: Nhập email + password hợp lệ → login thành công"],
        business_rules=["BR1: Email phải là địa chỉ đã xác thực"],
        project_id="PROJ",
    )


def _make_valid_llm_output() -> dict:
    return {
        "score": 75,
        "summary": "Ticket rõ ràng nhưng thiếu edge case cho sai password.",
        "ambiguous_items": [
            {"field": "AC1", "issue": "Không rõ format password", "suggestion": "Thêm độ dài tối thiểu"}
        ],
        "missing_items": [
            {"type": "missing_error_handling", "description": "Chưa có AC cho sai password", "suggested_text": "AC2: Sai password 3 lần → khóa tài khoản"}
        ],
        "improved_ac": ["AC1: Nhập email đã xác thực + password >= 8 ký tự → login thành công"],
    }


# ─────────────────────────────────────────────────────────────────
# format_context_chunks
# ─────────────────────────────────────────────────────────────────

def test_format_context_chunks_empty():
    result = format_context_chunks([])
    assert "Không có" in result


def test_format_context_chunks_formats_correctly():
    point = MagicMock()
    point.payload = {"text": "BRD content here", "source": "brd.pdf"}
    point.score = 0.912

    result = format_context_chunks([point])

    assert "[1]" in result
    assert "BRD content here" in result
    assert "brd.pdf" in result
    assert "0.912" in result


def test_format_context_chunks_multiple_points():
    points = []
    for i in range(3):
        p = MagicMock()
        p.payload = {"text": f"content {i}", "source": "src"}
        p.score = 0.9 - i * 0.1
        points.append(p)

    result = format_context_chunks(points)

    assert "[1]" in result
    assert "[2]" in result
    assert "[3]" in result


# ─────────────────────────────────────────────────────────────────
# _join_list
# ─────────────────────────────────────────────────────────────────

def test_join_list_empty():
    assert _join_list([]) == "(empty)"
    assert _join_list([], "custom") == "custom"


def test_join_list_numbered():
    result = _join_list(["AC1: foo", "AC2: bar"])
    assert "1. AC1: foo" in result
    assert "2. AC2: bar" in result


# ─────────────────────────────────────────────────────────────────
# run_analyze_chain — happy path
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_analyze_chain_returns_valid_result(ticket):
    """Chain trả về JSON hợp lệ → AnalysisResult populated đúng."""
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=_make_valid_llm_output())

    with patch("app.chains.analyze_chain.get_analyze_chain", return_value=mock_chain):
        result = await run_analyze_chain(ticket, context_chunks=[])

    assert isinstance(result, AnalysisResult)
    assert result.score == 75
    assert result.needs_review is False
    assert len(result.ambiguous_items) == 1
    assert len(result.missing_items) == 1
    assert result.ambiguous_items[0].field == "AC1"


@pytest.mark.asyncio
async def test_run_analyze_chain_passes_ticket_fields_to_prompt(ticket):
    """Prompt input phải chứa đầy đủ title, AC, BR từ ticket."""
    captured_input: dict = {}

    async def capture_invoke(prompt_input):
        captured_input.update(prompt_input)
        return _make_valid_llm_output()

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke

    with patch("app.chains.analyze_chain.get_analyze_chain", return_value=mock_chain):
        await run_analyze_chain(ticket, context_chunks=[])

    assert captured_input["title"] == ticket.title
    assert "AC1" in captured_input["acceptance_criteria"]
    assert "BR1" in captured_input["business_rules"]


# ─────────────────────────────────────────────────────────────────
# run_analyze_chain — fallback khi output không hợp lệ
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_analyze_chain_fallback_on_invalid_json(ticket):
    """LLM trả về JSON không khớp schema → needs_review=True, không crash."""
    mock_chain = MagicMock()
    mock_chain.ainvoke = AsyncMock(return_value={
        "score": "not-a-number",   # sai kiểu
        "garbage_field": True,
    })

    with patch("app.chains.analyze_chain.get_analyze_chain", return_value=mock_chain):
        result = await run_analyze_chain(ticket, context_chunks=[])

    assert isinstance(result, AnalysisResult)
    assert result.needs_review is True
    assert result.score == 0


@pytest.mark.asyncio
async def test_run_analyze_chain_fallback_on_empty_output(ticket):
    """LLM trả về dict rỗng → fallback needs_review=True."""
    mock_chain = MagicMock()
    mock_chain.ainvoke = AsyncMock(return_value={})

    with patch("app.chains.analyze_chain.get_analyze_chain", return_value=mock_chain):
        result = await run_analyze_chain(ticket, context_chunks=[])

    assert result.needs_review is True


# ─────────────────────────────────────────────────────────────────
# run_analyze_chain — LLM call fails
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_analyze_chain_raises_on_llm_error(ticket):
    """Nếu LLM call thất bại (network, timeout...) → raise RuntimeError."""
    mock_chain = MagicMock()
    mock_chain.ainvoke = AsyncMock(side_effect=Exception("Groq API timeout"))

    with patch("app.chains.analyze_chain.get_analyze_chain", return_value=mock_chain):
        with pytest.raises(RuntimeError, match="LLM analyze thất bại"):
            await run_analyze_chain(ticket, context_chunks=[])


# ─────────────────────────────────────────────────────────────────
# run_analyze_chain — ticket thiếu optional fields
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_analyze_chain_handles_missing_optional_fields():
    """Ticket không có user_story, AC, BR → vẫn chạy được (không crash)."""
    minimal_ticket = TicketInput(
        ticket_id="PROJ-1",
        title="Minimal ticket",
        project_id="PROJ",
        # user_story, acceptance_criteria, business_rules đều để default
    )

    captured: dict = {}

    async def capture_invoke(prompt_input):
        captured.update(prompt_input)
        return _make_valid_llm_output()

    mock_chain = MagicMock()
    mock_chain.ainvoke = capture_invoke

    with patch("app.chains.analyze_chain.get_analyze_chain", return_value=mock_chain):
        result = await run_analyze_chain(minimal_ticket, context_chunks=[])

    # user_story phải có giá trị fallback, không phải None
    assert captured["user_story"] != "None"
    assert "Không có" in captured["acceptance_criteria"]
    assert "Không có" in captured["business_rules"]
    assert result.needs_review is False


# ─────────────────────────────────────────────────────────────────
# get_analyze_chain — singleton
# ─────────────────────────────────────────────────────────────────

def test_get_analyze_chain_returns_singleton(monkeypatch):
    """get_analyze_chain() phải trả về cùng 1 instance khi gọi nhiều lần."""
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "fake-key-for-test")

    mock_groq_cls = MagicMock(return_value=MagicMock())

    with patch("app.chains.analyze_chain._build_llm", return_value=MagicMock()):
        c1 = get_analyze_chain()
        c2 = get_analyze_chain()

    assert c1 is c2
