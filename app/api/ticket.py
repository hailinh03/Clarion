"""
Clarion — Ticket API
POST /api/ticket/analyze  — phân tích ticket khi PM viết
POST /api/ticket/approve  — approve ticket, kích hoạt gen task / test case
"""
from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from app.schemas.ticket import TicketInput, TicketJSON
from app.schemas.analysis import AnalysisResult
from app.services.analyzer import analyze_ticket as analyzer_analyze_ticket
from app.services.embedding import embed_single
from app.services.qdrant_client import upsert_approved_ticket
from app.services.rabbitmq_client import publish_event

router = APIRouter()

@router.post("/ticket/analyze", response_model=AnalysisResult)
async def analyze_ticket(ticket: TicketInput) -> AnalysisResult:
    """
    API endpoint để phân tích ticket.
    Nhận input từ webhook hoặc UI, gọi LLM phân tích, và trả về JSON schema chuẩn.
    """
    return await analyzer_analyze_ticket(ticket)

@router.post("/ticket/approve")
async def approve_ticket(ticket: TicketJSON):
    """
    Approve ticket:
    1. Embed toàn bộ nội dung ticket và upsert vào Qdrant (approved_tickets).
    2. Phát event lên RabbitMQ để sinh tech task và test case chạy ngầm.
    """
    # 1. Tổng hợp text
    parts = [ticket.title]
    if ticket.user_story:
        parts.append(ticket.user_story)
    if ticket.acceptance_criteria:
        parts.extend(ticket.acceptance_criteria)
    if ticket.business_rules:
        parts.extend(ticket.business_rules)
    if ticket.edge_cases:
        parts.extend(ticket.edge_cases)
        
    ticket_text = "\n".join(parts)
    
    # [Bước A] Embed và upsert vào Qdrant (dùng threadpool để không block loop)
    def do_upsert():
        vector = embed_single(ticket_text)
        upsert_approved_ticket(
            ticket_id=ticket.ticket_id,
            vector=vector,
            project_id=ticket.project_id,
            sprint="current",  # Có thể bổ sung field sprint vào TicketJSON sau
            text=ticket_text
        )
    
    await run_in_threadpool(do_upsert)

    # [Bước B] Publish event ticket.approved lên RabbitMQ
    ticket_dict = ticket.model_dump()
    await publish_event("ticket.approved", ticket_dict)

    return {"status": "processing", "ticket_id": ticket.ticket_id}
