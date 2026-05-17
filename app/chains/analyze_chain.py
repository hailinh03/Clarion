"""
Clarion — Analyze Chain
LangChain chain: analyze_prompt | LLM(Groq) | JsonOutputParser → AnalysisResult

Luồng (từ ARCHITECTURE.md § Flow 2):
  ticket_text → embed → Qdrant search → context_chunks
      → build_analyze_prompt() → LLM → AnalysisResult (JSON validated)

Rules (từ RULES.md):
  - Luôn dùng | JsonOutputParser() ở cuối chain, không dùng raw LLM output.
  - Validate output bằng Pydantic trước khi trả về.
  - Fallback: nếu parse thất bại → trả về AnalysisResult(needs_review=True).
  - Model name đọc từ env, không hardcode.
"""
import os
from typing import Any, Dict, List

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from loguru import logger
from pydantic import ValidationError

from app.prompts.analyze_ticket import ANALYZE_SYSTEM_PROMPT, ANALYZE_USER_PROMPT
from app.schemas.analysis import AnalysisResult, AmbiguousItem, MissingItem
from app.schemas.ticket import TicketInput

# ─────────────────────────────────────────────────────────────────
# LLM factory — đọc từ env, hỗ trợ groq / anthropic / openai / huggingface
# ─────────────────────────────────────────────────────────────────

def _build_llm():
    """
    Khởi tạo LLM cho tác vụ phân tích ticket (tác vụ nặng — cần reasoning tốt).
    Provider đọc từ LLM_PROVIDER, model đọc từ ANALYZE_LLM_MODEL.

    Default: Groq + openai/gpt-oss-120b (free tier).
    """
    provider = os.getenv("LLM_PROVIDER", "groq").lower()
    model = os.getenv("ANALYZE_LLM_MODEL", "openai/gpt-oss-120b")

    logger.info(f"Building analyze LLM: provider={provider} model={model}")

    if provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=model,
            temperature=0,          # deterministic output → JSON ổn định hơn
            max_tokens=4096,
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, temperature=0, max_tokens=4096)

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, temperature=0, max_tokens=4096)

    # Default fallback: HuggingFace Inference API
    from langchain_community.llms import HuggingFaceEndpoint
    from langchain_community.chat_models.huggingface import ChatHuggingFace
    endpoint = HuggingFaceEndpoint(
        repo_id=model,
        task="text-generation",
        max_new_tokens=4096,
    )
    return ChatHuggingFace(llm=endpoint)


# ─────────────────────────────────────────────────────────────────
# Chain builder — singleton
# ─────────────────────────────────────────────────────────────────

_chain: Runnable | None = None


def get_analyze_chain() -> Runnable:
    """
    Trả về singleton LangChain chain cho tác vụ phân tích ticket.
    Chain: ChatPromptTemplate | LLM | JsonOutputParser
    """
    global _chain
    if _chain is None:
        prompt = ChatPromptTemplate.from_messages([
            ("system", ANALYZE_SYSTEM_PROMPT),
            ("human", ANALYZE_USER_PROMPT),
        ])
        llm = _build_llm()
        parser = JsonOutputParser()
        _chain = prompt | llm | parser
        logger.info("Analyze chain built ✓")
    return _chain


# ─────────────────────────────────────────────────────────────────
# Context formatter — chuẩn bị context_chunks từ Qdrant results
# ─────────────────────────────────────────────────────────────────

def format_context_chunks(scored_points: List[Any]) -> str:
    """
    Chuyển Qdrant ScoredPoint list thành plain-text block cho prompt.
    Mỗi chunk được đánh số và kèm score để LLM biết mức độ liên quan.

    Args:
        scored_points: List[ScoredPoint] từ qdrant_client.search_*()
                       Truyền list rỗng nếu không có context.
    """
    if not scored_points:
        return "(Không có tài liệu liên quan trong Qdrant)"

    lines: List[str] = []
    for i, point in enumerate(scored_points, start=1):
        payload = point.payload or {}
        text = payload.get("text", "").strip()
        source = payload.get("source", "unknown")
        score = round(point.score, 3)
        lines.append(f"[{i}] (score={score}, source={source})\n{text}")

    return "\n\n".join(lines)


# ─────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────

async def run_analyze_chain(
    ticket: TicketInput,
    context_chunks: List[Any],
) -> AnalysisResult:
    """
    Chạy full analyze pipeline cho 1 ticket.

    Args:
        ticket:         TicketInput đã validated bởi FastAPI.
        context_chunks: List[ScoredPoint] từ Qdrant (BRD + approved tickets).
                        Truyền [] nếu không có context.

    Returns:
        AnalysisResult — đã validated bằng Pydantic.
        Nếu LLM output không parse được → trả về fallback với needs_review=True.
    """
    chain = get_analyze_chain()

    context_text = format_context_chunks(context_chunks)
    if not context_chunks:
        context_text += (
            "\n\n⚠️ LƯU Ý ĐẶC BIỆT: Hệ thống không tìm thấy bất kỳ tài liệu tham chiếu nào "
            "trong Qdrant cho project_id này. "
            "BẠN TUYỆT ĐỐI KHÔNG ĐƯỢC TỰ BỊA RA (hallucinate) các con số cụ thể (ví dụ: 30 giây, "
            "10 phút, 5 lần, tối đa 3 lần...) trong các trường improved_ac hoặc missing_items. "
            "Thay vào đó, hãy dùng cụm từ '[Cần PM cung cấp thông số]'."
        )

    # Chuẩn bị input variables cho prompt template
    prompt_input: Dict[str, str] = {
        "title": ticket.title,
        "user_story": ticket.user_story or "(Không có user story)",
        "acceptance_criteria": _join_list(ticket.acceptance_criteria, "Không có AC"),
        "business_rules": _join_list(ticket.business_rules, "Không có Business Rule"),
        "context_chunks": context_text,
    }

    logger.info(f"Running analyze chain for ticket={ticket.ticket_id}")

    try:
        raw: Dict = await chain.ainvoke(prompt_input)
        logger.debug(f"Raw LLM output: {raw}")
    except Exception as exc:
        logger.error(f"LLM call failed for ticket={ticket.ticket_id}: {exc}")
        raise RuntimeError(f"LLM analyze thất bại: {exc}") from exc

    # ── Validate bằng Pydantic (RULES.md) ────────────────────────
    try:
        result = AnalysisResult(**raw)
        logger.info(
            f"Analyze complete ticket={ticket.ticket_id} "
            f"score={result.score} "
            f"ambiguous={len(result.ambiguous_items)} "
            f"missing={len(result.missing_items)}"
        )
        return result

    except (ValidationError, TypeError) as exc:
        # Fallback: LLM trả về output không khớp schema
        # Không crash — trả về partial result để PM có thể manual review
        logger.warning(
            f"LLM output validation failed for ticket={ticket.ticket_id}: {exc}. "
            f"Returning fallback needs_review=True."
        )
        return AnalysisResult(
            score=0,
            summary="⚠️ AI output không thể parse tự động. Cần PM review thủ công.",
            needs_review=True,
        )


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _join_list(items: List[str], empty_msg: str = "(empty)") -> str:
    """Nối list[str] thành multi-line string có đánh số thứ tự."""
    if not items:
        return empty_msg
    return "\n".join(f"{i}. {item}" for i, item in enumerate(items, start=1))
