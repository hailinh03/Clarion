"""
Clarion — FastAPI entrypoint
"""
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

# ── Load environment variables ──────────────────────────────────
load_dotenv()

# ── Lifespan: startup / shutdown hooks ──────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup tasks before the server accepts requests."""
    logger.info("🚀 Clarion starting up...")
    logger.info(f"   LLM_PROVIDER      : {os.getenv('LLM_PROVIDER', 'groq')}")
    logger.info(f"   EMBEDDING_PROVIDER: {os.getenv('EMBEDDING_PROVIDER', 'local')}")
    logger.info(f"   EMBEDDING_MODEL   : {os.getenv('EMBEDDING_MODEL', 'BAAI/bge-m3')}")
    logger.info(f"   QDRANT_URL        : {os.getenv('QDRANT_URL', 'http://localhost:6333')}")

    # Initialise Qdrant collections (idempotent — safe to call every startup)
    from app.services.qdrant_client import init_collections
    init_collections()

    # TODO: warm-up local embedding model (SentenceTransformer)

    yield  # ← server is running

    logger.info("🛑 Clarion shutting down...")


# ── FastAPI application ──────────────────────────────────────────
app = FastAPI(
    title="Clarion",
    description=(
        "AI agent tích hợp Jira — tự động review ticket, "
        "sinh technical task và test case trong SDLC."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS (cho Jira plugin / frontend) ───────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # TODO: restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers — sẽ được mount khi implement từng module ────────────
# from app.api.ticket import router as ticket_router
# from app.api.brd import router as brd_router
# app.include_router(ticket_router, prefix="/api", tags=["Ticket"])
# app.include_router(brd_router, prefix="/api", tags=["BRD"])


# ── Health check ─────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check() -> dict:
    """Liveness probe — dùng cho Docker / k8s."""
    return {
        "status": "ok",
        "service": "clarion",
        "version": app.version,
    }


@app.get("/", tags=["System"])
async def root() -> dict:
    return {
        "message": "Welcome to Clarion API",
        "docs": "/docs",
    }
