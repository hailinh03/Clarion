# Clarion — Development Rules

## 1. Rules chung

- Ngôn ngữ code: **Python 3.11+**
- Mọi API endpoint đều dùng **async/await**
- Mọi external call (LLM, embedding, Qdrant, Jira) đều phải có **try/except** và log lỗi rõ ràng
- Không hardcode API key, model name, threshold — luôn đọc từ `.env`
- Mọi function có side effect (ghi DB, gọi API ngoài) phải có unit test mock

---

## 2. LLM Output Rules — QUAN TRỌNG

### Luôn yêu cầu structured JSON output

Mọi LLM call trong Clarion đều phải trả về JSON, không bao giờ free-text.

```python
# Đúng — dùng Pydantic + LangChain structured output
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel

class AnalysisResult(BaseModel):
    score: int
    ambiguous_items: list[AmbiguousItem]
    missing_items: list[MissingItem]

parser = JsonOutputParser(pydantic_object=AnalysisResult)
chain = prompt | llm | parser
```

### Prompt phải có output format rõ ràng

Mọi prompt đều kết thúc bằng instruction format:

```
Trả về JSON hợp lệ theo schema sau, không thêm text ngoài JSON:
{schema}
```

### Validate output trước khi dùng

```python
# Luôn validate bằng Pydantic trước khi trả về
try:
    result = AnalysisResult(**llm_output)
except ValidationError as e:
    logger.error(f"LLM output invalid: {e}")
    # fallback: trả về partial result với flag cần human review
    return AnalysisResult(score=0, needs_review=True, raw_output=llm_output)
```

---

## 3. Embedding Rules

### Không bao giờ mix embedding model

```python
# SAI — dùng 2 model khác nhau, cosine similarity vô nghĩa
ac_vectors = embed_with_openai(ac_list)
tc_vectors = embed_with_bge(tc_list)
similarity = cosine(ac_vectors[0], tc_vectors[0])  # KẾT QUẢ SAI

# ĐÚNG — luôn dùng cùng 1 model
ac_vectors = embed_batch(ac_list)
tc_vectors = embed_batch(tc_list)
```

### Embed theo batch, không embed từng item

```python
# SAI — N lần API call
for text in texts:
    vector = embed(text)  # chậm, tốn quota

# ĐÚNG — 1 lần API call
vectors = embed_batch(texts)
```

### Normalize vector trước khi tính cosine similarity

```python
import numpy as np

def cosine_sim(a: list[float], b: list[float]) -> float:
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
```

---

## 4. Qdrant Rules

### Metadata bắt buộc khi upsert

```python
# Mọi vector upsert đều phải có metadata đầy đủ
qdrant_client.upsert(
    collection_name="approved_tickets",
    points=[PointStruct(
        id=ticket_id,
        vector=embedding,
        payload={
            "ticket_id": ticket_id,
            "project_id": project_id,
            "created_at": datetime.utcnow().isoformat(),
            "sprint": sprint_name,
            "source": "approved_ticket"  # để filter khi search
        }
    )]
)
```

### Luôn filter theo project_id khi search

```python
# SAI — search toàn bộ collection, lẫn data project khác
results = qdrant.search(collection_name="brd_chunks", query_vector=vec)

# ĐÚNG — filter theo project
from qdrant_client.models import Filter, FieldCondition, MatchValue

results = qdrant.search(
    collection_name="brd_chunks",
    query_vector=vec,
    query_filter=Filter(
        must=[FieldCondition(key="project_id", match=MatchValue(value=project_id))]
    ),
    limit=5
)
```

---

## 5. FastAPI Rules

### Response model bắt buộc

```python
# Mọi endpoint đều khai báo response_model
@router.post("/ticket/analyze", response_model=AnalysisResult)
async def analyze_ticket(ticket: TicketInput) -> AnalysisResult:
    ...
```

### Async cho mọi I/O

```python
# SAI — blocking call trong async endpoint
@router.post("/ticket/approve")
async def approve_ticket(ticket: TicketJSON):
    result = sync_llm_call(...)  # block event loop

# ĐÚNG — ghi nhận Task vào Postgres và đẩy heavy task vào RabbitMQ event bus
@router.post("/ticket/approve")
async def approve_ticket(ticket: TicketJSON, db: AsyncSession = Depends(get_db)):
    db.add(TaskStatus(id=f"tech_tasks_{ticket.ticket_id}", task_name="gen_tech_tasks", status="STARTED"))
    await db.commit()
    await publish_event("ticket.approved", ticket.model_dump())
    return {"status": "processing", "ticket_id": ticket.ticket_id}
```

---

## 6. AI Agent Context Rules

> Rules này dành cho AI coding assistant (Cursor, Copilot, Claude) khi sinh code cho project Clarion.

- **Luôn đọc `ARCHITECTURE.md`** trước khi tạo service mới để đảm bảo đúng cấu trúc thư mục
- **Luôn đọc `MODELS.md`** trước khi viết code liên quan đến LLM hoặc embedding — không hardcode model name
- **Luôn dùng Pydantic** cho input/output schema, không dùng plain dict
- **Mọi LangChain chain** phải có `| JsonOutputParser` ở cuối, không dùng raw LLM output
- **Khi sinh test case** phải có trường `ac_ref` mapping về AC/BR nào, để coverage check hoạt động
- **Threshold cosine similarity** đọc từ env `COVERAGE_THRESHOLD`, không hardcode 0.75
- Khi không chắc business logic, **comment `# TODO: confirm with PM`** thay vì tự suy đoán
- Không tạo endpoint mới nếu chưa có schema Pydantic tương ứng trong `schemas/`

---

## 7. Commit Convention

```
feat: thêm tính năng mới
fix: sửa bug
refactor: refactor không thay đổi behavior
test: thêm/sửa test
docs: cập nhật tài liệu
chore: config, dependency
```

Ví dụ:
```
feat: thêm coverage check bằng embedding cosine similarity
fix: sửa lỗi embed_batch trả về sai order khi input rỗng
docs: cập nhật MODELS.md thêm Groq free tier
```
