# Clarion — Project Overview

## Mục tiêu

Clarion là AI agent tích hợp trực tiếp vào Jira, tự động hóa các bước trong SDLC:

1. **Review ticket** — phát hiện requirement mơ hồ, thiếu AC, thiếu business rule, validation rule, error handling, edge case
2. **Suggest cải thiện** — gợi ý rewrite AC, bổ sung rule còn thiếu, scoring chất lượng ticket
3. **Sinh technical task** — sau khi ticket được approve, tự động breakdown task cho Dev
4. **Sinh test case** — từ AC và business rule, gen test case happy path + negative/edge case
5. **Coverage check** — kiểm tra test case đã cover hết AC/rule chưa, báo gap

---

## Luồng hoạt động chính (Happy Path)

```
PM viết Jira ticket
        ↓
[CLARION] Embed ticket → lưu vào Qdrant
        ↓
[CLARION] Search Qdrant → retrieve context (BRD chunks + ticket cũ tương tự)
        ↓
[CLARION] Build prompt: ticket + context → gọi LLM
        ↓
[CLARION] LLM phân tích: detect mơ hồ, missing AC, missing rule, score chất lượng
        ↓
[UI]     Hiển thị suggestion panel bên phải màn hình Jira
        ↓
PM review suggestion → chỉnh sửa ticket nếu cần → bấm Approve
        ↓
[CLARION] Ticket đã approve:
          - Embed lại ticket đã chuẩn hóa → lưu Qdrant (collection: approved_tickets)
          - Parse ticket thành JSON có cấu trúc
          ↓ (song song)
    ┌─────────────────────┬────────────────────────┐
    ↓                     ↓                        ↓
Gen tech task         Gen test case          (future: notify)
    ↓                     ↓
LLM breakdown         LLM sinh TC từng AC/rule
    ↓                     ↓
Jira sub-tasks        TC list (JSON)
                          ↓
                    Embedding coverage check
                    (AC vector ↔ TC vector, cosine sim)
                          ↓
                    Gap report: AC chưa được cover
        ↓
[UI] Hiển thị task list + test case list + gap alert trong Jira
```

---

## Các actor

| Actor | Vai trò |
|---|---|
| PM / BA | Viết ticket, review suggestion, approve |
| Developer | Nhận technical task được sinh tự động |
| QA | Nhận test case, xem gap report |
| Clarion AI | Phân tích, sinh task/test case, coverage check |

---

## Phạm vi hiện tại (MVP)

- [x] Review và suggest cải thiện ticket khi PM viết
- [x] Sinh technical task sau approve
- [x] Sinh test case từ AC và business rule
- [x] Coverage check bằng embedding similarity
- [ ] Tích hợp Jira webhook (trigger tự động)
- [ ] Notify qua Slack / email
- [ ] Dashboard chất lượng ticket theo sprint

---

## Nguyên tắc thiết kế

- **Không thay đổi workflow hiện tại** — Clarion tích hợp vào Jira, không yêu cầu team dùng tool mới
- **Suggestion, không áp đặt** — mọi output của AI đều là gợi ý, PM/QA/Dev có quyền chỉnh sửa
- **Structured output** — mọi output của LLM đều ở dạng JSON có schema rõ ràng, không free-text
- **Fail gracefully** — nếu AI không tự tin, trả về partial result kèm flag cần human review
