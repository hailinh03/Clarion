"""
Clarion — TestCase Pydantic schema
"""
from typing import List
from pydantic import BaseModel, Field


class TestCase(BaseModel):
    id: str = Field(..., description="TC-001, TC-002, ...")
    title: str
    type: str = Field(..., description="happy | negative | edge")
    ac_ref: str = Field(..., description="AC1 | BR1 — bắt buộc để coverage check hoạt động")
    precondition: str = ""
    steps: List[str] = Field(default_factory=list)
    expected_result: str
