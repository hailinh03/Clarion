"""
Clarion — Analyzer Service
Gọi LLM phân tích ticket, trả về AnalysisResult (JSON validated by Pydantic).
"""
from app.schemas.ticket import TicketInput
from app.schemas.analysis import AnalysisResult
from app.services.retrieval import search_context
from app.chains.analyze_chain import run_analyze_chain

async def analyze_ticket(ticket: TicketInput) -> AnalysisResult:
    """
    Phân tích ticket bằng cách:
    1. Tổng hợp text để vector search
    2. Tìm context từ Qdrant (BRD + approved tickets)
    3. Gọi LLM qua LangChain
    """
    # 1. Tổng hợp ticket text
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
    
    # 2. Retrieve context chunks từ Qdrant
    context_chunks = await search_context(
        ticket_text=ticket_text,
        project_id=ticket.project_id
    )
    
    # 3. Gọi analyze chain (LLM)
    result = await run_analyze_chain(
        ticket=ticket,
        context_chunks=context_chunks
    )
    
    return result
