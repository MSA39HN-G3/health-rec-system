# Hướng dẫn lấy thông tin config Cloudflare R2

> **Mục đích:** Điền đúng 4 biến R2 trong file `.env` của dự án:
> `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`.
>
> **Dành cho:** lập trình viên backend/devops khi cần cấu hình môi trường
> development hoặc production. Hệ thống dùng Cloudflare R2 (S3-compatible)
> làm nơi lưu file upload (ảnh đại diện khoa, sau này mở rộng PDF, ...).

---

## 1. Kiến thức cần biết trước

| Khái niệm | Là gì | Tìm ở đâu |
|---|---|---|
| **Account ID** | Mã định danh tài khoản Cloudflare (độ dài 32 hex). | Dashboard phải-trên của Cloudflare. |
| **Bucket** | Thư mục gốc trong R2 chứa tất cả object. | R2 > *Buckets*. |
| **API Token / Access Key** | Cặp `Access Key ID` + `Secret Access Key` để truy cập R2 theo S3. | R2 > *Manage R2 API Tokens*. |
| **Endpoint** | URL R2 dạng `https://<account_id>.r2.cloudflarestorage.com` — **BE tự dựng từ `R2_ACCOUNT_ID`**, không cần khai báo. | Tự sinh. |

> ⚠️ **Bảo mật:** `R2_SECRET_ACCESS_KEY` chỉ hiện **đúng một lần** khi bạn tạo
> token. Nếu lỡ mất, phải **xoá token cũ và tạo token mới**. Không commit `.env`
> lên git (xem `.gitignore`).

---

## 2. Lấy `R2_ACCOUNT_ID`

### Cách 1 — Từ Cloudflare Dashboard

1. Đăng nhập [dash.cloudflare.com](https://dash.cloudflare.com).
2. Nhìn góc **phải-trên**, ngay dưới tên tài khoản → dòng chữ *Account ID*
   (32 ký tự hex, ví dụ `a1b2c3d4e5f6...`). Bấm **Copy**.

### Cách 2 — Từ R2

1. Trong sidebar trái chọn **R2** > *Overview*.
2. Cuộn xuống phần **Account ID**, nhấn **Copy**.

> Dán giá trị này vào biến `R2_ACCOUNT_ID=...` trong `.env`.

---

## 3. Tạo bucket → lấy `R2_BUCKET`

> Nếu đã có sẵn bucket, bỏ qua bước tạo, chỉ cần lấy **tên bucket** và dán
> vào `R2_BUCKET`.

### Bước 3.1 — Tạo bucket

1. Vào **R2** > **Create bucket**.
2. Nhập **Bucket name**, gợi ý cho dự án: `health-rec-assets`
   (chỉ chữ thường, số, dấu gạch ngang; toàn cục).
3. **Location:** chọn `Automatic` (R2 tự chọn region gần nhất).
4. Nhấn **Create bucket**.

### Bước 3.2 — Cấu hình truy cập

Dự án **ưu tiên bucket PRIVATE** (FE chỉ xem ảnh qua presigned GET).

- Trong bucket vừa tạo, vào tab **Settings**.
- **Public access:**
  - **Mặc định khuyến nghị:** để **tắt** public access → FE chỉ xem qua
    URL presigned có TTL (`R2_PRESIGN_GET_TTL`, mặc định 1 giờ).
  - *Nếu cần custom domain* (vd `assets.example.com`): bật **Public access**
    và thêm `R2_PUBLIC_HOST=assets.example.com` vào `.env`. Khi đó BE trả
    URL public trực tiếp, không cần ký.

> ⚠️ **Không bật "Public access"** trên bucket (chỉ bật khi thật sự
> cần custom domain — production). CORS policy thì **bắt buộc phải thêm** —
> cấu hình ở **§5** (Settings → CORS Policy), nếu không FE PUT lên R2 sẽ
> bị trình duyệt chặn vì lỗi CORS.

### Bước 3.3 — Ghi tên bucket vào `.env`

```
R2_BUCKET=health-rec-assets
```

---

## 4. Tạo API Token → lấy `R2_ACCESS_KEY_ID` và `R2_SECRET_ACCESS_KEY`

### Bước 4.1 — Mở trang tạo token

1. Vào **R2** > **Manage R2 API Tokens** (nút bên phải Overview).
2. Nhấn **Create API token**.

### Bước 4.2 — Chọn quyền

- **Permissions:** chọn **Object Read & Write** (FE cần ghi, BE cần đọc để
  HEAD/derive URL). Tránh **Admin** vì quá rộng.
- **Bucket scope:** chọn **Apply to specific buckets only** → chỉ chọn
  bucket `health-rec-assets`. Không cấp token full-account trừ khi có lý do.

### Bước 4.3 — TTL (tuỳ chọn)

- Để **No expiration** cho môi trường production (xoay key theo lịch riêng).
- Cho môi trường dev có thể đặt `1 year` để an toàn hơn.

### Bước 4.4 — Tạo và copy

Nhấn **Create API Token**. Màn hình tiếp theo hiển thị **một lần duy nhất**:

| Trường | Điền vào biến |
|---|---|
| `Access Key ID` | `R2_ACCESS_KEY_ID` |
| `Secret Access Key` | `R2_SECRET_ACCESS_KEY` |
| `Endpoint` (nếu có) | **Không cần** — BE tự dựng từ `R2_ACCOUNT_ID`. |

> ⚠️ **Secret Access Key chỉ hiện một lần.** Nếu lỡ đóng tab → phải tạo
> token mới. Lưu vào password manager (Bitwarden/1Password) hoặc secret
> manager (Vault, AWS Secrets Manager, ...).

### Bước 4.5 — Thêm vào `.env`

```
R2_ACCOUNT_ID=a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4
R2_ACCESS_KEY_ID=0123456789abcdef0123456789abcdef
R2_SECRET_ACCESS_KEY=abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789
R2_BUCKET=health-rec-assets
```

---

## 5. (Tuỳ chọn) Bật CORS cho FE upload

Vì FE PUT thẳng lên R2 (không qua BE), trình duyệt sẽ yêu cầu CORS trên bucket.

1. Vào bucket > **Settings** > **CORS Policy** > **Add CORS Policy**.
2. Dán JSON sau (chỉnh origin cho phù hợp môi trường):

```json
[
  {
    "AllowedOrigins": [
      "http://localhost:3000",
      "http://localhost:5173",
      "https://fe.example.com"
    ],
    "AllowedMethods": ["PUT", "GET", "HEAD"],
    "AllowedHeaders": ["Content-Type"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

3. **Save**.

> Nếu khi test FE gặp `403` kèm message có chữ `CORS`, kiểm tra:
> - Origin có trong `AllowedOrigins` không.
> - `Content-Type` có trong `AllowedHeaders` không (bắt buộc vì PUT có header này).

---

## 6. Test nhanh sau khi điền `.env`

Sau khi copy xong 4 biến vào `.env` (và `pip install -r requirements.txt` nếu
chưa có `boto3`), chạy lệnh sau trong venv:

```bash
./.venv/Scripts/python.exe -c "
import os
from dotenv import load_dotenv
load_dotenv()
import boto3
from botocore.client import Config

client = boto3.client(
    's3',
    endpoint_url=f\"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com\",
    aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'],
    aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'],
    region_name='auto',
    config=Config(signature_version='s3v4'),
)
print(client.list_buckets())
"
```

Kết quả mong đợi:

- **Khoẻ:** in ra danh sách bucket, có `health-rec-assets` (hoặc tên bạn đặt).
- **Sai Account ID:** `EndpointConnectionError` / DNS không phân giải.
- **Sai Access Key:** `403 InvalidAccessKeyId`.
- **Sai Secret:** `403 SignatureDoesNotMatch`.
- **Thiếu quyền trên bucket:** `403 Access Denied`.

Nếu lệnh trên chạy được, bạn có thể `flask db upgrade` rồi `flask run` và
dùng endpoint `POST /api/v1/uploads/presign` để upload thử.

---

## 7. Vòng đời & xoay key

- **Không commit** file `.env` lên git (đã nằm trong `.gitignore`).
- Lưu `R2_SECRET_ACCESS_KEY` vào secret manager của đội.
- Khi nhân viên rời dự án: vào **Manage R2 API Tokens** → xoá token đã cấp
  cho họ → tạo token mới nếu cần.
- Token dùng cho dev có thể đặt TTL ngắn hơn (90 ngày) để bắt buộc xoay.

---

## 8. Các biến R2 còn lại (BE đã có giá trị mặc định, thường không cần đổi)

Xem `.env.example` (mục `# ----- Cloudflare R2 -----`):

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `R2_PUBLIC_HOST` | rỗng | Custom domain public (vd `assets.example.com`). |
| `R2_PRESIGN_PUT_TTL` | `600` | TTL (giây) presigned PUT (FE upload). |
| `R2_PRESIGN_GET_TTL` | `3600` | TTL (giây) presigned GET (FE xem ảnh). |
| `R2_MAX_UPLOAD_BYTES` | `15728640` | Giới hạn size file (mặc định 15 MB). |
| `R2_ALLOWED_CONTENT_TYPES` | `image/jpeg,image/png,image/webp,application/pdf` | Whitelist MIME. |

---

## 9. Lỗi thường gặp

| Triệu chứng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `EndpointConnectionError` | Sai `R2_ACCOUNT_ID` hoặc nhân viên chưa đăng ký R2. | Kiểm tra Account ID ở dashboard. |
| `403 InvalidAccessKeyId` | Token bị xoá hoặc copy thiếu. | Tạo token mới. |
| `403 SignatureDoesNotMatch` | Lẫn secret key từ token khác / có ký tự lạ. | Tạo lại token và copy cẩn thận. |
| `403 Access Denied` | Token đúng nhưng không có quyền trên bucket này. | Vào token → đổi *Bucket scope* thành **Apply to specific buckets** → chọn bucket. |
| `403` + CORS khi upload từ trình duyệt | Bucket chưa có CORS policy. | Làm theo **Bước 5**. |
| URL ảnh load hết hạn trên FE | Presigned GET có TTL. | Bình thường — FE cần `GET /departments/{id}` lại để BE derive URL mới. |

---

## 10. Tài liệu liên quan

- [`.env.example`](../.env.example) — danh sách biến môi trường.
- [`FE_UPLOADS.md`](./FE_UPLOADS.md) — API upload R2 dành cho FE.
- [`FE_DEPARTMENT_AVATAR_UPLOAD.md`](./FE_DEPARTMENT_AVATAR_UPLOAD.md) — luồng end-to-end.
- [Cloudflare R2 docs](https://developers.cloudflare.com/r2/) — tài liệu chính thức.

---

## 11. Lịch sử thay đổi

| Phiên bản | Thay đổi |
|---|---|
| **1.0.0** | Hướng dẫn lấy Account ID, tạo bucket, tạo API Token, bật CORS, test nhanh. |