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
| `Qwen2.5-72B-Instruct` | HuggingFace | HF Inference API (free tier) | ⭐ Tốt nhất free cho reasoning |
| `meta-llama/Llama-3.3-70B-Instruct` | HuggingFace | HF Inference API (free tier) | ⭐ Mạnh, follow instruction tốt |
| `google/gemma-3-27b-it` | HuggingFace | HF Inference API (free tier) | Tốt cho tiếng Việt |
| `mistralai/Mistral-7B-Instruct-v0.3` | Groq | Groq free tier (nhanh) | Nhẹ hơn nhưng rate limit cao |
| `deepseek-r1-distill-llama-70b` | Groq | Groq free tier | Reasoning tốt |

> **Khuyến nghị hiện tại:** `Qwen2.5-72B-Instruct` qua HuggingFace Inference API hoặc `deepseek-r1-distill-llama-70b` qua Groq (nhanh hơn).

---

## LLM — Sinh task / test case (tác vụ generation)

Prompt rõ ràng, schema cố định → không cần model quá mạnh, ưu tiên **nhanh và rẻ**.

### Free options ⭐
| Model | Nguồn | Ghi chú |
|---|---|---|
| `Qwen2.5-7B-Instruct` | HuggingFace / Groq | Nhanh, đủ dùng cho gen có cấu trúc |
| `meta-llama/Llama-3.1-8B-Instruct` | Groq free | Rất nhanh |
| `gemma-7b-it` | Groq free | Nhẹ, tốt cho JSON output |

---

## Cấu hình LangChain — Switching model dễ dàng

```python
# app/services/llm_provider.py
import os
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

def get_analyze_llm():
    provider = os.getenv("LLM_PROVIDER", "huggingface")
    
    if provider == "anthropic":
        return ChatAnthropic(model="claude-3-5-sonnet-20241022")
    
    elif provider == "openai":
        return ChatOpenAI(model="gpt-4o")
    
    elif provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(model="deepseek-r1-distill-llama-70b")
    
    else:  # huggingface (default free)
        endpoint = HuggingFaceEndpoint(
            repo_id="Qwen/Qwen2.5-72B-Instruct",
            task="text-generation",
            max_new_tokens=2048,
        )
        return ChatHuggingFace(llm=endpoint)

def get_generation_llm():
    """LLM nhẹ hơn cho gen task/test case"""
    provider = os.getenv("LLM_PROVIDER", "huggingface")
    
    if provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(model="llama-3.1-8b-instant")
    
    else:  # huggingface
        endpoint = HuggingFaceEndpoint(
            repo_id="Qwen/Qwen2.5-7B-Instruct",
            task="text-generation",
            max_new_tokens=2048,
        )
        return ChatHuggingFace(llm=endpoint)
```

---

## .env mẫu

```env
# LLM Provider: anthropic | openai | groq | huggingface
LLM_PROVIDER=huggingface

# API Keys (chỉ cần key của provider đang dùng)
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GROQ_API_KEY=                    # free tại console.groq.com
HUGGINGFACE_API_KEY=             # free tại huggingface.co/settings/tokens

# Embedding
EMBEDDING_PROVIDER=local         # local | openai
EMBEDDING_MODEL=BAAI/bge-m3      # dùng local free

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=                  # để trống nếu self-host local

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
