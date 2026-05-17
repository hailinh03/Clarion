"""
Clarion — Tech Task Generator Service
LLM sinh danh sách TechTask từ ticket đã approve.
"""
from typing import List, Dict
from loguru import logger
from pydantic import ValidationError

from app.chains.task_chain import get_task_chain
from app.schemas.task import TechTask

def _join_list(items: list[str], empty_msg: str = "(empty)") -> str:
    if not items:
        return empty_msg
    return "\n".join(f"{i}. {item}" for i, item in enumerate(items, start=1))

async def gen_tech_tasks(ticket_json: dict) -> List[TechTask]:
    """
    Sử dụng LLM để sinh danh sách TechTask từ ticket_json.
    """
    chain = get_task_chain()
    
    prompt_input = {
        "title": ticket_json.get("title", ""),
        "user_story": ticket_json.get("user_story", "(Không có user story)"),
        "acceptance_criteria": _join_list(ticket_json.get("acceptance_criteria", []), "Không có AC"),
        "business_rules": _join_list(ticket_json.get("business_rules", []), "Không có Business Rule"),
    }
    
    ticket_id = ticket_json.get("ticket_id", "unknown")
    logger.info(f"Generating tech tasks for ticket={ticket_id}")
    
    try:
        raw: List[Dict] = await chain.ainvoke(prompt_input)
    except Exception as exc:
        logger.error(f"Task generation LLM call failed for ticket={ticket_id}: {exc}")
        raise RuntimeError(f"Task generation failed: {exc}") from exc
        
    tasks = []
    if isinstance(raw, list):
        for item in raw:
            try:
                task = TechTask(**item)
                tasks.append(task)
            except ValidationError as e:
                logger.warning(f"Invalid TechTask from LLM output: {item} - Error: {e}")
    else:
        logger.warning(f"LLM output for tasks is not a list. Type: {type(raw)}")
        
    logger.info(f"Generated {len(tasks)} tech tasks for ticket={ticket_id}")
    return tasks
