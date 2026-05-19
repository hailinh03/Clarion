# Clarion — Model Reference

## Nguyên tắc chọn model

- **1 embedding model duy nhất** cho toàn bộ hệ thống (BRD, ticket, AC, test case) — đảm bảo vector space đồng nhất
- **LLM mạnh** cho tác vụ phân tích phức tạp (detect ambiguity, suggest AC)
- **LLM nhanh/nhỏ** cho tác vụ generation có cấu trúc (gen task, gen test case) — prompt rõ ràng hơn nên không cần model lớn

---

## Embedding Model

### Lựa chọn 1 — Có budget (recommended)
| Model | Chiều | Cost | Ghi chú |
|---|---|---|---|
| `text-embedding-3-large` | 3072 | $0.13/1M token | Chất lượng tốt nhất, OpenAI |
| `text-embedding-3-small` | 1536 | $0.02/1M token | Tiết kiệm hơn, vẫn tốt |

### Lựa chọn 2 — Free / Self-host ⭐ (dùng khi không có budget)
| Model | Chiều | Cách chạy | Chất lượng |
|---|---|---|---|
| `BAAI/bge-large-en-v1.5` | 1024 | HuggingFace / local | ⭐⭐⭐⭐ Tốt nhất trong free |
| `BAAI/bge-m3` | 1024 | HuggingFace / local | ⭐⭐⭐⭐ Multilingual (Anh + Việt) |
| `sentence-transformers/all-MiniLM-L6-v2` | 384 | HuggingFace / local | ⭐⭐⭐ Nhẹ, nhanh, đủ dùng |

> **Khuyến nghị hiện tại:** Dùng `BAAI/bge-m3` nếu ticket có tiếng Việt lẫn tiếng Anh.

```python
# Cách dùng bge-m3 local
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-m3")
vectors = model.encode(texts, normalize_embeddings=True)
```

---

## LLM — Phân tích ticket (tác vụ nặng)

Cần reasoning tốt, hiểu business context, output JSON chính xác.

### Có budget
| Model | API | Ghi chú |
|---|---|---|
| `claude-3-5-sonnet-20241022` | Anthropic | Tốt nhất cho structured analysis |
| `gpt-4o` | OpenAI | Tốt, phổ biến |

### Free options ⭐
| Model | Nguồn | Cách truy cập | Ghi chú |
|---|---|---|---|
| `gemini-2.5-flash` | Google | Google AI Studio (free tier) | ⭐ **Mặc định & Khuyến nghị chính thức** — Cực nhanh, hỗ trợ JSON cực chuẩn, context lớn |
| `Qwen2.5-72B-Instruct` | HuggingFace | HF Inference API (free tier) | ⭐ Tốt nhất free cho reasoning |
| `meta-llama/Llama-3.3-70B-Instruct` | HuggingFace | HF Inference API (free tier) | ⭐ Mạnh, follow instruction tốt |
| `openai/gpt-oss-120b` | Groq | Groq free tier | Reasoning tốt |

> **Khuyến nghị hiện tại:** `gemini-2.5-flash` qua Google AI Studio API (mặc định của dự án) hoặc `openai/gpt-oss-120b` qua Groq.

---

## LLM — Sinh task / test case (tác vụ generation)

Prompt rõ ràng, schema cố định → không cần model quá mạnh, ưu tiên **nhanh và rẻ**.

### Free options ⭐
| Model | Nguồn | Ghi chú |
|---|---|---|
| `gemini-2.5-flash` | Google free | ⭐ **Mặc định & Khuyến nghị chính thức** — Rất nhanh, xuất JSON chuẩn xác |
| `Qwen2.5-7B-Instruct` | HuggingFace / Groq | Nhanh, đủ dùng cho gen có cấu trúc |
| `meta-llama/Llama-3.1-8B-Instruct` | Groq free | Rất nhanh |
| `openai/gpt-oss-120b` | Groq free | Rất mạnh, support cấu trúc tốt |

---

## Cấu hình LangChain — Switching model dễ dàng (xem app/chains/*_chain.py)

```python
# Việc xây dựng LLM được tích hợp trực tiếp trong các chain: app/chains/analyze_chain.py, app/chains/task_chain.py, app/chains/testcase_chain.py
# Cho phép cấu hình qua các biến môi trường: LLM_PROVIDER, ANALYZE_LLM_MODEL, GENERATION_LLM_MODEL

# Ví dụ logic xây dựng LLM:
def _build_llm():
    provider = os.getenv("LLM_PROVIDER", "groq").lower()
    model = os.getenv("ANALYZE_LLM_MODEL", "openai/gpt-oss-120b")
    
    if provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(model=model, temperature=0, max_tokens=4096)
        
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, temperature=0, max_tokens=4096)
        
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, temperature=0, max_tokens=4096)
        
    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model, temperature=0)
```

---

## .env mẫu

```env
# LLM Config
LLM_PROVIDER=groq
ANALYZE_LLM_MODEL=openai/gpt-oss-120b
GENERATION_LLM_MODEL=openai/gpt-oss-120b

# API Keys (chỉ cần key của provider đang dùng)
GROQ_API_KEY=gsk_your_key_here
# ANTHROPIC_API_KEY=
# OPENAI_API_KEY=
# GOOGLE_API_KEY=

# Embedding
EMBEDDING_PROVIDER=local         # local | openai
EMBEDDING_MODEL=BAAI/bge-m3      # dùng local free

# Qdrant Vector DB
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=                  # để trống nếu self-host local

# Task state & Queue (PostgreSQL & RabbitMQ)
CELERY_BROKER_URL=amqp://guest:guest@localhost:5672//
DATABASE_URL=postgresql+asyncpg://postgres:postgrespassword@localhost:5432/clarion

# Coverage check
COVERAGE_THRESHOLD=0.75
```

---

## Lộ trình nâng cấp model

```
Giai đoạn 1 (MVP - free):
  Embedding:  BAAI/bge-m3 (local)
  Analyze:    Qwen2.5-72B qua HuggingFace hoặc Groq
  Generate:   Qwen2.5-7B qua Groq

Giai đoạn 2 (có budget nhỏ):
  Embedding:  text-embedding-3-small (OpenAI, rẻ)
  Analyze:    claude-3-5-haiku hoặc gpt-4o-mini
  Generate:   claude-3-5-haiku

Giai đoạn 3 (production):
  Embedding:  text-embedding-3-large
  Analyze:    claude-3-5-sonnet
  Generate:   claude-3-5-haiku
```
