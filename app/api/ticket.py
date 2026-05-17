"""
Clarion — Ticket API
POST /api/ticket/analyze  — phân tích ticket khi PM viết
POST /api/ticket/approve  — approve ticket, kích hoạt gen task / test case
"""
from fastapi import APIRouter

from app.schemas.ticket import TicketInput
from app.schemas.analysis import AnalysisResult
from app.services.analyzer import analyze_ticket as analyzer_analyze_ticket

router = APIRouter()


@router.post("/ticket/analyze", response_model=AnalysisResult)
async def analyze_ticket(ticket: TicketInput) -> AnalysisResult:
    """
    API endpoint để phân tích ticket.
    Nhận input từ webhook hoặc UI, gọi LLM phân tích, và trả về JSON schema chuẩn.
    """
    return await analyzer_analyze_ticket(ticket)


@router.post("/ticket/approve")
async def approve_ticket():
    # TODO: implement — xem task_generator.py + testcase_generator.py
    return {"status": "not_implemented"}
