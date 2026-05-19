"""
Clarion — Test Case Generator Service
LLM sinh danh sách TestCase từ AC + BR của ticket.
"""
from typing import List, Dict
from loguru import logger
from pydantic import ValidationError

from app.chains.testcase_chain import get_testcase_chain
from app.schemas.testcase import TestCase

def _join_list(items: list[str], empty_msg: str = "(empty)") -> str:
    if not items:
        return empty_msg
    return "\n".join(f"{i}. {item}" for i, item in enumerate(items, start=1))

async def gen_test_cases(ticket_json: dict) -> List[TestCase]:
    """
    Sử dụng LLM để sinh danh sách TestCase từ ticket_json.
    """
    chain = get_testcase_chain()
    
    prompt_input = {
        "acceptance_criteria": _join_list(ticket_json.get("acceptance_criteria", []), "Không có AC"),
        "business_rules": _join_list(ticket_json.get("business_rules", []), "Không có Business Rule"),
        "edge_cases": _join_list(ticket_json.get("edge_cases", []), "Không có Edge Case"),
    }
    
    ticket_id = ticket_json.get("ticket_id", "unknown")
    logger.info(f"Generating test cases for ticket={ticket_id}")
    
    try:
        raw: List[Dict] = await chain.ainvoke(prompt_input)
    except Exception as exc:
        logger.error(f"Test case generation LLM call failed for ticket={ticket_id}: {exc}")
        raise RuntimeError(f"Test case generation failed: {exc}") from exc
        
    testcases = []
    if isinstance(raw, list):
        for item in raw:
            try:
                tc = TestCase(**item)
                testcases.append(tc)
            except ValidationError as e:
                logger.warning(f"Invalid TestCase from LLM output: {item} - Error: {e}")
    else:
        logger.warning(f"LLM output for test cases is not a list. Type: {type(raw)}")
        
    logger.info(f"Generated {len(testcases)} test cases for ticket={ticket_id}")
    return testcases
