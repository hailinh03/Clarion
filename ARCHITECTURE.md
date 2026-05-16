# Clarion — Architecture & Tech Stack

## Tech Stack

### Backend
| Layer | Tech | Lý do |
|---|---|---|
| API Framework | **FastAPI** | Async native, tự gen OpenAPI docs, dễ tích hợp webhook Jira |
| AI Orchestration | **LangChain** | Chain prompt, quản lý memory, tích hợp nhiều LLM provider |
| Vector Database | **Qdrant** | Self-hostable, hỗ trợ filter theo metadata, free tier tốt |
| Task Queue | **Celery + Redis** | Xử lý gen task/test case async sau khi approve |

### Embedding Model
| Dùng cho | Model | Chiều | Nguồn |
|---|---|---|---|
| BRD chunks, ticket, AC, test case | `text-embedding-3-large` | 3072 | OpenAI API |
| Thay thế free/self-host | `BAAI/bge-large-en-v1.5` | 1024 | HuggingFace |

> **Quan trọng:** Tất cả dữ liệu trong Clarion (BRD, ticket, AC, test case) dùng **cùng 1 embedding model** để đảm bảo vector space đồng nhất. Cosine similarity chỉ có nghĩa khi 2 vector từ cùng 1 model.

### LLM
| Tác vụ | Model ưu tiên | Model free thay thế |
|---|---|---|
| Phân tích ticket, detect mơ hồ, suggest cải thiện | `claude-3-5-sonnet` / `gpt-4o` | `Qwen2.5-72B-Instruct` (HF) |
| Sinh tech task, sinh test case | `claude-3-5-haiku` / `gpt-4o-mini` | `Qwen2.5-7B-Instruct` (HF) |

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
    ↓
[Bước A] Embed ticket đã approve → Qdrant upsert (collection: approved_tickets)
    ↓
[Bước B] Parse ticket → TicketJSON {
    title, user_story, ac_list, business_rules, edge_cases
}
    ↓
[Song song qua Celery]
    ├── Task: gen_tech_tasks(ticket_json)
    │       ↓ LLM → JSON array of TechTask
    │       ↓ Jira API: tạo sub-task
    │
    └── Task: gen_test_cases(ticket_json)
            ↓ LLM → JSON array of TestCase (có ac_ref)
            ↓ coverage_check(ac_list, test_cases)
                ├── embed_batch(ac_list)
                ├── embed_batch(test_case_titles)
                ├── cosine_similarity_matrix()
                ├── threshold = 0.75
                └── gap_report: [AC chưa được cover]
            ↓ Jira API: attach test case + gap report vào ticket
```

---

## Cấu trúc thư mục

```
clarion/
├── app/
│   ├── main.py                  # FastAPI entrypoint
│   ├── api/
│   │   ├── ticket.py            # POST /ticket/analyze, /ticket/approve
│   │   └── brd.py               # POST /brd/upload
│   ├── services/
│   │   ├── embedding.py         # embed_single, embed_batch
│   │   ├── retrieval.py         # search Qdrant, build context
│   │   ├── analyzer.py          # LLM phân tích ticket
│   │   ├── task_generator.py    # LLM sinh tech task
│   │   ├── testcase_generator.py# LLM sinh test case
│   │   └── coverage.py          # cosine similarity, gap report
│   ├── chains/
│   │   ├── analyze_chain.py     # LangChain chain cho phân tích
│   │   ├── task_chain.py
│   │   └── testcase_chain.py
│   ├── schemas/
│   │   ├── ticket.py            # Pydantic models
│   │   ├── analysis.py
│   │   ├── task.py
│   │   └── testcase.py
│   ├── prompts/                 # Prompt templates (xem PROMPT_TEMPLATES.md)
│   └── workers/
│       └── celery_app.py        # Async task processing
├── tests/
├── .env
├── OVERVIEW.md
├── ARCHITECTURE.md
├── MODELS.md
├── RULES.md
└── PROMPT_TEMPLATES.md
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
