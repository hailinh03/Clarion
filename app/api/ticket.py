"""
Clarion — Ticket API
POST /api/ticket/analyze  — phân tích ticket khi PM viết
POST /api/ticket/approve  — approve ticket, kích hoạt gen task / test case
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.database import get_db
from app.db.models import TaskStatus

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
async def approve_ticket(ticket: TicketJSON, db: AsyncSession = Depends(get_db)):
    """
    Approve ticket:
    1. Embed toàn bộ nội dung ticket và upsert vào Qdrant (approved_tickets).
    2. Ghi nhận trạng thái vào PostgreSQL.
    3. Phát event lên RabbitMQ để sinh tech task và test case chạy ngầm.
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
            sprint="current",
            text=ticket_text
        )
    
    await run_in_threadpool(do_upsert)

    # [Bước B] Ghi nhận 2 Task vào DB (hỗ trợ update nếu đã tồn tại)
    task_tech_id = f"tech_tasks_{ticket.ticket_id}"
    task_test_id = f"test_cases_{ticket.ticket_id}"
    
    # Xử lý tech task
    result_tech = await db.execute(select(TaskStatus).filter(TaskStatus.id == task_tech_id))
    task_tech = result_tech.scalars().first()
    if task_tech:
        task_tech.status = "STARTED"
        task_tech.result = None
        task_tech.error = None
    else:
        db.add(TaskStatus(id=task_tech_id, task_name="gen_tech_tasks", status="STARTED"))
        
    # Xử lý test case
    result_test = await db.execute(select(TaskStatus).filter(TaskStatus.id == task_test_id))
    task_test = result_test.scalars().first()
    if task_test:
        task_test.status = "STARTED"
        task_test.result = None
        task_test.error = None
    else:
        db.add(TaskStatus(id=task_test_id, task_name="gen_test_cases", status="STARTED"))
        
    await db.commit()

    # [Bước C] Publish event ticket.approved lên RabbitMQ
    ticket_dict = ticket.model_dump()
    await publish_event("ticket.approved", ticket_dict)

    return {
        "status": "processing", 
        "ticket_id": ticket.ticket_id,
        "message": "Đã đẩy task tạo Tech Task và Test Case xuống background"
    }

import json

@router.get("/ticket/status/{ticket_id}")
async def get_ticket_status(ticket_id: str, db: AsyncSession = Depends(get_db)):
    """Lấy trạng thái xử lý ngầm của Ticket (Tech Tasks và Test Cases)."""
    task_tech_id = f"tech_tasks_{ticket_id}"
    task_test_id = f"test_cases_{ticket_id}"
    
    result_tech = await db.execute(select(TaskStatus).filter(TaskStatus.id == task_tech_id))
    task_tech = result_tech.scalars().first()
    
    result_test = await db.execute(select(TaskStatus).filter(TaskStatus.id == task_test_id))
    task_test = result_test.scalars().first()
    
    if not task_tech and not task_test:
        raise HTTPException(status_code=404, detail="Không tìm thấy task xử lý cho ticket này")
        
    # Parse kết quả từ JSON string thành Dict/List để Frontend nhận được JSON chuẩn
    tech_result = None
    if task_tech and task_tech.result:
        try:
            tech_result = json.loads(task_tech.result)
        except Exception:
            tech_result = task_tech.result
            
    test_result = None
    if task_test and task_test.result:
        try:
            test_result = json.loads(task_test.result)
        except Exception:
            test_result = task_test.result
        
    return {
        "ticket_id": ticket_id,
        "tech_tasks": {
            "status": task_tech.status if task_tech else "NOT_FOUND",
            "result": tech_result,
            "error": task_tech.error if task_tech else None
        },
        "test_cases": {
            "status": task_test.status if task_test else "NOT_FOUND",
            "result": test_result,
            "error": task_test.error if task_test else None
        }
    }
