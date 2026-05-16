"""
Clarion — Analysis Pydantic schemas
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class AmbiguousItem(BaseModel):
    field: str = Field(..., description="AC1 | BR1 | title | description")
    issue: str
    suggestion: str


class MissingItem(BaseModel):
    type: str = Field(
        ...,
        description=(
            "missing_ac | missing_rule | missing_validation "
            "| missing_error_handling | missing_edge_case"
        ),
    )
    description: str
    suggested_text: Optional[str] = None


class AnalysisResult(BaseModel):
    score: int = Field(..., ge=0, le=100)
    summary: Optional[str] = None
    ambiguous_items: List[AmbiguousItem] = Field(default_factory=list)
    missing_items: List[MissingItem] = Field(default_factory=list)
    improved_ac: List[str] = Field(default_factory=list)
    # Fallback flag — set True nếu LLM output không validate được
    needs_review: bool = False
