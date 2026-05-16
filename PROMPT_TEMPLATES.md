# Clarion — Prompt Templates

Các prompt này được dùng trong LangChain chains. Biến trong {curly_braces} là input động.

---

## 1. Prompt phân tích ticket

File: app/prompts/analyze_ticket.py
Chain: app/chains/analyze_chain.py
Model: LLM mạnh (Qwen2.5-72B / Claude Sonnet)

### System prompt

```
Bạn là một Business Analyst AI chuyên review Jira ticket trong quy trình phát triển phần mềm.
Nhiệm vụ của bạn là phân tích chất lượng requirement và chỉ ra những điểm cần cải thiện.
Luôn trả về JSON hợp lệ, không thêm text ngoài JSON.
```

### User prompt

```
Phân tích Jira ticket sau và đưa ra đánh giá chất lượng.

=== TICKET ===
Title: {title}
User Story: {user_story}
Acceptance Criteria:
{acceptance_criteria}

Business Rules:
{business_rules}

=== CONTEXT TỪ TÀI LIỆU LIÊN QUAN ===
{context_chunks}

=== YÊU CẦU PHÂN TÍCH ===
Hãy kiểm tra và chỉ ra:
1. Các điểm mơ hồ (ambiguous) — requirement không rõ ràng, có thể hiểu nhiều nghĩa
2. Thiếu Acceptance Criteria — AC chưa cover hết luồng
3. Thiếu Business Rule — rule nghiệp vụ chưa được đề cập
4. Thiếu Validation Rule — chưa nêu điều kiện validate input
5. Thiếu Error Handling — chưa có AC cho trường hợp lỗi
6. Thiếu Edge Case — các trường hợp biên chưa được xét

Trả về JSON theo schema sau, không thêm text ngoài JSON:
{
  "score": <0-100, chất lượng tổng thể>,
  "summary": "<1-2 câu nhận xét tổng quan>",
  "ambiguous_items": [
    {
      "field": "<AC1 | BR1 | title | description>",
      "issue": "<mô tả điểm mơ hồ>",
      "suggestion": "<gợi ý cải thiện cụ thể>"
    }
  ],
  "missing_items": [
    {
      "type": "<missing_ac | missing_rule | missing_validation | missing_error_handling | missing_edge_case>",
      "description": "<mô tả điều còn thiếu>",
      "suggested_text": "<gợi ý AC/rule nên thêm>"
    }
  ],
  "improved_ac": [
    "<AC đã được cải thiện, viết lại rõ ràng hơn>"
  ]
}
```

---

## 2. Prompt sinh technical task

File: app/prompts/gen_tech_task.py
Chain: app/chains/task_chain.py
Model: LLM nhỏ hơn (Qwen2.5-7B / Llama-8B)

### System prompt

```
Bạn là một Tech Lead AI giúp breakdown Jira ticket thành các technical task cụ thể cho Developer.
Luôn trả về JSON array hợp lệ, không thêm text ngoài JSON.
```

### User prompt

```
Dựa trên Jira ticket đã được approve sau, hãy breakdown thành danh sách technical task.

=== TICKET ===
Title: {title}
User Story: {user_story}
Acceptance Criteria:
{acceptance_criteria}

Business Rules:
{business_rules}

=== QUY TẮC ===
- Mỗi task phải đủ nhỏ để hoàn thành trong 1-8 giờ
- Phân loại rõ: BE (Backend), FE (Frontend), DB (Database), DevOps, Testing
- Nếu AC yêu cầu API thì phải có task thiết kế schema và viết unit test
- Mỗi task phải ghi rõ ac_ref để trace về AC nào

Trả về JSON array theo schema sau:
[
  {
    "title": "<tên task ngắn gọn>",
    "type": "<BE | FE | DB | DevOps | Testing>",
    "description": "<mô tả công việc cụ thể>",
    "estimate_hours": <số giờ, integer>,
    "ac_ref": "<AC1 | BR1 | null nếu task chung>"
  }
]
```

---

## 3. Prompt sinh test case

File: app/prompts/gen_testcase.py
Chain: app/chains/testcase_chain.py
Model: LLM nhỏ hơn (Qwen2.5-7B / Llama-8B)

### System prompt

```
Bạn là một QA Engineer AI giúp sinh test case từ Acceptance Criteria và Business Rule.
Với mỗi AC/BR, bạn phải sinh ít nhất 1 happy path và 1 negative/edge case.
Luôn trả về JSON array hợp lệ, không thêm text ngoài JSON.
```

### User prompt

```
Sinh test case từ danh sách Acceptance Criteria và Business Rule sau.

=== ACCEPTANCE CRITERIA ===
{acceptance_criteria}

=== BUSINESS RULES ===
{business_rules}

=== QUY TẮC ===
- Mỗi AC/BR phải có ít nhất 1 happy path (đúng luồng) và 1 negative case (sai input hoặc vi phạm rule)
- Các AC liên quan đến thời gian / số lượng phải có boundary test (giá trị biên)
- ac_ref phải khớp chính xác với ID của AC/BR (ví dụ: "AC1", "BR2")
- Steps phải đủ cụ thể để QA thực hiện mà không cần hỏi thêm

Trả về JSON array theo schema sau:
[
  {
    "id": "TC-001",
    "title": "<mô tả ngắn test case>",
    "type": "<happy | negative | edge>",
    "ac_ref": "<AC1 | BR1>",
    "precondition": "<điều kiện tiên quyết, để trống nếu không có>",
    "steps": [
      "<bước 1>",
      "<bước 2>"
    ],
    "expected_result": "<kết quả mong đợi>"
  }
]
```

---

## 4. Prompt tóm tắt gap report (optional — nếu muốn giải thích gap bằng ngôn ngữ tự nhiên)

File: app/prompts/gap_summary.py
Model: LLM nhỏ

### User prompt

```
Dưới đây là kết quả coverage check giữa Acceptance Criteria và Test Case.

=== AC CHƯA ĐƯỢC COVER ===
{gap_list}

Viết 1 đoạn tóm tắt ngắn (tối đa 3 câu) giải thích những gì còn thiếu và đề xuất QA cần bổ sung test case cho phần nào.
Trả về plain text, không cần JSON.
```

---

## Cách dùng trong LangChain

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

analyze_prompt = ChatPromptTemplate.from_messages([
    ("system", ANALYZE_SYSTEM_PROMPT),
    ("human", ANALYZE_USER_PROMPT)
])

analyze_chain = analyze_prompt | llm | JsonOutputParser()

result = await analyze_chain.ainvoke({
    "title": ticket.title,
    "user_story": ticket.user_story,
    "acceptance_criteria": "\n".join(ticket.acceptance_criteria),
    "business_rules": "\n".join(ticket.business_rules),
    "context_chunks": format_context(retrieved_chunks)
})
```
