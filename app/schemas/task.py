"""
Clarion — TechTask Pydantic schema
"""
from typing import Optional
from pydantic import BaseModel, Field


class TechTask(BaseModel):
    title: str
    type: str = Field(..., description="BE | FE | DB | DevOps | Testing")
    description: str
    estimate_hours: int = Field(..., ge=1, le=8)
    ac_ref: Optional[str] = Field(None, description="AC1 | BR1 | null nếu task chung")
