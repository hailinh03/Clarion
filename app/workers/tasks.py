"""
Clarion — Celery task definitions
Tasks được gọi async sau khi PM approve ticket.
"""
from app.workers.celery_app import celery_app


@celery_app.task(name="tasks.gen_tech_tasks")
def task_gen_tech_tasks(ticket_json: dict):
    """Sinh technical task từ ticket đã approve."""
    # TODO: import + call task_generator.gen_tech_tasks(ticket_json)
    raise NotImplementedError


@celery_app.task(name="tasks.gen_test_cases")
def task_gen_test_cases(ticket_json: dict):
    """Sinh test case từ ticket đã approve + chạy coverage check."""
    # TODO: import + call testcase_generator.gen_test_cases(ticket_json)
    raise NotImplementedError
