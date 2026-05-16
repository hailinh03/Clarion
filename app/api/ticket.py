"""
Clarion — Ticket API
POST /api/ticket/analyze  — phân tích ticket khi PM viết
POST /api/ticket/approve  — approve ticket, kích hoạt gen task / test case
"""
from fastapi import APIRouter

router = APIRouter()


@router.post("/ticket/analyze")
async def analyze_ticket():
    # TODO: implement — xem analyzer.py + analyze_chain.py
    return {"status": "not_implemented"}


@router.post("/ticket/approve")
async def approve_ticket():
    # TODO: implement — xem task_generator.py + testcase_generator.py
    return {"status": "not_implemented"}
