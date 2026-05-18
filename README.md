# Clarion 🔍

> **AI agent tích hợp Jira** — tự động review ticket, sinh technical task và test case trong SDLC.

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![LangChain](https://img.shields.io/badge/LangChain-0.3-orange)](https://langchain.com)
[![Qdrant](https://img.shields.io/badge/Qdrant-local-purple?logo=qdrant)](https://qdrant.tech)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

---

## 🤖 AI Agent Guide
If you are an AI coding assistant (e.g. Cursor, Copilot, Antigravity) working on this repository, please read and adhere to the guidelines and specifications stored in the [context/](file:///home/ubuntu/innovation/Clarion/context) directory:
*   [context/ARCHITECTURE.md](file:///home/ubuntu/innovation/Clarion/context/ARCHITECTURE.md): Comprehensive system architecture, database integrations (PostgreSQL & Qdrant), and background task flows.
*   [context/MODELS.md](file:///home/ubuntu/innovation/Clarion/context/MODELS.md): Pre-configured LLM models, parameters, and recommended providers (e.g. Google Gemini).
*   [context/RULES.md](file:///home/ubuntu/innovation/Clarion/context/RULES.md): Coding rules, strict formatting conventions, and behavior patterns.
*   [context/OVERVIEW.md](file:///home/ubuntu/innovation/Clarion/context/OVERVIEW.md): Overview of Clarion features and project scope.

---

## Mục tiêu

Clarion giúp PM / BA viết Jira ticket chất lượng hơn và tự động hóa công việc lặp lại của Dev + QA:

| Tính năng | Mô tả |
|---|---|
| 🔍 **Review ticket** | Phát hiện AC mơ hồ, thiếu business rule, thiếu edge case, thiếu error handling |
| ✍️ **Suggest cải thiện** | Gợi ý rewrite AC, bổ sung rule còn thiếu, chấm điểm chất lượng 0–100 |
| 🛠️ **Sinh technical task** | Breakdown ticket thành sub-task có estimate cho Dev |
| 🧪 **Sinh test case** | Sinh TC happy path + negative + edge case từ AC/BR |
| 📊 **Coverage check** | Kiểm tra test case đã cover hết AC chưa, báo gap |

---

## Tech Stack

| Layer | Công nghệ | Ghi chú |
|---|---|---|
| API | **FastAPI** + Uvicorn | Async, tự gen OpenAPI docs |
| AI Orchestration | **LangChain** | Chain, parser, multi-provider LLM |
| LLM (free) | **Groq** — `openai/gpt-oss-120b` | Free tier, reasoning tốt |
| Embedding (free) | **BAAI/bge-m3** local | Multilingual Anh+Việt, dim=1024 |
| Vector DB | **Qdrant** Docker local | Self-host, filter theo metadata |
| Task Queue | **Celery + Redis** | Xử lý gen task/TC async |

> **100% free để chạy:** Groq free tier + local embedding + Qdrant local Docker. Không cần credit card.

---

## Cấu trúc thư mục

```
clarion/
├── app/
│   ├── main.py                   # FastAPI entrypoint, lifespan hooks
│   ├── api/
│   │   ├── ticket.py             # POST /api/ticket/analyze, /ticket/approve
│   │   └── brd.py                # POST /api/brd/upload
│   ├── services/
│   │   ├── embedding.py          # ✅ BAAI/bge-m3 local, singleton, embed_batch/single
│   │   ├── qdrant_client.py      # ✅ Kết nối Qdrant, init 3 collections, upsert/search
│   │   ├── retrieval.py          # ✅ search context từ Qdrant
│   │   ├── analyzer.py           # ✅ LLM phân tích ticket
│   │   ├── task_generator.py     # ✅ LLM sinh tech task
│   │   ├── testcase_generator.py # 🔲 LLM sinh test case
│   │   └── coverage.py           # 🔲 cosine similarity, gap report
│   ├── chains/
│   │   ├── analyze_chain.py      # ✅ ChatPromptTemplate | Groq | JsonOutputParser
│   │   ├── task_chain.py         # ✅ chain sinh tech task
│   │   └── testcase_chain.py     # 🔲 chain sinh test case
│   ├── schemas/
│   │   ├── ticket.py             # ✅ TicketInput, TicketJSON
│   │   ├── analysis.py           # ✅ AnalysisResult, AmbiguousItem, MissingItem
│   │   ├── task.py               # ✅ TechTask
│   │   └── testcase.py           # ✅ TestCase
│   ├── prompts/
│   │   ├── analyze_ticket.py     # ✅ System + user prompt cho phân tích
│   │   ├── gen_tech_task.py      # ✅ Prompt sinh tech task
│   │   └── gen_testcase.py       # ✅ Prompt sinh test case
│   └── workers/
│       ├── celery_app.py         # ✅ Celery + Redis config
│       └── tasks.py              # ✅ task_gen_tech_tasks, task_gen_test_cases
├── tests/
│   ├── test_main.py              # ✅ Health check smoke test
│   ├── test_embedding.py         # ✅ 8 test cases, mock model
│   ├── test_qdrant_client.py     # ✅ 15 test cases, mock Qdrant
│   └── test_analyze_chain.py     # ✅ 10 test cases, mock LLM
├── .env.example                  # Template cấu hình
├── docker-compose.yml            # Qdrant + Redis
└── requirements.txt
```

> ✅ Implemented &nbsp;|&nbsp; 🔲 Scaffold (TODO)

---

## Qdrant Collections

| Collection | Dùng cho | Metadata |
|---|---|---|
| `brd_chunks` | BRD chunks upload offline | source, filename, page, section, project_id |
| `approved_tickets` | Ticket đã PM approve | ticket_id, project_id, created_at, sprint |
| `test_cases` | Test case đã sinh | ticket_id, ac_ref, type (happy\|negative\|edge) |

> Tất cả collection dùng **cùng 1 embedding model** (bge-m3, dim=1024) để cosine similarity có nghĩa.

---

## Cài đặt & Chạy

### Yêu cầu

- Python 3.11+
- Docker Desktop (để chạy Qdrant + Redis)
- [Groq API key](https://console.groq.com) (free)

### 1. Clone và cài dependencies

```bash
git clone https://github.com/hailinh03/Clarion.git
cd Clarion

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Cấu hình `.env`

```bash
cp .env.example .env
```

Mở `.env`, chỉnh sửa:

```env
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here      # Lấy tại console.groq.com (free)

EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=BAAI/bge-m3         # Download tự động lần đầu (~1.5GB)

QDRANT_URL=http://localhost:6333    # Chạy qua Docker bên dưới
QDRANT_API_KEY=                     # Để trống khi self-host
```

### 3. Khởi động Qdrant + Redis

```bash
docker compose up -d
```

Kiểm tra Qdrant dashboard: http://localhost:6333/dashboard

### 4. Chạy API server

```bash
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

---

## API Endpoints

| Method | Endpoint | Mô tả | Status |
|---|---|---|---|
| `GET` | `/health` | Liveness probe | ✅ |
| `POST` | `/api/ticket/analyze` | Phân tích ticket, trả về AnalysisResult | ✅ |
| `POST` | `/api/ticket/approve` | Approve ticket, kích hoạt gen task + TC | ✅ |
| `POST` | `/api/brd/upload` | Upload BRD PDF/Word → chunk → embed → Qdrant | ✅ |

---

## Sample Data

Thư mục `sample_data/` chứa dữ liệu mẫu để test end-to-end mà không cần tài liệu thật từ dự án.

### `sample_data/BRD_Authentication_Sample.md`

BRD mẫu đầy đủ cho module **Authentication & User Management**, gồm:

| Section | Nội dung |
|---|---|
| Business Rules | 19 rules (BR-ACC, BR-PWD, BR-SES, BR-OTP) |
| Acceptance Criteria | 27 AC cho 4 chức năng (Đăng ký, Đăng nhập, Quên mật khẩu, Refresh Token) |
| Validation Rules | Đầy đủ field validation + error message |
| Edge Cases | 13 edge case thực tế (double submit, clock skew, token reuse…) |
| Error Handling | Bảng HTTP status code + response format |

**Dùng để test flow BRD upload:**

```bash
# 1. Khởi động server
uvicorn app.main:app --reload

# 2. Upload BRD sample (khi endpoint /api/brd/upload được implement)
curl -X POST http://localhost:8000/api/brd/upload \
  -F "file=@sample_data/BRD_Authentication_Sample.md" \
  -F "project_id=CLARION-MVP"
```

**Dùng để test phân tích ticket:**

```json
// POST /api/ticket/analyze — sample payload
{
  "ticket_id": "AUTH-001",
  "title": "Đăng ký tài khoản bằng email",
  "user_story": "As a new user, I want to register with email so that I can access the system.",
  "acceptance_criteria": [
    "AC1: Hệ thống cho phép đăng ký với email và password",
    "AC2: Gửi OTP xác nhận sau khi đăng ký"
  ],
  "business_rules": [
    "BR1: Mỗi email chỉ đăng ký 1 tài khoản",
    "BR2: Mật khẩu tối thiểu 8 ký tự"
  ],
  "project_id": "CLARION-MVP"
}
```

> Clarion sẽ so sánh ticket này với BRD đã upload, phát hiện các AC còn thiếu (error handling, edge case) và suggest cải thiện dựa trên Business Rules trong BRD.

---

## Chạy Tests

```bash
# Chạy tất cả (không cần Qdrant server, không cần Groq key — toàn bộ đều mock)
pytest tests/ -v

# Chạy từng module
pytest tests/test_embedding.py -v
pytest tests/test_qdrant_client.py -v
pytest tests/test_analyze_chain.py -v
```

**Tất cả tests đều mock external services** (SentenceTransformer, QdrantClient, Groq) → chạy được trong CI/CD không cần tài nguyên thật.

---

## Data Flow

### Flow 1 — Phân tích ticket (online)

```
POST /api/ticket/analyze
    │
    ├─► embed(ticket_text)                   # bge-m3 local
    │
    ├─► Qdrant search (brd_chunks + tickets) # filter by project_id
    │       └─► top-5 context chunks
    │
    ├─► build prompt (ticket + context)
    │
    └─► Groq LLM → JSON → AnalysisResult {
            score, ambiguous_items,
            missing_items, improved_ac
        }
```

### Flow 2 — Sau khi approve (async Celery)

```
POST /api/ticket/approve
    │
    ├─► embed + upsert Qdrant (approved_tickets)
    │
    └─► Celery tasks (song song):
            ├─► gen_tech_tasks → TechTask[] → Jira sub-tasks
            └─► gen_test_cases → TestCase[]
                    └─► coverage_check (cosine sim AC ↔ TC)
                            └─► gap_report: AC chưa cover
```

---

## Nguyên tắc thiết kế

- **1 embedding model duy nhất** cho toàn hệ thống — không mix model
- **Structured JSON output** — mọi LLM call đều qua `JsonOutputParser` + Pydantic validation
- **Fail gracefully** — nếu LLM output lỗi → trả về `needs_review=True`, không crash
- **Filter theo project_id** khi search Qdrant — tránh lẫn data giữa các project
- **Model name không hardcode** — luôn đọc từ `.env`

---

## Lộ trình phát triển

- [x] Scaffold cấu trúc thư mục
- [x] `embedding.py` — BAAI/bge-m3 local, singleton, normalize
- [x] `qdrant_client.py` — kết nối, init 3 collections, upsert/search
- [x] `analyze_chain.py` — Groq + LangChain + JsonOutputParser
- [x] `retrieval.py` — build context từ Qdrant cho prompt
- [x] `api/ticket.py` — implement endpoint analyze + approve
- [x] `api/brd.py` — upload, chunk, embed, upsert BRD
- [x] `task_chain.py` + `task_generator.py` — gen tech task
- [ ] `testcase_chain.py` + `testcase_generator.py` — gen test case
- [ ] `coverage.py` — cosine similarity + gap report
- [ ] Jira webhook integration
- [ ] Dashboard chất lượng ticket theo sprint

---

## Tài liệu nội bộ

| File | Nội dung |
|---|---|
| [`OVERVIEW.md`](OVERVIEW.md) | Mục tiêu, luồng hoạt động, actors |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Tech stack, data flow, schema JSON, cấu trúc thư mục |
| [`MODELS.md`](MODELS.md) | Danh sách model embedding + LLM, hướng dẫn switching |
| [`RULES.md`](RULES.md) | Coding rules bắt buộc cho toàn project |
| [`PROMPT_TEMPLATES.md`](PROMPT_TEMPLATES.md) | Prompt templates đầy đủ cho 3 tác vụ chính |

---

## License

MIT © 2026 Clarion Team
