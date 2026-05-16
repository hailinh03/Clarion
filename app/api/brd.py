"""
Clarion — BRD Upload API
POST /api/brd/upload  — upload BRD (PDF/Word) → chunk → embed → Qdrant
"""
from fastapi import APIRouter

router = APIRouter()


@router.post("/brd/upload")
async def upload_brd():
    # TODO: implement — parse PDF/Word, chunk 400 token overlap 50,
    #       embed_batch(), qdrant upsert collection: brd_chunks
    return {"status": "not_implemented"}
