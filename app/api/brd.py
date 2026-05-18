"""
Clarion — BRD Upload API
POST /api/brd/upload  — upload BRD (PDF/Word) → lưu tạm → Celery xử lý ngầm.
"""
import os
import uuid
from fastapi import APIRouter, File, Form, UploadFile, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from loguru import logger

from app.db.database import get_db
from app.db.models import TaskStatus

from app.services.rabbitmq_client import publish_event

router = APIRouter()

UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/brd/upload")
async def upload_brd(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """
    API endpoint để upload tài liệu BRD.
    Hỗ trợ PDF, DOCX, TXT. File sẽ được lưu tạm và đẩy vào hàng đợi Celery
    để chunking và embedding bất đồng bộ.
    """
    filename = file.filename or "unknown_file"
    file_bytes = await file.read()
    
    # 1. Lưu file tạm
    temp_filename = f"{uuid.uuid4()}_{filename}"
    file_path = os.path.join(UPLOAD_DIR, temp_filename)
    
    try:
        with open(file_path, "wb") as f:
            f.write(file_bytes)
    except Exception as e:
        logger.error(f"Lỗi khi lưu file tạm {filename}: {e}")
        raise HTTPException(status_code=500, detail="Không thể lưu file tải lên.")

    # 2. Tạo bản ghi TaskStatus vào PostgreSQL
    task_id = str(uuid.uuid4())
    task_record = TaskStatus(
        id=task_id,
        task_name="process_brd",
        status="STARTED"
    )
    db.add(task_record)
    await db.commit()

    # 3. Publish event lên RabbitMQ
    try:
        await publish_event("brd.uploaded", {
            "task_id": task_id,
            "file_path": file_path, 
            "filename": filename, 
            "project_id": project_id
        })
    except Exception as e:
        logger.error(f"Lỗi khi publish event brd.uploaded: {e}")
        # Dọn dẹp nếu lỗi
        if os.path.exists(file_path):
            os.remove(file_path)
        
        task_record.status = "FAILED"
        task_record.error = str(e)
        await db.commit()
        
        raise HTTPException(status_code=500, detail="Không thể khởi động tiến trình xử lý nền.")

    return {
        "status": "processing",
        "task_id": task_id,
        "message": "BRD upload thành công và đang được xử lý nền (RabbitMQ).",
        "project_id": project_id,
        "filename": filename
    }

@router.get("/brd/status/{task_id}")
async def get_brd_status(task_id: str, db: AsyncSession = Depends(get_db)):
    """
    API endpoint để kiểm tra trạng thái xử lý BRD từ PostgreSQL.
    """
    result = await db.execute(select(TaskStatus).filter(TaskStatus.id == task_id))
    task = result.scalars().first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task không tồn tại")
        
    response = {
        "task_id": task.id,
        "status": task.status,
    }
    
    if task.status == "SUCCESS" and task.result:
        response["result"] = task.result
    elif task.status == "FAILED" and task.error:
        response["error"] = task.error
        
    return response

