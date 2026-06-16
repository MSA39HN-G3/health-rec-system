# Health Record System — API base (Flask)

Base cho web API bằng Python/Flask theo mẫu **application factory**, gồm:

- ✅ Cấu trúc rõ ràng theo lớp **Controller → Service → Repository** (app factory + blueprint).
- ✅ **Xử lý exception tập trung** qua lớp `AppException` + error handlers.
- ✅ **Đa ngôn ngữ (i18n)** bằng JSON catalog, tự nhận diện từ `?lang=` hoặc header `Accept-Language`.
- ✅ **Response chuẩn hóa** thống nhất cho mọi API (thành công & lỗi).
- ✅ **Message tách ra file riêng** (`app/i18n/locales/*.json`).
- ✅ **Thông tin nhạy cảm tách ra `.env`** (không commit).
- ✅ Database **PostgreSQL 16** qua SQLAlchemy + Flask-Migrate (Alembic).

## Cấu trúc thư mục

```
health-rec-system/
├── app/
│   ├── __init__.py          # application factory create_app()
│   ├── config.py            # config theo môi trường, đọc từ .env
│   ├── extensions.py        # db, migrate
│   ├── api/v1/auth.py       # Controller: xử lý HTTP cho đăng nhập Google
│   ├── services/            # Service: logic nghiệp vụ
│   │   ├── auth_service.py  #   - điều phối luồng đăng nhập
│   │   └── google_oauth.py  #   - gateway gọi Google (đổi code, verify token)
│   ├── repositories/        # Repository: truy cập DB
│   │   └── user_repository.py
│   ├── models/              # Entity (SQLAlchemy): User
│   ├── common/response.py   # success_response / error_response (chuẩn hóa)
│   ├── errors/              # exception nghiệp vụ + handler tập trung
│   └── i18n/                # logic dịch + locales/{en,vi}.json
├── migrations/              # sinh ra bởi flask db init
├── .env.example             # mẫu biến môi trường
├── requirements.txt
└── run.py                   # điểm chạy dev
```

## Cài đặt

```bash
# 1. Tạo & kích hoạt virtualenv
py -m venv .venv
.venv\Scripts\activate          # Windows PowerShell
# source .venv/bin/activate     # macOS/Linux

# 2. Cài dependencies
pip install -r requirements.txt

# 3. Tạo file .env từ mẫu rồi chỉnh DATABASE_URL, SECRET_KEY
copy .env.example .env          # Windows
# cp .env.example .env          # macOS/Linux
```

### Chuẩn bị PostgreSQL 16

Tạo database (ví dụ tên `health_rec`) khớp với `DATABASE_URL` trong `.env`:

```sql
CREATE DATABASE health_rec;
```

### Chạy migration (tạo bảng)

```bash
flask --app run db init        # chỉ chạy lần đầu, tạo thư mục migrations/
flask --app run db migrate -m "init"
flask --app run db upgrade
```

## Chạy app

```bash
python run.py
# API chạy tại http://localhost:5000
```

## Thử nhanh

```bash
# Health check
curl http://localhost:5000/health

# Lấy URL đăng nhập Google (xem mục "Đăng nhập bằng Google")
curl http://localhost:5000/api/v1/auth/google/url
```

## Format response chuẩn hóa

Thành công:
```json
{ "success": true, "data": { ... }, "message": "Đăng nhập thành công." }
```

Lỗi:
```json
{ "success": false, "error": { "code": 401, "message": "Token của Google không hợp lệ.", "details": { ... } } }
```

## Đa ngôn ngữ

- Chọn ngôn ngữ qua query `?lang=vi` / `?lang=en`, hoặc header `Accept-Language: vi`.
- Thêm chuỗi mới: sửa cả `app/i18n/locales/en.json` và `vi.json` theo cùng key.
- Dùng trong code: `from app.i18n import translate; translate("errors.not_found")`.

## Đăng nhập bằng Google (OAuth2)

Cấu hình `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` trong `.env`
(tạo OAuth Client ID dạng *Web application* tại Google Cloud Console). `GOOGLE_REDIRECT_URI`
là URL **trang FE** xử lý callback và phải khớp tuyệt đối với khai báo trên Google Console.

Luồng:

```
FE  --(1) GET /api/v1/auth/google/url-->  BE   trả về { auth_url, state }
FE  --redirect người dùng tới auth_url-->  Google
Google --redirect kèm ?code=...-------->  FE (tại GOOGLE_REDIRECT_URI)
FE  --(2) POST .../google/callback {code}-> BE  đổi code lấy token + verify -> trả user
```

**API 1 — lấy URL redirect**

```bash
curl http://localhost:5000/api/v1/auth/google/url
# { "success": true, "data": { "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?...",
#   "state": "xxx" } }
```
> FE lưu `state`, redirect người dùng tới `auth_url`. Khi Google trả về, FE so khớp `state`
> nhận lại với `state` đã lưu (chống CSRF) trước khi gọi API 2.

**API 2 — gửi authorization_code lên để xác thực**

```bash
curl -X POST http://localhost:5000/api/v1/auth/google/callback \
  -H "Content-Type: application/json" \
  -d "{\"authorization_code\":\"<code FE nhận từ Google>\"}"
# { "success": true, "data": { "user": { "id":1, "email":"...", "full_name":"...",
#   "picture":"...", "email_verified":true } }, "message": "Signed in successfully." }
```

BE thực hiện: (1) đổi `code` lấy token tại Google — đây là bước Google xác thực code;
(2) verify `id_token` (kiểm tra chữ ký + audience) bằng `google-auth`; (3) tạo/cập nhật
`User` trong DB và trả về. Mọi lỗi (code sai/hết hạn, token không hợp lệ, chưa cấu hình...)
đều trả về response chuẩn hóa với message đã dịch theo ngôn ngữ request.

> Bước cấp **JWT/session của hệ thống** sau khi login thành công chưa được thêm (theo lựa
> chọn ban đầu là chưa cần JWT). Khi cần, phát token ngay tại `google/callback` sau khi có `user`.

## Thêm exception nghiệp vụ mới

```python
from app.errors import NotFoundException
raise NotFoundException("errors.not_found", details={"id": some_id})
```

Handler tập trung sẽ tự dịch message theo ngôn ngữ request và trả về response chuẩn hóa.
