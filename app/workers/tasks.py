"""
Clarion — Celery task definitions
Tasks được gọi async sau khi PM approve ticket.
"""
from app.workers.celery_app import celery_app


@celery_app.task(name="tasks.gen_tech_tasks")
def task_gen_tech_tasks(ticket_json: dict):
    """Sinh technical task từ ticket đã approve."""
    import asyncio
    from loguru import logger
    from app.services.task_generator import gen_tech_tasks

    ticket_id = ticket_json.get("ticket_id", "unknown")
    logger.info(f"[Celery] Bắt đầu sinh Tech Tasks cho ticket_id={ticket_id}")
    try:
        tasks = asyncio.run(gen_tech_tasks(ticket_json))
        logger.info(f"[Celery] Hoàn thành sinh {len(tasks)} Tech Tasks cho ticket_id={ticket_id}")
        return [t.model_dump() for t in tasks]
    except Exception as e:
        logger.error(f"[Celery] Lỗi khi sinh Tech Tasks cho ticket={ticket_id}: {e}")
        raise


@celery_app.task(name="tasks.gen_test_cases")
def task_gen_test_cases(ticket_json: dict):
    """Sinh test case từ ticket đã approve + chạy coverage check."""
    # TODO: import + call testcase_generator.gen_test_cases(ticket_json)
    raise NotImplementedError
