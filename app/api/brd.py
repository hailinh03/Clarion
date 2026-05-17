"""
Clarion — BRD Upload API
POST /api/brd/upload  — upload BRD (PDF/Word) → chunk → embed → Qdrant
"""
import io
import uuid
from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from fastapi.concurrency import run_in_threadpool

from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger

from app.services.embedding import embed_batch
from app.services.qdrant_client import upsert_brd_chunk

router = APIRouter()


def _parse_and_chunk_file(file_bytes: bytes, filename: str) -> list[dict]:
    """Parse PDF/Word và chunk văn bản, giữ lại thông tin page nếu có thể."""
    chunks = []
    # 400 token tương đương khoảng 1600 ký tự (trung bình 4 char/token)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1600,
        chunk_overlap=200,
    )

    if filename.lower().endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if not page_text or not page_text.strip():
                continue
            page_chunks = text_splitter.split_text(page_text)
            for chunk_text in page_chunks:
                chunks.append({
                    "text": chunk_text,
                    "page": i + 1,
                    "section": "unknown"
                })

    elif filename.lower().endswith((".docx", ".doc")):
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        full_text = "\n".join([p.text for p in doc.paragraphs])
        doc_chunks = text_splitter.split_text(full_text)
        for chunk_text in doc_chunks:
            chunks.append({
                "text": chunk_text,
                "page": 0,
                "section": "unknown"
            })
            
    elif filename.lower().endswith(".txt"):
        full_text = file_bytes.decode("utf-8")
        doc_chunks = text_splitter.split_text(full_text)
        for chunk_text in doc_chunks:
            chunks.append({
                "text": chunk_text,
                "page": 0,
                "section": "unknown"
            })
    else:
        raise ValueError(f"Định dạng file không hỗ trợ: {filename}")

    return chunks


@router.post("/brd/upload")
async def upload_brd(
    file: UploadFile = File(...),
    project_id: str = Form(...),
):
    """
    API endpoint để upload tài liệu BRD.
    Hỗ trợ PDF, DOCX, TXT. Tài liệu sẽ được parse, chia nhỏ (chunk),
    nhúng vector (embed_batch) và đưa vào Qdrant brd_chunks.
    """
    filename = file.filename or "unknown_file"
    file_bytes = await file.read()
    
    # 1. Parse & Chunk
    try:
        chunks = _parse_and_chunk_file(file_bytes, filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Lỗi khi parse file {filename}: {e}")
        raise HTTPException(status_code=500, detail="Lỗi khi xử lý file tải lên.")

    if not chunks:
        return {"status": "success", "message": "File không có nội dung text", "chunks_processed": 0}

    # 2. Embed & Upsert (đưa vào threadpool để không block loop vì gọi embedding local)
    def process_and_upsert():
        # Gọi embed theo batch như RULES.md quy định
        texts = [c["text"] for c in chunks]
        try:
            vectors = embed_batch(texts)
        except Exception as e:
            logger.error(f"Lỗi embedding cho file {filename}: {e}")
            raise

        for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
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

    try:
        await run_in_threadpool(process_and_upsert)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Lỗi khi lưu trữ vector vào Qdrant.")

    return {
        "status": "success",
        "message": "BRD upload và xử lý thành công.",
        "project_id": project_id,
        "filename": filename,
        "chunks_processed": len(chunks)
    }

