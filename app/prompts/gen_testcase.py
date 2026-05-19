"""
Clarion — Gen Test Case Prompt Templates
Source: PROMPT_TEMPLATES.md § 3
"""

GEN_TESTCASE_SYSTEM_PROMPT = (
    "Bạn là một QA Engineer AI giúp sinh test case từ Acceptance Criteria, Business Rule và Edge Cases.\n"
    "Với mỗi AC/BR/EC, bạn phải sinh ít nhất 1 happy path và 1 negative/edge case.\n"
    "Luôn trả về JSON array hợp lệ, không thêm text ngoài JSON."
)

GEN_TESTCASE_USER_PROMPT = """\
Sinh test case từ danh sách Acceptance Criteria, Business Rule và Edge Cases sau.

=== ACCEPTANCE CRITERIA ===
{acceptance_criteria}

=== BUSINESS RULES ===
{business_rules}

=== EDGE CASES ===
{edge_cases}

=== QUY TẮC ===
- Mỗi AC/BR/EC phải có ít nhất 1 happy path và 1 negative case
- ac_ref phải khớp chính xác với ID của AC/BR/EC (ví dụ: "AC1", "BR2", "EC1")
- Steps phải đủ cụ thể để QA thực hiện mà không cần hỏi thêm

Trả về JSON array:
[{{"id":"TC-001","title":"","type":"happy|negative|edge","ac_ref":"AC1","precondition":"","steps":[""],"expected_result":""}}]\
"""
