# BUSINESS REQUIREMENTS DOCUMENT
# Authentication & User Management

| Field | Value |
|---|---|
| Document ID | BRD-AUTH-001 |
| Version | 1.2 |
| Project | Clarion MVP |
| Status | Approved |
| Author | PM Team |
| Reviewed by | Tech Lead, QA Lead |
| Sprint | Sprint 1 |

---

## 1. Project Overview

Module Authentication & User Management bao gồm các chức năng: đăng ký tài khoản, đăng nhập, quản lý phiên, đặt lại mật khẩu và xác thực hai yếu tố (2FA).

### 1.1 Mục tiêu

- Cho phép người dùng tạo tài khoản an toàn bằng email và mật khẩu
- Xác thực danh tính người dùng qua email OTP trước khi kích hoạt tài khoản
- Cung cấp cơ chế đăng nhập an toàn, hỗ trợ phiên làm việc và refresh token
- Cho phép người dùng đặt lại mật khẩu khi quên qua email
- Hỗ trợ xác thực hai yếu tố (2FA) tùy chọn bằng TOTP (Google Authenticator)

### 1.2 Phạm vi

Áp dụng cho tất cả người dùng cuối truy cập qua web browser và mobile app.
Không bao gồm: SSO/OAuth bên thứ ba (Google, Facebook), quản lý phân quyền (authorization).

---

## 2. Stakeholders

| Stakeholder | Vai trò | Trách nhiệm |
|---|---|---|
| Product Manager | Owner | Approve requirement, priority |
| Tech Lead | Reviewer | Technical feasibility, architecture review |
| QA Lead | Reviewer | Test coverage, acceptance criteria review |
| Security Team | Reviewer | Security compliance, vulnerability assessment |
| Dev Team | Implementer | Implementation, unit test |
| End User | Consumer | Sử dụng tính năng đăng ký/đăng nhập |

---

## 3. Business Rules (BR)

### 3.1 Quy tắc tài khoản

| ID | Business Rule | Mức độ |
|---|---|---|
| BR-ACC-001 | Mỗi địa chỉ email chỉ được đăng ký duy nhất 1 tài khoản trong hệ thống. | Bắt buộc |
| BR-ACC-002 | Tài khoản chưa xác nhận email sau 24 giờ kể từ khi đăng ký sẽ bị tự động xóa. | Bắt buộc |
| BR-ACC-003 | Tài khoản bị khóa tạm thời 15 phút sau 5 lần đăng nhập sai liên tiếp. | Bắt buộc |
| BR-ACC-004 | Người dùng không thể đăng nhập vào tài khoản chưa xác nhận email. | Bắt buộc |
| BR-ACC-005 | Tài khoản bị admin vô hiệu hóa sẽ không thể đăng nhập cho đến khi được kích hoạt lại. | Bắt buộc |

### 3.2 Quy tắc mật khẩu

| ID | Business Rule | Mức độ |
|---|---|---|
| BR-PWD-001 | Mật khẩu phải có tối thiểu 8 ký tự. | Bắt buộc |
| BR-PWD-002 | Mật khẩu phải chứa ít nhất 1 chữ hoa (A-Z), 1 chữ số (0-9), và 1 ký tự đặc biệt (!@#$%^&*). | Bắt buộc |
| BR-PWD-003 | Mật khẩu mới khi đặt lại không được trùng với 3 mật khẩu gần nhất. | Bắt buộc |
| BR-PWD-004 | Mật khẩu phải được hash bằng bcrypt (cost factor >= 12) trước khi lưu vào database. | Bắt buộc |
| BR-PWD-005 | Không lưu mật khẩu dạng plain text ở bất kỳ đâu, bao gồm log. | Bắt buộc |

### 3.3 Quy tắc phiên làm việc (Session)

| ID | Business Rule | Mức độ |
|---|---|---|
| BR-SES-001 | Access token có hiệu lực trong 15 phút. | Bắt buộc |
| BR-SES-002 | Refresh token có hiệu lực trong 7 ngày. | Bắt buộc |
| BR-SES-003 | Mỗi tài khoản tối đa 5 phiên đăng nhập đồng thời trên các thiết bị khác nhau. | Bắt buộc |
| BR-SES-004 | Khi đăng xuất, refresh token phải bị revoke ngay lập tức. | Bắt buộc |
| BR-SES-005 | Refresh token chỉ được dùng 1 lần (rotation). Sau khi dùng phải cấp token mới. | Bắt buộc |

### 3.4 Quy tắc OTP

| ID | Business Rule | Mức độ |
|---|---|---|
| BR-OTP-001 | OTP xác nhận email có hiệu lực trong 10 phút kể từ thời điểm gửi. | Bắt buộc |
| BR-OTP-002 | OTP đặt lại mật khẩu có hiệu lực trong 15 phút. | Bắt buộc |
| BR-OTP-003 | OTP gồm 6 chữ số, sinh ngẫu nhiên. | Bắt buộc |
| BR-OTP-004 | Mỗi email chỉ được gửi tối đa 3 OTP trong vòng 1 giờ. | Bắt buộc |
| BR-OTP-005 | OTP chỉ được sử dụng 1 lần. Sau khi dùng phải bị invalidate ngay. | Bắt buộc |
| BR-OTP-006 | Hệ thống phải gửi OTP trong vòng 60 giây sau khi nhận request. | Bắt buộc |

---

## 4. Functional Requirements

### 4.1 Đăng ký tài khoản (User Registration)

Mô tả: Người dùng cung cấp thông tin cơ bản để tạo tài khoản mới. Tài khoản chỉ được kích hoạt sau khi xác nhận email thành công.

#### Acceptance Criteria

| ID | Acceptance Criteria |
|---|---|
| AC-REG-001 | Hệ thống cho phép đăng ký với: full name, email, password, confirm password. |
| AC-REG-002 | Sau khi submit thành công, hệ thống gửi email chứa OTP 6 chữ số đến địa chỉ email đã đăng ký trong vòng 60 giây. |
| AC-REG-003 | Người dùng nhập OTP đúng trong 10 phút thì tài khoản được kích hoạt, redirect về trang đăng nhập. |
| AC-REG-004 | Nếu email đã tồn tại trong hệ thống, hiển thị lỗi: "Email này đã được đăng ký. Vui lòng đăng nhập hoặc dùng email khác." |
| AC-REG-005 | Nếu password và confirm password không khớp, hiển thị lỗi inline ngay dưới field confirm password. |
| AC-REG-006 | Nếu password không đủ điều kiện theo BR-PWD-001/002, hiển thị lỗi cụ thể chỉ rõ điều kiện nào chưa đạt. |
| AC-REG-007 | Người dùng có thể yêu cầu gửi lại OTP tối đa 3 lần trong 1 giờ (BR-OTP-004). |
| AC-REG-008 | OTP nhập sai 5 lần liên tiếp thì OTP bị vô hiệu hóa, yêu cầu gửi lại. |
| AC-REG-009 | Tài khoản chưa xác nhận email sau 24 giờ sẽ bị xóa tự động (BR-ACC-002). |

#### Validation Rules

| Field | Rule | Error Message |
|---|---|---|
| full_name | Bắt buộc, 2-100 ký tự, chỉ chứa chữ cái và khoảng trắng | Họ tên không hợp lệ (2-100 ký tự) |
| email | Bắt buộc, đúng format RFC 5322, tối đa 254 ký tự | Email không đúng định dạng |
| password | Bắt buộc, min 8 ký tự, có chữ hoa, số, ký tự đặc biệt | Mật khẩu không đủ điều kiện bảo mật |
| confirm_password | Bắt buộc, phải khớp với password | Mật khẩu xác nhận không khớp |

#### Edge Cases

| ID | Edge Case | Expected Behavior |
|---|---|---|
| EC-REG-001 | Email chứa ký tự Unicode (ví dụ: tên miền tiếng Việt) | Từ chối, hiển thị lỗi format email không hợp lệ |
| EC-REG-002 | Người dùng submit form 2 lần nhanh (double click) | Chỉ xử lý request đầu tiên, request thứ 2 bị bỏ qua (idempotent) |
| EC-REG-003 | Email server không phản hồi khi gửi OTP | Trả về lỗi 503, hiển thị "Không thể gửi email. Vui lòng thử lại sau." |
| EC-REG-004 | Người dùng truy cập link xác nhận đã hết hạn | Hiển thị trang thông báo hết hạn, cho phép gửi lại OTP |
| EC-REG-005 | Tài khoản bị xóa do hết hạn 24h, người dùng nhập OTP cũ | Hiển thị lỗi OTP không hợp lệ, hướng dẫn đăng ký lại |
| EC-REG-006 | Người dùng mở đồng thời 2 tab và submit cùng lúc | Chỉ 1 tài khoản được tạo, tab còn lại nhận lỗi email đã tồn tại |

---

### 4.2 Đăng nhập (User Login)

Mô tả: Người dùng đã có tài khoản và đã xác nhận email có thể đăng nhập bằng email và mật khẩu. Hệ thống cấp access token và refresh token sau khi xác thực thành công.

#### Acceptance Criteria

| ID | Acceptance Criteria |
|---|---|
| AC-LOG-001 | Đăng nhập thành công với email và password đúng thì nhận access token (15 phút) và refresh token (7 ngày). |
| AC-LOG-002 | Đăng nhập với email không tồn tại hoặc password sai thì hiển thị lỗi chung: "Email hoặc mật khẩu không đúng." (không phân biệt để tránh user enumeration). |
| AC-LOG-003 | Đăng nhập với tài khoản chưa xác nhận email thì hiển thị lỗi: "Tài khoản chưa được xác nhận. Vui lòng kiểm tra email." kèm nút gửi lại OTP. |
| AC-LOG-004 | Sau 5 lần đăng nhập sai liên tiếp thì khóa tài khoản 15 phút, hiển thị thông báo và thời gian còn lại. |
| AC-LOG-005 | Trong thời gian tài khoản bị khóa, mọi request đăng nhập đều bị từ chối kể cả nhập đúng password. |
| AC-LOG-006 | Đăng nhập thành công thì lưu refresh token vào HttpOnly cookie, access token trả về response body. |
| AC-LOG-007 | Tối đa 5 phiên đồng thời (BR-SES-003). Phiên thứ 6 thì tự động thu hồi phiên cũ nhất. |

#### Validation Rules

| Field | Rule | Error Message |
|---|---|---|
| email | Bắt buộc, đúng format email | Vui lòng nhập email hợp lệ |
| password | Bắt buộc, không validate độ phức tạp tại bước này | Vui lòng nhập mật khẩu |

#### Edge Cases

| ID | Edge Case | Expected Behavior |
|---|---|---|
| EC-LOG-001 | Tài khoản bị admin disable trong khi user đang đăng nhập | Access token hiện tại vẫn hoạt động đến khi hết hạn. Refresh token bị revoke ngay. |
| EC-LOG-002 | Người dùng đăng nhập từ IP khác quốc gia so với thường lệ | Ghi log security event, gửi email cảnh báo (không chặn đăng nhập). |
| EC-LOG-003 | Đồng hồ server và client lệch nhau (clock skew) | Cho phép sai lệch tối đa 5 phút khi validate JWT. |
| EC-LOG-004 | Người dùng nhập password có khoảng trắng ở đầu/cuối | Trim whitespace trước khi validate. |

---

### 4.3 Quên mật khẩu (Forgot Password)

Mô tả: Người dùng quên mật khẩu có thể yêu cầu đặt lại qua email. Hệ thống gửi OTP để xác thực danh tính trước khi cho phép đặt mật khẩu mới.

#### Acceptance Criteria

| ID | Acceptance Criteria |
|---|---|
| AC-FPW-001 | Người dùng nhập email thì hệ thống gửi OTP 6 chữ số đến email trong vòng 60 giây. |
| AC-FPW-002 | Nếu email không tồn tại, hiển thị thông báo: "Nếu email tồn tại trong hệ thống, bạn sẽ nhận được hướng dẫn." (không tiết lộ email có tồn tại hay không). |
| AC-FPW-003 | OTP hợp lệ trong 15 phút (BR-OTP-002). Quá thời gian thì yêu cầu gửi lại. |
| AC-FPW-004 | Sau khi xác nhận OTP thành công, người dùng nhập mật khẩu mới và xác nhận. |
| AC-FPW-005 | Mật khẩu mới không được trùng 3 mật khẩu gần nhất (BR-PWD-003). |
| AC-FPW-006 | Đặt lại thành công thì tất cả phiên hiện tại bị đăng xuất, revoke toàn bộ refresh token. |
| AC-FPW-007 | Giới hạn gửi OTP: tối đa 3 lần trong 1 giờ (BR-OTP-004). |

#### Edge Cases

| ID | Edge Case | Expected Behavior |
|---|---|---|
| EC-FPW-001 | Người dùng mở 2 tab và request OTP đồng thời | Chỉ 1 OTP được active. OTP thứ 2 invalidate OTP thứ 1. |
| EC-FPW-002 | Người dùng đặt lại mật khẩu trùng với mật khẩu hiện tại | Từ chối, hiển thị lỗi: "Mật khẩu mới không được trùng mật khẩu hiện tại." |
| EC-FPW-003 | OTP đúng nhưng hết hạn đúng thời điểm submit | Hệ thống check theo server time. Nếu hết hạn thì thông báo OTP hết hạn. |

---

### 4.4 Refresh Token

Mô tả: Client tự động làm mới access token khi sắp hết hạn bằng refresh token.

#### Acceptance Criteria

| ID | Acceptance Criteria |
|---|---|
| AC-REF-001 | Client gửi refresh token hợp lệ thì nhận access token mới (15 phút) và refresh token mới (rotation). |
| AC-REF-002 | Refresh token cũ bị revoke ngay sau khi dùng. |
| AC-REF-003 | Refresh token hết hạn hoặc đã bị revoke thì trả về 401, buộc đăng nhập lại. |
| AC-REF-004 | Nếu phát hiện refresh token bị dùng lần thứ 2 (token reuse) thì revoke toàn bộ phiên của user. |

---

## 5. Non-Functional Requirements

| ID | Category | Requirement |
|---|---|---|
| NFR-001 | Performance | API đăng nhập phải phản hồi trong < 500ms ở percentile 95 với load 100 concurrent users. |
| NFR-002 | Performance | Gửi email OTP trong vòng 60 giây kể từ khi nhận request. |
| NFR-003 | Security | Tất cả endpoint authentication phải dùng HTTPS. Không cho phép HTTP. |
| NFR-004 | Security | Rate limiting: tối đa 10 request/phút/IP cho endpoint đăng ký và quên mật khẩu. |
| NFR-005 | Security | Log tất cả sự kiện bảo mật: đăng nhập thất bại, khóa tài khoản, đặt lại mật khẩu. |
| NFR-006 | Availability | Module authentication phải đạt uptime 99.9%. |
| NFR-007 | Scalability | Hệ thống phải xử lý được 1000 concurrent login requests mà không degradation. |
| NFR-008 | Compliance | Mật khẩu và dữ liệu nhạy cảm phải tuân thủ OWASP Top 10. |

---

## 6. Error Handling & HTTP Status Codes

| HTTP Code | Scenario | Response |
|---|---|---|
| 400 | Request body thiếu field hoặc sai format | { error: "VALIDATION_ERROR", details: [...] } |
| 401 | Token hết hạn hoặc không hợp lệ | { error: "UNAUTHORIZED", message: "Token invalid or expired" } |
| 403 | Tài khoản bị khóa hoặc vô hiệu hóa | { error: "ACCOUNT_LOCKED", retry_after: 900 } |
| 409 | Email đã tồn tại khi đăng ký | { error: "EMAIL_ALREADY_EXISTS" } |
| 422 | OTP sai hoặc hết hạn | { error: "OTP_INVALID", message: "OTP không hợp lệ hoặc đã hết hạn" } |
| 429 | Vượt rate limit | { error: "RATE_LIMIT_EXCEEDED", retry_after: 3600 } |
| 500 | Lỗi server không xác định | { error: "INTERNAL_ERROR", request_id: "..." } |
| 503 | Email service không khả dụng | { error: "EMAIL_SERVICE_UNAVAILABLE" } |

---

## 7. Glossary

| Thuật ngữ | Định nghĩa |
|---|---|
| OTP | One-Time Password — mã xác thực dùng 1 lần, hết hạn sau thời gian nhất định. |
| Access Token | JWT token ngắn hạn (15 phút) dùng để xác thực request API. |
| Refresh Token | Token dài hạn (7 ngày) dùng để lấy access token mới mà không cần đăng nhập lại. |
| Token Rotation | Cơ chế mỗi lần dùng refresh token sẽ cấp token mới và revoke token cũ. |
| bcrypt | Thuật toán hash mật khẩu một chiều, không thể giải mã ngược. |
| HttpOnly Cookie | Cookie không thể đọc bằng JavaScript, giảm nguy cơ XSS attack. |
| User Enumeration | Kỹ thuật tấn công để xác định email/username nào tồn tại trong hệ thống. |
| Clock Skew | Sự lệch thời gian giữa server và client, ảnh hưởng đến validate JWT. |
