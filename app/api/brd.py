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
    """Parse PDF/Word/MD và chunk văn bản, giữ lại thông tin page và section (heading)."""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1600,
        chunk_overlap=200,
    )
    
    raw_blocks = []
    current_section = "unknown"
    current_page = 1

    if filename.lower().endswith(".pdf"):
        from pypdf import PdfReader
        import re
        reader = PdfReader(io.BytesIO(file_bytes))
        for i, page in enumerate(reader.pages):
            current_page = i + 1
            page_text = page.extract_text(extraction_mode="layout")
            if not page_text or not page_text.strip():
                continue
            
            lines = page_text.split('\n')
            current_block_lines = []
            for line in lines:
                stripped = line.strip()
                # Phát hiện heading markdown hoặc heading dạng "1. Overview"
                if stripped.startswith(("# ", "## ", "### ")) or re.match(r"^[0-9]+(\.[0-9]+)*\s+[A-Z]", stripped):
                    if current_block_lines:
                        raw_blocks.append({"text": "\n".join(current_block_lines), "page": current_page, "section": current_section})
                        current_block_lines = []
                    current_section = stripped.lstrip("#").strip()
                current_block_lines.append(line)
            
            if current_block_lines:
                raw_blocks.append({"text": "\n".join(current_block_lines), "page": current_page, "section": current_section})

    elif filename.lower().endswith((".docx", ".doc")):
        from docx import Document
        from docx.text.paragraph import Paragraph
        from docx.table import Table
        
        doc = Document(io.BytesIO(file_bytes))
        
        for element in doc.element.body:
            if element.tag.endswith('p'):
                p = Paragraph(element, doc)
                
                # Detect page break in paragraph
                for run in p.runs:
                    xml = run._element.xml
                    if 'w:br' in xml and 'type="page"' in xml:
                        current_page += 1
                    elif 'w:lastRenderedPageBreak' in xml:
                        current_page += 1
                        
                style_name = p.style.name if p.style else ""
                if style_name.startswith('Heading'):
                    current_section = p.text.strip()
                    
                if p.text.strip():
                    raw_blocks.append({"text": p.text, "page": current_page, "section": current_section})
                    
            elif element.tag.endswith('tbl'):
                table = Table(element, doc)
                table_text = []
                for row in table.rows:
                    row_data = [cell.text.replace('\n', ' ').strip() for cell in row.cells]
                    table_text.append(" | ".join(row_data))
                raw_blocks.append({"text": "\n".join(table_text), "page": current_page, "section": current_section})
            
    elif filename.lower().endswith((".txt", ".md")):
        full_text = file_bytes.decode("utf-8")
        lines = full_text.split('\n')
        current_block_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(("# ", "## ", "### ")):
                if current_block_lines:
                    raw_blocks.append({"text": "\n".join(current_block_lines), "page": current_page, "section": current_section})
                    current_block_lines = []
                current_section = stripped.lstrip("#").strip()
            current_block_lines.append(line)
        if current_block_lines:
            raw_blocks.append({"text": "\n".join(current_block_lines), "page": current_page, "section": current_section})
    else:
        raise ValueError(f"Định dạng file không hỗ trợ: {filename}")

    # Gộp các block cùng (page, section) trước khi split
    aggregated = {}
    for block in raw_blocks:
        key = (block["page"], block["section"])
        if key not in aggregated:
            aggregated[key] = []
        aggregated[key].append(block["text"])

    chunks = []
    for (page, section), texts in aggregated.items():
        combined_text = "\n\n".join(texts)
        if not combined_text.strip():
            continue
            
        # Nối section vào đầu để bảo toàn ngữ cảnh cho LLM
        context_text = f"[{section}]\n{combined_text}"
        
        split_chunks = text_splitter.split_text(context_text)
        for c in split_chunks:
            chunks.append({
                "text": c,
                "page": page,
                "section": section
            })

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

