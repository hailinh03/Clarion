"""
Clarion — RabbitMQ Consumer Worker
Lắng nghe các Event từ Exchange 'clarion_events'.
"""
import asyncio
import json
import uuid
import os
from dotenv import load_dotenv
load_dotenv()  # Nạp biến môi trường từ .env NGAY LẬP TỨC

from loguru import logger
import aio_pika

from app.services.rabbitmq_client import get_rabbitmq_connection, EXCHANGE_NAME
from app.services.task_generator import gen_tech_tasks
from app.services.testcase_generator import gen_test_cases
from app.services.embedding import embed_batch
from app.services.qdrant_client import upsert_test_case, upsert_brd_chunk
from app.services.coverage import coverage_check
from app.services.brd_processor import parse_and_chunk_file

from app.db.database import AsyncSessionLocal
from app.db.models import TaskStatus
from sqlalchemy.future import select

async def handle_tech_tasks(message: aio_pika.IncomingMessage):
    """Lắng nghe event 'ticket.approved' để sinh Tech Tasks."""
    async with message.process():
        payload = json.loads(message.body.decode())
        ticket_id = payload.get("ticket_id", "unknown")
        task_db_id = f"tech_tasks_{ticket_id}"
        logger.info(f"[Consumer] Bắt đầu sinh Tech Tasks cho ticket_id={ticket_id}")
        
        async with AsyncSessionLocal() as db:
            try:
                tasks = await gen_tech_tasks(payload)
                logger.info(f"[Consumer] Hoàn thành sinh {len(tasks)} Tech Tasks cho ticket_id={ticket_id}")
                
                result = await db.execute(select(TaskStatus).filter(TaskStatus.id == task_db_id))
                task_record = result.scalars().first()
                if task_record:
                    task_record.status = "SUCCESS"
                    task_record.result = json.dumps({"tasks_generated": len(tasks)})
                    await db.commit()
            except Exception as e:
                logger.error(f"[Consumer] Lỗi khi sinh Tech Tasks cho ticket={ticket_id}: {e}")
                result = await db.execute(select(TaskStatus).filter(TaskStatus.id == task_db_id))
                task_record = result.scalars().first()
                if task_record:
                    task_record.status = "FAILED"
                    task_record.error = str(e)
                    await db.commit()

async def handle_test_cases(message: aio_pika.IncomingMessage):
    """Lắng nghe event 'ticket.approved' để sinh Test Cases + Coverage Check."""
    async with message.process():
        payload = json.loads(message.body.decode())
        ticket_id = payload.get("ticket_id", "unknown")
        project_id = payload.get("project_id", "unknown")
        task_db_id = f"test_cases_{ticket_id}"
        
        logger.info(f"[Consumer] Bắt đầu sinh Test Cases cho ticket_id={ticket_id}")
        
        async with AsyncSessionLocal() as db:
            try:
                # 1. Gen test cases
                test_cases = await gen_test_cases(payload)
                
                # 2. Coverage check
                ac_list = payload.get("acceptance_criteria", [])
                coverage_report = coverage_check(ac_list, test_cases)
                
                # 3. Embed & Upsert
                if test_cases:
                    tc_texts = [f"{tc.title} {' '.join(tc.steps)} {tc.expected_result}" for tc in test_cases]
                    tc_vectors = embed_batch(tc_texts)
                    
                    for tc, vector in zip(test_cases, tc_vectors):
                        upsert_test_case(
                            tc_id=tc.id,
                            vector=vector,
                            ticket_id=ticket_id,
                            ac_ref=tc.ac_ref,
                            tc_type=tc.type,
                            title=tc.title,
                            project_id=project_id,
                        )
                        
                logger.info(f"[Consumer] Hoàn thành sinh {len(test_cases)} Test Cases, Coverage: {coverage_report['coverage_percentage']}%")
                
                result = await db.execute(select(TaskStatus).filter(TaskStatus.id == task_db_id))
                task_record = result.scalars().first()
                if task_record:
                    task_record.status = "SUCCESS"
                    task_record.result = json.dumps({
                        "test_cases_generated": len(test_cases),
                        "coverage": coverage_report
                    })
                    await db.commit()
            except Exception as e:
                logger.error(f"[Consumer] Lỗi khi sinh Test Cases cho ticket={ticket_id}: {e}")
                result = await db.execute(select(TaskStatus).filter(TaskStatus.id == task_db_id))
                task_record = result.scalars().first()
                if task_record:
                    task_record.status = "FAILED"
                    task_record.error = str(e)
                    await db.commit()

async def handle_brd_process(message: aio_pika.IncomingMessage):
    """Lắng nghe event 'brd.uploaded' để nhúng vector BRD."""
    async with message.process():
        payload = json.loads(message.body.decode())
        task_id = payload.get("task_id")
        file_path = payload.get("file_path")
        filename = payload.get("filename")
        project_id = payload.get("project_id")
        
        logger.info(f"[Consumer] Bắt đầu xử lý BRD: {filename} (Project: {project_id}, Task: {task_id})")
        
        async with AsyncSessionLocal() as db:
            try:
                with open(file_path, "rb") as f:
                    file_bytes = f.read()
                    
                chunks = parse_and_chunk_file(file_bytes, filename)
                if not chunks:
                    logger.warning(f"[Consumer] File {filename} không có text.")
                    return
                    
                texts = [c["text"] for c in chunks]
                vectors = embed_batch(texts)
                
                for chunk, vector in zip(chunks, vectors):
                    chunk_id = str(uuid.uuid4())
                    upsert_brd_chunk(
                        chunk_id=chunk_id,
                        vector=vector,
                        source="upload",
                        filename=filename,
                        page=chunk["page"],
                        section=chunk["section"],
                        project_id=project_id,
                        text=chunk["text"],
                    )
                    
                logger.info(f"[Consumer] Xử lý xong BRD {filename}: {len(chunks)} chunks.")
                
                # Cập nhật trạng thái SUCCESS vào DB
                if task_id:
                    result = await db.execute(select(TaskStatus).filter(TaskStatus.id == task_id))
                    task = result.scalars().first()
                    if task:
                        task.status = "SUCCESS"
                        task.result = json.dumps({"chunks_processed": len(chunks)})
                        await db.commit()
                        
            except Exception as e:
                logger.error(f"[Consumer] Lỗi xử lý BRD {filename}: {e}")
                # Cập nhật trạng thái FAILED vào DB
                if task_id:
                    result = await db.execute(select(TaskStatus).filter(TaskStatus.id == task_id))
                    task = result.scalars().first()
                    if task:
                        task.status = "FAILED"
                        task.error = str(e)
                        await db.commit()
            finally:
                # Dọn dẹp file tạm
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.debug(f"[Consumer] Đã xóa file tạm {file_path}")

async def main():
    connection = await get_rabbitmq_connection()
    async with connection:
        channel = await connection.channel()
        # Ensure QoS
        await channel.set_qos(prefetch_count=1)
        
        exchange = await channel.declare_exchange(
            EXCHANGE_NAME, 
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )
        
        # Declare queues
        q_tech_tasks = await channel.declare_queue("q_tech_tasks", durable=True)
        q_test_cases = await channel.declare_queue("q_test_cases", durable=True)
        q_brd_process = await channel.declare_queue("q_brd_process", durable=True)
        
        # Bind queues to topic exchange
        await q_tech_tasks.bind(exchange, routing_key="ticket.approved")
        await q_test_cases.bind(exchange, routing_key="ticket.approved")
        await q_brd_process.bind(exchange, routing_key="brd.uploaded")
        
        # Start consuming
        await q_tech_tasks.consume(handle_tech_tasks)
        await q_test_cases.consume(handle_test_cases)
        await q_brd_process.consume(handle_brd_process)
        
        logger.info("[Consumer] Đang lắng nghe sự kiện từ RabbitMQ. Bấm Ctrl+C để thoát.")
        await asyncio.Future()  # Chạy vô hạn

if __name__ == "__main__":
    asyncio.run(main())
