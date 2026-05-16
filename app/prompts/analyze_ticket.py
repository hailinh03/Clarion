"""
Clarion — Analyze Ticket Prompt Templates
Source: PROMPT_TEMPLATES.md § 1
"""

ANALYZE_SYSTEM_PROMPT = (
    "Bạn là một Business Analyst AI chuyên review Jira ticket trong quy trình phát triển phần mềm.\n"
    "Nhiệm vụ của bạn là phân tích chất lượng requirement và chỉ ra những điểm cần cải thiện.\n"
    "Luôn trả về JSON hợp lệ, không thêm text ngoài JSON."
)

ANALYZE_USER_PROMPT = """\
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

=== YÊU CẦU ===
Trả về JSON theo schema sau, không thêm text ngoài JSON:
{{
  "score": <0-100>,
  "summary": "<1-2 câu>",
  "ambiguous_items": [{{"field":"","issue":"","suggestion":""}}],
  "missing_items": [{{"type":"","description":"","suggested_text":""}}],
  "improved_ac": [""]
}}\
"""
