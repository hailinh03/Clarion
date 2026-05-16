"""
Clarion — Ticket Pydantic schemas
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class TicketInput(BaseModel):
    """Input thô từ Jira webhook hoặc UI."""
    ticket_id: str = Field(..., description="Jira ticket ID, e.g. PROJ-123")
    title: str
    user_story: Optional[str] = None
    acceptance_criteria: List[str] = Field(default_factory=list)
    business_rules: List[str] = Field(default_factory=list)
    edge_cases: List[str] = Field(default_factory=list)
    project_id: str


class TicketJSON(TicketInput):
    """Ticket đã được chuẩn hoá sau khi PM approve."""
    pass
