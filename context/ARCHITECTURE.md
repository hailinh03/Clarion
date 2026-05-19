# Clarion — Architecture & Tech Stack

## Tech Stack

### Backend
| Layer | Tech | Lý do |
|---|---|---|
| API Framework | **FastAPI** | Async native, tự gen OpenAPI docs, dễ tích hợp webhook Jira |
| Database | **PostgreSQL** | Lưu trữ trạng thái và kết quả của các background task qua SQLAlchemy asyncpg |
| AI Orchestration | **LangChain** | Chain prompt, quản lý memory, tích hợp nhiều LLM provider |
| Vector Database | **Qdrant** | Self-hostable, hỗ trợ filter theo metadata, free tier tốt |
| Task Queue | **RabbitMQ** (via `aio-pika`) | Hàng đợi tin nhắn xử lý các tác vụ nền bất đồng bộ hiệu năng cao |

### Embedding Model
| Dùng cho | Model | Chiều | Nguồn |
|---|---|---|---|
| BRD chunks, ticket, AC, test case | `text-embedding-3-large` | 3072 | OpenAI API |
| Thay thế free/self-host | `BAAI/bge-large-en-v1.5` | 1024 | HuggingFace |

> **Quan trọng:** Tất cả dữ liệu trong Clarion (BRD, ticket, AC, test case) dùng **cùng 1 embedding model** để đảm bảo vector space đồng nhất. Cosine similarity chỉ có nghĩa khi 2 vector từ cùng 1 model.

### LLM
| Tác vụ | Model ưu tiên | Model free thay thế |
|---|---|---|
| Phân tích ticket, detect mơ hồ, suggest cải thiện | `claude-3-5-sonnet` / `gpt-4o` | `openai/gpt-oss-120b` (Groq) |
| Sinh tech task, sinh test case | `claude-3-5-haiku` / `gpt-4o-mini` | `openai/gpt-oss-120b` (Groq) |

> Xem chi tiết model free tại `MODELS.md`

---

## Qdrant Collections

```
qdrant/
├── brd_chunks          # BRD được chunk + embed (offline, upload 1 lần)
│   └── metadata: { source, filename, page, section, project_id }
│
├── approved_tickets    # Ticket đã approve, embed toàn bộ nội dung
│   └── metadata: { ticket_id, project_id, created_at, sprint }
│
└── test_cases          # Test case đã sinh (để tái sử dụng sau này)
    └── metadata: { ticket_id, ac_ref, type: happy|negative|edge }
```

---

## Data Flow Chi Tiết

### Flow 1 — Offline: Chuẩn bị BRD

```
Upload BRD (PDF/Word/Confluence)
    ↓
Parse text → chunk 400 token, overlap 50 token
    ↓
embed_batch(chunks) → text-embedding-3-large
    ↓
Qdrant upsert → collection: brd_chunks
    (metadata: source, section, project_id)
```

### Flow 2 — Online: Phân tích ticket khi PM viết

```
Jira webhook → POST /api/ticket/analyze
    ↓
ticket_text = title + description + AC (raw)
    ↓
ticket_vector = embed(ticket_text)              # 1 lần embed
    ↓
context_chunks = qdrant.search(
    vector=ticket_vector,
    collection=["brd_chunks", "approved_tickets"],
    top_k=5,
    filter={ project_id: ... }
)
    ↓
prompt = build_analyze_prompt(ticket, context_chunks)
    ↓
llm_response = LLM.invoke(prompt)              # structured JSON output
    ↓
return AnalysisResult {
    score: int,                                 # 0-100
    ambiguous_items: [{ field, issue, suggestion }],
    missing_items: [{ type, description }],
    improved_ac: [string],
}
```

### Flow 3 — Online: Sau khi PM approve

```
PM bấm Approve → POST /api/ticket/approve
    │
    ├─► [Bước A] Embed ticket đã approve → Qdrant upsert (collection: approved_tickets)
    │
    ├─► [Bước B] Ghi nhận 2 bản ghi TaskStatus (gen_tech_tasks & gen_test_cases) ở trạng thái 'STARTED' vào PostgreSQL
    │
    └─► [Bước C] Publish event 'ticket.approved' lên RabbitMQ
            │
            ├─► Consumer: handle_tech_tasks
            │       └─► LLM gen_tech_tasks → cập nhật Postgres thành SUCCESS/FAILED (kèm JSON TechTask)
            │
            └─► Consumer: handle_test_cases
                    ├─► LLM gen_test_cases
                    ├─► coverage_check(ac_list, test_cases, br_list, ec_list)
                    │       ├── embed_batch(ac_list)
                    │       ├── embed_batch(test_case_titles)
                    │       ├── cosine_similarity_matrix()
                    │       ├── threshold (đọc từ env COVERAGE_THRESHOLD, default 0.75)
                    │       └── gap_report: AC/BR/EC chưa được cover
                    ├─► Embed & Upsert các TestCase được sinh vào Qdrant (test_cases)
                    └─► Cập nhật Postgres thành SUCCESS/FAILED (kèm JSON TestCase & Coverage Report)
```

---

## Cấu trúc thư mục

```
clarion/
├── app/
│   ├── main.py                  # FastAPI entrypoint, lifespan hooks
│   ├── api/
│   │   ├── ticket.py            # POST /api/ticket/analyze, /ticket/approve, GET /ticket/status/{ticket_id}
│   │   └── brd.py               # POST /api/brd/upload, GET /brd/status/{task_id}
│   ├── db/
│   │   ├── database.py          # Cấu hình SQLAlchemy async session & engine (PostgreSQL)
│   │   └── models.py            # Định nghĩa bảng task_status lưu trạng thái tác vụ nền
│   ├── services/
│   │   ├── embedding.py         # embed_single, embed_batch (SentenceTransformer local)
│   │   ├── qdrant_client.py     # kết nối Qdrant, init collections, upsert & search
│   │   ├── rabbitmq_client.py   # kết nối và publish_event lên RabbitMQ
│   │   ├── retrieval.py         # search Qdrant, build context cho LLM prompt
│   │   ├── analyzer.py          # LLM phân tích ticket
│   │   ├── brd_processor.py     # parsing (PDF, DOCX, TXT) và chunking BRD
│   │   ├── task_generator.py    # LLM sinh tech task
│   │   ├── testcase_generator.py# LLM sinh test case
│   │   └── coverage.py          # tính cosine similarity giữa AC/BR/EC và test case, xuất gap report
│   ├── chains/
│   │   ├── analyze_chain.py     # LangChain chain cho phân tích ticket (ambiguity, missing items)
│   │   ├── task_chain.py        # LangChain chain sinh tech task
│   │   └── testcase_chain.py    # LangChain chain sinh test case
│   ├── schemas/
│   │   ├── ticket.py            # Pydantic models cho input ticket
│   │   ├── analysis.py          # Pydantic models cho kết quả phân tích
│   │   ├── task.py              # Pydantic models cho TechTask
│   │   └── testcase.py          # Pydantic models cho TestCase
│   ├── prompts/                 # Prompt templates (xem PROMPT_TEMPLATES.md)
│   └── workers/
│       └── consumer.py          # RabbitMQ event consumer lắng nghe events & xử lý background jobs
├── tests/                       # Thư mục unit tests (mock external services)
├── .env.example                 # Template cấu hình các biến môi trường
├── docker-compose.yml           # Định nghĩa các container service: Qdrant, RabbitMQ, PostgreSQL
└── requirements.txt             # Định nghĩa dependencies của dự án
```

---

## Schema chính

### TicketJSON (input chuẩn hóa)
```json
{
  "ticket_id": "PROJ-123",
  "title": "string",
  "user_story": "As a... I want... So that...",
  "acceptance_criteria": ["AC1: ...", "AC2: ..."],
  "business_rules": ["BR1: ..."],
  "edge_cases": ["EC1: ..."],
  "project_id": "string"
}
```

### AnalysisResult (output phân tích)
```json
{
  "score": 72,
  "ambiguous_items": [
    { "field": "AC2", "issue": "Không rõ format password", "suggestion": "Thêm: tối thiểu 1 ký tự đặc biệt" }
  ],
  "missing_items": [
    { "type": "error_handling", "description": "Chưa có AC cho trường hợp server timeout" }
  ],
  "improved_ac": ["AC1: ...", "AC2: ..."]
}
```

### TechTask (output gen task)
```json
{
  "title": "string",
  "type": "BE | FE | DB | DevOps | Testing",
  "description": "string",
  "estimate_hours": 4,
  "ac_ref": "AC1"
}
```

### TestCase (output gen test case)
```json
{
  "id": "TC-001",
  "title": "string",
  "type": "happy | negative | edge",
  "ac_ref": "AC1",
  "precondition": "string",
  "steps": ["step1", "step2"],
  "expected_result": "string"
}
```
