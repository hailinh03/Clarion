"""
Clarion — Qdrant Retrieval Service
Search context chunks từ brd_chunks + approved_tickets.
Rule: luôn filter theo project_id khi search (RULES.md §4).

Flow 2 (ARCHITECTURE.md):
  ticket_vector → search brd_chunks (top_k=5)
                → search approved_tickets (top_k=3)
                → merge results → trả về context cho LLM prompt
"""
from typing import Any, List

from loguru import logger

from app.services.embedding import embed_single
from app.services.qdrant_client import search_approved_tickets, search_brd_chunks


async def search_context(
    *,
    ticket_text: str,
    project_id: str,
    brd_top_k: int = 5,
    ticket_top_k: int = 3,
) -> List[Any]:
    """
    Tìm context liên quan từ Qdrant cho 1 ticket đang được phân tích.

    Luồng (Flow 2 — ARCHITECTURE.md):
      1. Embed ticket_text → vector
      2. Search collection brd_chunks (BRD tài liệu)
      3. Search collection approved_tickets (ticket cũ đã approve)
      4. Merge kết quả, sắp theo score giảm dần

    Args:
        ticket_text:   Văn bản tổng hợp của ticket (title + user_story + AC + BR).
        project_id:    Bắt buộc — filter Qdrant theo project (RULES.md §4).
        brd_top_k:     Số BRD chunks cần lấy (default 5).
        ticket_top_k:  Số approved ticket cần lấy (default 3).

    Returns:
        List[ScoredPoint] — merge từ cả 2 collection, sắp theo score giảm dần.
        Trả về list rỗng nếu không tìm thấy gì hoặc collection trống.
    """
    # ── Bước 1: Embed ticket text ──────────────────────────────────
    try:
        ticket_vector = embed_single(ticket_text)
    except Exception as exc:
        logger.error(f"search_context: embed failed for project={project_id}: {exc}")
        # Không crash — trả về context rỗng, LLM vẫn có thể phân tích
        # ticket mà không có context (chất lượng thấp hơn nhưng vẫn hữu ích)
        return []

    # ── Bước 2 + 3: Search song song 2 collection ─────────────────
    # Qdrant client là sync, nhưng nhanh (local Docker) nên gọi tuần tự
    brd_results: List[Any] = []
    ticket_results: List[Any] = []

    try:
        brd_results = search_brd_chunks(
            vector=ticket_vector,
            project_id=project_id,
            top_k=brd_top_k,
        )
        logger.debug(
            f"search_context: brd_chunks returned {len(brd_results)} results "
            f"for project={project_id}"
        )
    except Exception as exc:
        # Không crash — collection có thể trống hoặc chưa có data
        logger.warning(f"search_context: brd_chunks search failed: {exc}")

    try:
        ticket_results = search_approved_tickets(
            vector=ticket_vector,
            project_id=project_id,
            top_k=ticket_top_k,
        )
        logger.debug(
            f"search_context: approved_tickets returned {len(ticket_results)} results "
            f"for project={project_id}"
        )
    except Exception as exc:
        logger.warning(f"search_context: approved_tickets search failed: {exc}")

    # ── Bước 4: Merge + sắp theo score giảm dần ───────────────────
    merged = brd_results + ticket_results
    merged.sort(key=lambda p: p.score, reverse=True)

    logger.info(
        f"search_context: total {len(merged)} context chunks "
        f"(brd={len(brd_results)}, tickets={len(ticket_results)}) "
        f"for project={project_id}"
    )

    return merged
