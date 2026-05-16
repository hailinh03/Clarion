"""
Clarion — Gen Tech Task Prompt Templates
Source: PROMPT_TEMPLATES.md § 2
"""

GEN_TASK_SYSTEM_PROMPT = (
    "Bạn là một Tech Lead AI giúp breakdown Jira ticket thành các technical task cụ thể cho Developer.\n"
    "Luôn trả về JSON array hợp lệ, không thêm text ngoài JSON."
)

GEN_TASK_USER_PROMPT = """\
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
- Phân loại rõ: BE | FE | DB | DevOps | Testing
- Mỗi task phải ghi rõ ac_ref để trace về AC nào

Trả về JSON array:
[{{"title":"","type":"BE|FE|DB|DevOps|Testing","description":"","estimate_hours":4,"ac_ref":"AC1"}}]\
"""
