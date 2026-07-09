# Hướng dẫn FE: Quản lý Bác sĩ (Doctor)

> **Phiên bản: 1.0.0** — Bản đầu: mở rộng Doctor model với thông tin cá nhân, chuyên môn, hành chính, tài liệu và thống kê.

Module quản lý bác sĩ bao gồm đầy đủ CRUD, quản lý tài liệu, thống kê và đánh giá.

> Tài liệu liên quan: [`FE_RBAC.md`](./FE_RBAC.md) (phân quyền),
> [`FE_AUTH_TOKEN.md`](./FE_AUTH_TOKEN.md) (token, gọi API có bảo vệ),
> [`FE_UPLOADS.md`](./FE_UPLOADS.md) (upload ảnh qua Cloudflare R2).

---

## 1. Quyền truy cập

| Action | Permission | Roles |
|--------|------------|-------|
| Xem danh sách / chi tiết bác sĩ | `department:manage` | admin, department_head |
| Tạo / Sửa / Xóa bác sĩ | `department:manage` | admin, department_head |
| Quản lý tài liệu | `department:manage` | admin, department_head |
| Xem thống kê | `department:manage` | admin, department_head |
| Tính lại thống kê | `department:manage` | admin only |
| Tạo/Sửa đánh giá | `rating:write` | admin, patient |
| Xem đánh giá | `rating:read` | admin, doctor, patient |
| Xóa đánh giá | `department:manage` | admin only |

> FE nên gate menu/nút "Quản lý Bác sĩ" theo `hasPermission("department:manage")`.

---

## 2. Mô hình dữ liệu Bác sĩ

### 2.1 Thông tin cơ bản

| Trường | Kiểu | Bắt buộc | Ý nghĩa |
|--------|------|:---:|---|
| `id` | int | — | Khóa chính |
| `full_name` | string (≤255) | ✅ | Họ tên bác sĩ |
| `department_id` | int | ✅ | FK tới Department |
| `department` | object | — | Thông tin khoa: `{id, name, code}` |
| `title` | string (≤64) | — | Chức danh (vd "Thạc sĩ", "Giáo sư") |
| `is_active` | bool | — | Trạng thái hoạt động (mặc định `true`) |
| `created_at` / `updated_at` | string (ISO) | — | Thời điểm tạo/cập nhật |

### 2.2 Phần 1: Thông tin cá nhân

| Trường | Kiểu | Ý nghĩa |
|--------|------|----------|
| `phone` | string (≤32) | Số điện thoại liên hệ |
| `email` | string (≤255) | Email cá nhân |
| `avatar_object_key` | string (≤512) | Khóa object trong R2 |
| `avatar_url` | string (≤512) | URL hiển thị ảnh (presigned) |
| `date_of_birth` | string (ISO date) | Ngày sinh |
| `gender` | string | `male` \| `female` \| `other` |
| `address` | string | Địa chỉ |

### 2.3 Phần 2: Thông tin chuyên môn

| Trường | Kiểu | Ý nghĩa |
|--------|------|----------|
| `license_number` | string (≤64) | Số giấy phép hành nghề |
| `license_issue_date` | string (ISO date) | Ngày cấp giấy phép |
| `license_expiry_date` | string (ISO date) | Ngày hết hạn |
| `specialization` | string (≤255) | Chuyên khoa chính |
| `sub_specializations` | string[] | Danh sách chuyên khoa phụ |
| `education` | string[] | Trình độ học vấn |
| `experience_years` | int | Số năm kinh nghiệm |
| `training_institutions` | string[] | Nơi đào tạo |

### 2.4 Phần 5: Thông tin hành chính

| Trường | Kiểu | Ý nghĩa |
|--------|------|----------|
| `employment_type` | string | `full_time` \| `part_time` \| `contract` |
| `hire_date` | string (ISO date) | Ngày vào làm |
| `contract_end_date` | string (ISO date) | Ngày kết thúc hợp đồng |
| `is_accepting_new_patients` | bool | Nhận bệnh nhân mới (mặc định `true`) |

---

## 3. Tạo bác sĩ — `POST /api/v1/doctors`

Cần permission `department:manage`.

### Request body

```jsonc
{
  "full_name": "Nguyen Van A",           // bắt buộc
  "department_id": 1,                     // bắt buộc
  "title": "Thạc sĩ",
  
  // Thông tin cá nhân
  "phone": "0912345678",
  "email": "nvana@hospital.com",
  "avatar_object_key": "doctors/avatar_001.png",
  "date_of_birth": "1980-05-15",
  "gender": "male",
  "address": "123 Nguyễn Trãi, Q1, TP.HCM",
  
  // Thông tin chuyên môn
  "license_number": "GD-00012345",
  "license_issue_date": "2010-01-15",
  "license_expiry_date": "2030-01-15",
  "specialization": "Tim mạch",
  "sub_specializations": ["Nội soi tim", "Siêu âm tim"],
  "education": ["Đại học Y Hà Nội", "Thạc sĩ Tim mạch"],
  "experience_years": 15,
  "training_institutions": ["BV Bạch Mai", "BV Trung ương"],
  
  // Thông tin hành chính
  "employment_type": "full_time",
  "hire_date": "2010-03-01",
  "contract_end_date": "2030-03-01",
  "is_accepting_new_patients": true
}
```

> **Tối thiểu chỉ cần `full_name` và `department_id`.**

### Response — `201 Created`

```jsonc
{
  "status": "success",
  "code": "201",
  "message": "Tạo bác sĩ thành công.",
  "data": {
    "id": 1,
    "full_name": "Nguyen Van A",
    "department_id": 1,
    "department": { "id": 1, "name": "Tim mạch", "code": "CK-001" },
    "title": "Thạc sĩ",
    "is_active": true,
    // ... full object
    "created_at": "2026-07-09T10:00:00+00:00",
    "updated_at": "2026-07-09T10:00:00+00:00"
  }
}
```

### Các lỗi có thể gặp

| HTTP | Khi nào | `message` |
|------|----------|-----------|
| **404** | `department_id` không tồn tại | "errors.not_found" |
| **400** | `license_number` đã tồn tại | "errors.duplicate" |
| **422** | Thiếu/sai field | "Dữ liệu không hợp lệ." |
| **403** | Thiếu permission | "errors.forbidden" |

---

## 4. Danh sách bác sĩ — `GET /api/v1/doctors`

Cần permission `department:manage`. Hỗ trợ phân trang.

| Query | Mặc định | Ràng buộc |
|-------|-----------|-----------|
| `page` | 1 | ≥ 1 |
| `size` | 20 | 1–100 |
| `department_id` | — | Lọc theo khoa |
| `is_active` | — | Lọc theo trạng thái |

```jsonc
// GET /api/v1/doctors?page=1&size=20&department_id=1
{
  "status": "success",
  "code": "200",
  "data": [
    {
      "id": 1,
      "full_name": "Nguyen Van A",
      "department": { "id": 1, "name": "Tim mạch", "code": "CK-001" },
      "title": "Thạc sĩ",
      "specialization": "Tim mạch",
      "is_active": true,
      "is_accepting_new_patients": true,
      "created_at": "2026-07-09T10:00:00+00:00"
    }
  ],
  "meta": { "page": 1, "size": 20, "totalPage": 5 }
}
```

---

## 5. Chi tiết bác sĩ — `GET /api/v1/doctors/{id}`

Cần permission `department:manage`.

| Query | Mô tả |
|-------|--------|
| `include_stats` | `true` để include thống kê |
| `include_ratings` | `true` để include đánh giá (limit 20) |

```jsonc
// GET /api/v1/doctors/1?include_stats=true
{
  "status": "success",
  "data": {
    "id": 1,
    "full_name": "Nguyen Van A",
    // ... all fields
    "statistics": {
      "total_appointments": 150,
      "completed_appointments": 140,
      "average_rating": 4.5,
      "total_ratings": 50
    }
  }
}
```

---

## 6. Cập nhật bác sĩ — `PATCH /api/v1/doctors/{id}`

Cần permission `department:manage`. **Cập nhật từng phần (partial update).**

### Request body — tất cả field đều tùy chọn

```jsonc
// PATCH /api/v1/doctors/1
{
  "full_name": "Nguyen Van B",
  "title": "Giáo sư",
  "phone": "0987654321",
  "specialization": "Nội soi tim",
  "is_accepting_new_patients": false,
  "license_expiry_date": "2035-01-15",
  // Arrays: thay thế toàn bộ
  "sub_specializations": ["Nội soi tim", "Phẫu thuật tim"],
  "education": ["Đại học Y Hà Nội", "Tiến sĩ Tim mạch"]
}
```

### Quy tắc khi cập nhật

| Trường | Quy tắc |
|--------|----------|
| `department_id` | Thay đổi khoa phụ trách |
| `license_number` | Không được trùng với bác sĩ khác |
| `avatar_object_key` | Tự động xóa object cũ trên R2 |
| Arrays | Thay thế toàn bộ; gửi `[]` để xóa hết |

---

## 7. Xóa bác sĩ — `DELETE /api/v1/doctors/{id}`

Cần permission `department:manage`. **Soft delete** — chỉ set `is_active = false`.

```jsonc
// DELETE /api/v1/doctors/1
{
  "status": "success",
  "message": "Xóa bác sĩ thành công."
}
```

---

## 8. Tìm kiếm bác sĩ — `GET /api/v1/doctors/search`

Cần permission `department:manage`.

| Query | Bắt buộc | Mô tả |
|-------|:---:|--------|
| `q` | ✅ | Từ khóa tìm kiếm |
| `page` | — | Trang (mặc định 1) |
| `size` | — | Số item/trang (mặc định 20) |
| `department_id` | — | Lọc theo khoa |

> Tìm kiếm theo `full_name`, `specialization`, `license_number`.

---

## 9. Giấy phép sắp hết hạn — `GET /api/v1/doctors/expiring-licenses`

Cần permission `department:manage` (admin only).

| Query | Mặc định | Mô tả |
|-------|-----------|--------|
| `days` | 30 | Số ngày cảnh báo trước |

```jsonc
// GET /api/v1/doctors/expiring-licenses?days=30
{
  "status": "success",
  "message": "Giấy phép hành nghề sắp hết hạn trong 30 ngày",
  "data": [
    {
      "id": 1,
      "full_name": "Nguyen Van A",
      "license_number": "GD-00012345",
      "license_expiry_date": "2026-07-25"
    }
  ]
}
```

---

## 10. Quản lý Tài liệu

### 10.1 Mô hình DoctorDocument

| Trường | Kiểu | Ý nghĩa |
|--------|------|----------|
| `id` | int | Khóa chính |
| `doctor_id` | int | FK tới Doctor |
| `document_type` | string | `license` \| `degree` \| `certificate` \| `contract` \| `id_card` \| `other` |
| `title` | string (≤255) | Tiêu đề tài liệu |
| `object_key` | string (≤512) | Khóa object trong R2 |
| `url` | string (≤512) | URL hiển thị |
| `issue_date` | string (ISO date) | Ngày cấp |
| `expiry_date` | string (ISO date) | Ngày hết hạn |
| `is_verified` | bool | Đã xác minh chưa (mặc định `false`) |
| `created_at` / `updated_at` | string (ISO) | Thời điểm tạo/cập nhật |

### 10.2 Danh sách tài liệu — `GET /api/v1/doctors/{doctor_id}/documents`

```jsonc
{
  "status": "success",
  "data": [
    {
      "id": 1,
      "document_type": "license",
      "title": "Giấy phép hành nghề",
      "url": "https://r2.example.com/docs/license.pdf",
      "issue_date": "2010-01-15",
      "expiry_date": "2030-01-15",
      "is_verified": true,
      "is_expiring_soon": false
    }
  ]
}
```

### 10.3 Tạo tài liệu — `POST /api/v1/doctors/{doctor_id}/documents`

```jsonc
{
  "document_type": "license",              // bắt buộc
  "title": "Giấy phép hành nghề",         // bắt buộc
  "object_key": "doctor/document/4f1c2a....pdf",
  "issue_date": "2010-01-15",
  "expiry_date": "2030-01-15"
}
```

> **Lưu ý:** Mỗi bác sĩ chỉ có **1 giấy phép hành nghề** (`document_type: license`). 
> Tạo license mới khi đã có sẽ trả lỗi 400.
>
> **`object_key` phải upload qua R2 trước** thông qua flow presign → PUT → confirm
> với `kind: "doctor_document"`. Xem chi tiết mục **11. Upload tài liệu bác sĩ** bên dưới.

### 10.4 Cập nhật tài liệu — `PATCH /api/v1/doctors/{doctor_id}/documents/{id}`

```jsonc
{
  "title": "Giấy phép hành nghề (gia hạn)",
  "object_key": "doctor/document/new-key.pdf",  // optional - upload qua R2 trước
  "expiry_date": "2035-01-15",
  "is_verified": true
}
```

> Khi PATCH `object_key` đổi sang key mới hoặc set về `null`, **BE tự xóa object
> cũ trên R2** sau khi commit DB. FE không cần gọi API delete.

### 10.5 Xóa tài liệu — `DELETE /api/v1/doctors/{doctor_id}/documents/{id}`

> Khi xóa tài liệu, **BE tự xóa object trên R2** (best-effort) sau khi commit DB.

### 10.6 Xác minh tài liệu — `POST /api/v1/doctors/{doctor_id}/documents/{id}/verify`

Chỉ admin.

### 10.7 Admin: Tài liệu sắp hết hạn — `GET /api/v1/documents/expiring`

```jsonc
// GET /api/v1/documents/expiring?days=30
{
  "status": "success",
  "data": [
    {
      "id": 1,
      "doctor": { "id": 1, "full_name": "BS. Nguyen Van A" },
      "document_type": "license",
      "title": "Giấy phép hành nghề",
      "expiry_date": "2026-07-25",
      "is_expiring_soon": true
    }
  ]
}
```

### 10.8 Admin: Tài liệu chưa xác minh — `GET /api/v1/documents/unverified`

---

## 11. Upload tài liệu bác sĩ qua Cloudflare R2

> **Phiên bản: 1.0.0** — Thêm luồng direct-upload cho tài liệu bác sĩ (giấy phép
> hành nghề, bằng cấp, chứng chỉ, hợp đồng, ...). Tận dụng 2 endpoint chung
> `/api/v1/uploads/presign` và `/api/v1/uploads/confirm` với `kind = "doctor_document"`.
>
> Tài liệu liên quan: [`FE_UPLOADS.md`](./FE_UPLOADS.md) (API upload R2),
> [`FE_DEPARTMENT_AVATAR_UPLOAD.md`](./FE_DEPARTMENT_AVATAR_UPLOAD.md) (flow tương tự).

### 11.1 Tổng quan flow

```
┌────────┐  1. presign  ┌──────────┐
│  FE    │ ───────────▶ │   BE     │ → { object_key, url (signed PUT), headers }
│        │ ◀─────────── │          │
│        │  2. PUT file + headers
│        │ ────────────────────────▶ R2
│        │  3. confirm  ┌──────────┐
│        │ ───────────▶ │   BE     │ → { object_key, url (signed GET, TTL 1h) }
│        │ ◀─────────── │          │
│        │  4. POST /doctors/{id}/documents
│        │ ───────────▶ │   BE     │ → { document với object_key + url }
└────────┘              └──────────┘
```

| Method | Path | Mục đích trong luồng tài liệu |
|--------|------|-------------------------------|
| `POST` | `/api/v1/uploads/presign` | Xin URL upload đã ký với `kind: "doctor_document"` |
| `PUT`  | URL trả về ở trên (R2, **không qua BE**) | Upload file thẳng lên R2 |
| `POST` | `/api/v1/uploads/confirm` | Xác nhận + nhận URL đọc |
| `POST` | `/api/v1/doctors/{id}/documents` | Gắn `object_key` vào tài liệu |

### 11.2 Bước 1 — Xin URL upload

```http
POST /api/v1/uploads/presign HTTP/1.1
Authorization: Bearer <token>
Content-Type: application/json

{
  "kind": "doctor_document",       // ← khác biệt so với avatar
  "content_type": "application/pdf",
  "size": 1048576,                 // ≤ R2_MAX_UPLOAD_BYTES (mặc định 15 MB)
  "filename": "license.pdf"
}
```

| Trường | Bắt buộc | Ý nghĩa |
|--------|:--------:|----------|
| `kind` | ✅ | Hằng số `doctor_document` |
| `content_type` | ✅ | MIME trong whitelist: `application/pdf`, `image/jpeg`, `image/png`, `image/webp` |
| `size` | ✅ | Byte. Phải `> 0` và `≤ R2_MAX_UPLOAD_BYTES` (mặc định 15 MB) |
| `filename` | ❌ | Chỉ phục vụ log BE |

**Response** trả về `object_key` có dạng `doctor/document/<uuid>.pdf`. Lưu lại
key này để dùng ở bước 4.

### 11.3 Bước 2 — Upload thẳng lên R2

```js
await fetch(presignData.url, {
  method: "PUT",
  headers: presignData.headers,   // { "Content-Type": "application/pdf" }
  body: file,                     // raw bytes, KHÔNG multipart
});
```

> ⚠️ **Không retry**: presigned URL chỉ dùng được 1 lần cho PUT trong TTL (10 phút).
> Nếu lỗi mạng → xin URL mới (bước 1) rồi PUT lại.
>
> ⚠️ **Giữ nguyên `Content-Type`** như lúc gọi `presign`. Bỏ qua → R2 từ chối
> (`403 SignatureDoesNotMatch`).

### 11.4 Bước 3 — Xác nhận & nhận URL đọc

```http
POST /api/v1/uploads/confirm HTTP/1.1
Authorization: Bearer <token>
Content-Type: application/json

{
  "kind": "doctor_document",
  "object_key": "doctor/document/4f1c2a....pdf",
  "content_type": "application/pdf"
}
```

**Response**:

```jsonc
{
  "status": "success",
  "data": {
    "kind": "doctor_document",
    "object_key": "doctor/document/4f1c2a....pdf",
    "url": "https://...presigned-get...",     // TTL 1 giờ
    "expires_in": 3600
  }
}
```

> `url` chỉ sống `expires_in` giây. Khi hết hạn, gọi lại
> `GET /api/v1/doctors/{id}/documents/{doc_id}` để BE tự derive URL mới từ
> `object_key`.

### 11.5 Bước 4 — Gắn object_key vào tài liệu

```http
POST /api/v1/doctors/1/documents HTTP/1.1
Authorization: Bearer <token>
Content-Type: application/json

{
  "document_type": "license",
  "title": "Giấy phép hành nghề",
  "object_key": "doctor/document/4f1c2a....pdf",
  "issue_date": "2010-01-15",
  "expiry_date": "2030-01-15"
}
```

**Response** trả về document đầy đủ với `url` (presigned GET, TTL 1 giờ).

### 11.6 BE tự xóa object cũ trên R2 (FE không cần gọi delete)

Tương tự avatar khoa, cơ chế dọn dẹp object cũ áp dụng cho `object_key` tài liệu:

- **PATCH `object_key` đổi sang key mới**: BE tự xóa object cũ trên R2 sau khi commit DB.
- **PATCH `object_key: null`**: BE tự xóa object cũ + set cột về `null`.
- **DELETE tài liệu**: BE tự xóa object trên R2 (best-effort) sau khi commit DB.
- **PATCH idempotent**: gửi cùng `object_key` đã có sẵn → BE không xóa gì.
- **Lỗi R2** chỉ log warning, không rollback DB. File orphan có thể dọn sau
  bằng lifecycle policy của bucket.

| Trước PATCH (`object_key`) | Body gửi | Object trên R2 |
|---|---|---|
| `null` | `doctor/document/xyz.pdf` | tạo `xyz.pdf` (không xóa gì) |
| `doctor/document/abc.pdf` | `doctor/document/xyz.pdf` | xóa `abc.pdf`, tạo `xyz.pdf` |
| `doctor/document/abc.pdf` | `abc.pdf` (giữ nguyên) | giữ nguyên (idempotent) |
| `doctor/document/abc.pdf` | `null` | xóa `abc.pdf` |
| `null` | `null` | giữ nguyên |

### 11.7 Ví dụ React hook (drop-in)

```ts
// useDoctorDocumentUpload.ts
import { useCallback, useState } from "react";

type PresignResp = {
  kind: "doctor_document";
  object_key: string;
  method: "PUT";
  url: string;
  headers: Record<string, string>;
  expires_in: number;
};

type ConfirmResp = {
  kind: "doctor_document";
  object_key: string;
  url: string;
  expires_in: number;
};

type DoctorDocument = {
  id: number;
  document_type: string;
  title: string;
  object_key: string | null;
  url: string | null;
  issue_date: string | null;
  expiry_date: string | null;
  is_verified: boolean;
};

const ALLOWED_CT = [
  "image/jpeg", "image/png", "image/webp", "application/pdf"
] as const;
const MAX_BYTES = 15 * 1024 * 1024; // 15 MB

export type UploadStatus =
  | "idle" | "presigning" | "uploading" | "confirming" | "saving"
  | "done" | "error";

export class UploadDocError extends Error {
  readonly step: UploadStatus;
  readonly http?: number;
  constructor(step: UploadStatus, message: string, http?: number) {
    super(message); this.step = step; this.http = http;
  }
}

declare const apiFetch: <T = unknown>(
  path: string,
  init?: { method?: string; body?: BodyInit | null }
) => Promise<{ data: T }>;

export function useDoctorDocumentUpload(doctorId: number) {
  const [status, setStatus] = useState<UploadStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [document, setDocument] = useState<DoctorDocument | null>(null);

  const upload = useCallback(
    async (params: {
      file: File;
      documentType: string;
      title: string;
      issueDate?: string;
      expiryDate?: string;
    }) => {
      const { file, documentType, title, issueDate, expiryDate } = params;
      setError(null);

      try {
        // Validate client
        if (file.size <= 0 || file.size > MAX_BYTES) {
          throw new UploadDocError("presigning", "Tệp vượt quá 15 MB hoặc rỗng.");
        }
        const ct = (file.type || "").toLowerCase();
        if (!ALLOWED_CT.includes(ct as typeof ALLOWED_CT[number])) {
          throw new UploadDocError(
            "presigning", "Chỉ chấp nhận JPG, PNG, WEBP, PDF."
          );
        }

        // 1) presign
        setStatus("presigning");
        const p = await apiFetch<PresignResp>("/api/v1/uploads/presign", {
          method: "POST",
          body: JSON.stringify({
            kind: "doctor_document",
            content_type: file.type,
            size: file.size,
            filename: file.name,
          }),
        });

        // 2) PUT thẳng lên R2
        setStatus("uploading");
        const putRes = await fetch(p.data.url, {
          method: "PUT",
          headers: p.data.headers,
          body: file,
        });
        if (!putRes.ok) {
          throw new UploadDocError("uploading", `R2 từ chối (${putRes.status}).`, putRes.status);
        }

        // 3) confirm
        setStatus("confirming");
        await apiFetch<ConfirmResp>("/api/v1/uploads/confirm", {
          method: "POST",
          body: JSON.stringify({
            kind: "doctor_document",
            object_key: p.data.object_key,
            content_type: file.type,
          }),
        });

        // 4) POST tạo tài liệu
        setStatus("saving");
        const d = await apiFetch<DoctorDocument>(
          `/api/v1/doctors/${doctorId}/documents`,
          {
            method: "POST",
            body: JSON.stringify({
              document_type: documentType,
              title: title,
              object_key: p.data.object_key,
              issue_date: issueDate,
              expiry_date: expiryDate,
            }),
          }
        );
        setDocument(d.data);
        setStatus("done");
        return d.data;
      } catch (e) {
        const msg = e instanceof UploadDocError
          ? e.message
          : e instanceof Error
          ? e.message
          : "Upload thất bại.";
        setError(msg);
        setStatus("error");
        throw e;
      }
    },
    [doctorId]
  );

  return { upload, status, error, document };
}
```

### 11.8 Lỗi thường gặp

| Bước thất bại | HTTP / Mã | Gợi ý xử lý FE |
|---------------|-----------|----------------|
| client | `size > 15 MB` hoặc `size = 0` | "Tệp vượt quá 15 MB." |
| client | `content_type` không nằm whitelist | "Chỉ chấp nhận JPG, PNG, WEBP, PDF." |
| presign | `400 upload_kind_unsupported` | "Loại upload không được hỗ trợ." |
| presign | `400 upload_content_type_unsupported` | "Định dạng tệp không được phép." |
| presign | `400 upload_too_large` | "Tệp vượt quá kích thước cho phép." |
| presign | `401 auth_unauthorized` | Đăng nhập lại. |
| presign | `503` | "Dịch vụ upload chưa sẵn sàng, thử lại sau." |
| uploading | `403 SignatureDoesNotMatch` | Lấy đúng `data.headers` từ presign. |
| uploading | `403 RequestExpired` | Xin `presign` mới + PUT lại. |
| uploading | `0` / NetworkError | "Mất kết nối tới R2." |
| confirming | `404 upload_object_not_found` | "Upload chưa tới R2 — thử lại." |
| saving | `400 document_type: duplicate_license` | Bác sĩ đã có giấy phép → PATCH thay vì POST. |
| saving | `403 permission_denied` | "Bạn không có quyền tạo tài liệu." |
| saving | `404 doctor_not_found` | "Bác sĩ không tồn tại hoặc đã bị xoá." |
| saving | `422` | Hiển thị message BE trả về. |

### 11.9 Checklist triển khai nhanh

- [ ] `apiFetch` có kèm `Authorization: Bearer <token>`.
- [ ] Validate content-type (`image/jpeg`, `image/png`, `image/webp`, `application/pdf`) & size (≤ 15 MB) phía client.
- [ ] Lưu `object_key` sau bước 1; gắn vào tài liệu ở bước 4.
- [ ] Với `document_type: "license"`, kiểm tra backend trả lỗi `duplicate_license` nếu đã có → dùng PATCH thay vì POST.
- [ ] Khi đổi file: chỉ cần PATCH `object_key` mới — BE tự xóa object cũ trên R2.
- [ ] Khi xóa tài liệu: gọi DELETE — BE tự xóa object trên R2.
- [ ] File lỗi → dùng placeholder + nút "Thử lại".

---

## 12. Thống kê Bác sĩ

### 11.1 Mô hình DoctorStatistics

| Trường | Kiểu | Ý nghĩa |
|--------|------|----------|
| `doctor_id` | int | FK tới Doctor (unique) |
| `total_appointments` | int | Tổng số lịch hẹn |
| `completed_appointments` | int | Lịch hẹn hoàn thành |
| `cancelled_appointments` | int | Lịch hẹn hủy |
| `completion_rate` | float | Tỷ lệ hoàn thành (%) |
| `cancellation_rate` | float | Tỷ lệ hủy (%) |
| `average_rating` | float | Điểm TB (1-5) |
| `total_ratings` | int | Số lượt đánh giá |
| `average_consultation_time_minutes` | int | Thời gian khám TB (phút) |
| `patient_satisfaction_score` | float | Điểm hài lòng (0-100) |
| `last_calculated_at` | string (ISO) | Thời điểm tính cuối |

### 11.2 Xem thống kê — `GET /api/v1/doctors/{id}/statistics`

```jsonc
{
  "status": "success",
  "data": {
    "doctor_id": 1,
    "total_appointments": 150,
    "completed_appointments": 140,
    "cancelled_appointments": 10,
    "completion_rate": 93.33,
    "cancellation_rate": 6.67,
    "average_rating": 4.5,
    "total_ratings": 50,
    "average_consultation_time_minutes": 15,
    "patient_satisfaction_score": 92.5,
    "last_calculated_at": "2026-07-09T10:00:00+00:00"
  }
}
```

### 11.3 Tính lại thống kê — `POST /api/v1/doctors/{id}/statistics/recalculate`

Chỉ admin. Tính lại từ dữ liệu thực tế.

### 11.4 Top bác sĩ — `GET /api/v1/doctors/statistics/top-rated`

```jsonc
// GET /api/v1/doctors/statistics/top-rated?limit=10
{
  "status": "success",
  "data": [
    { "doctor_id": 1, "average_rating": 4.9, "total_ratings": 100 }
  ]
}
```

### 11.5 Bác sĩ nhiều lịch hẹn nhất — `GET /api/v1/doctors/statistics/most-active`

```jsonc
// GET /api/v1/doctors/statistics/most-active?limit=10
{
  "status": "success",
  "data": [
    { "doctor_id": 1, "total_appointments": 500, "completed_appointments": 480 }
  ]
}
```

---

## 13. Đánh giá Bác sĩ

### 12.1 Mô hình DoctorRating

| Trường | Kiểu | Ý nghĩa |
|--------|------|----------|
| `id` | int | Khóa chính |
| `doctor_id` | int | FK tới Doctor |
| `patient_id` | int | FK tới Patient |
| `patient` | object | `{id, full_name}` |
| `appointment_id` | int | FK tới Appointment (nullable) |
| `rating` | int | 1-5 sao |
| `comment` | string | Nhận xét (≤2000) |
| `created_at` / `updated_at` | string (ISO) | Thời điểm tạo/cập nhật |

### 12.2 Tạo đánh giá — `POST /api/v1/ratings`

Cần permission `rating:write`.

```jsonc
{
  "doctor_id": 1,              // bắt buộc
  "patient_id": 1,             // bắt buộc
  "appointment_id": 10,        // tùy chọn
  "rating": 5,                // bắt buộc (1-5)
  "comment": "Bác sĩ rất tận tâm, khám kỹ lưỡng."
}
```

> Mỗi lịch hẹn chỉ được đánh giá **1 lần**.

### 12.3 Xem đánh giá của bác sĩ — `GET /api/v1/doctors/{id}/ratings`

Cần permission `rating:read`.

```jsonc
{
  "status": "success",
  "data": [
    {
      "id": 1,
      "rating": 5,
      "comment": "Bác sĩ rất tận tâm",
      "patient": { "id": 1, "full_name": "Nguyen Thi B" },
      "created_at": "2026-07-09T10:00:00+00:00"
    }
  ],
  "meta": { "page": 1, "size": 20, "totalPage": 3 }
}
```

### 12.4 Phân bố đánh giá — `GET /api/v1/doctors/{id}/ratings/distribution`

**Public endpoint** — không cần auth.

```jsonc
{
  "status": "success",
  "data": {
    "1": 2,   // 1 sao: 2 đánh giá
    "2": 5,   // 2 sao: 5 đánh giá
    "3": 10,
    "4": 30,
    "5": 53   // 5 sao: 53 đánh giá
  }
}
```

### 12.5 Cập nhật đánh giá — `PATCH /api/v1/ratings/{id}`

Chỉ người tạo hoặc admin được sửa.

```jsonc
{
  "rating": 4,
  "comment": "Cập nhật: bác sĩ vẫn tốt nhưng chờ lâu."
}
```

### 12.6 Xóa đánh giá — `DELETE /api/v1/ratings/{id}`

Chỉ admin.

---

## 14. Tóm tắt Endpoint

### Doctor CRUD

| Method | Path | Permission | Mô tả |
|--------|------|------------|--------|
| `POST` | `/api/v1/doctors` | `department:manage` | Tạo bác sĩ |
| `GET` | `/api/v1/doctors` | `department:manage` | Danh sách bác sĩ |
| `GET` | `/api/v1/doctors/{id}` | `department:manage` | Chi tiết bác sĩ |
| `PATCH` | `/api/v1/doctors/{id}` | `department:manage` | Cập nhật bác sĩ (BE tự xóa avatar cũ trên R2) |
| `DELETE` | `/api/v1/doctors/{id}` | `department:manage` | Xóa bác sĩ (soft, BE tự xóa avatar cũ trên R2) |
| `GET` | `/api/v1/doctors/search` | `department:manage` | Tìm kiếm bác sĩ |
| `GET` | `/api/v1/doctors/expiring-licenses` | `department:manage` | GPL hết hạn |

### Doctor Documents

| Method | Path | Permission | Mô tả |
|--------|------|------------|--------|
| `GET` | `/api/v1/doctors/{id}/documents` | `department:manage` | Danh sách tài liệu |
| `POST` | `/api/v1/doctors/{id}/documents` | `department:manage` | Tạo tài liệu (cần `object_key` đã upload qua R2) |
| `PATCH` | `/api/v1/doctors/{id}/documents/{doc_id}` | `department:manage` | Cập nhật tài liệu (BE tự xóa object cũ trên R2) |
| `DELETE` | `/api/v1/doctors/{id}/documents/{doc_id}` | `department:manage` | Xóa tài liệu (BE tự xóa object cũ trên R2) |
| `POST` | `/api/v1/doctors/{id}/documents/{doc_id}/verify` | `department:manage` | Xác minh tài liệu |
| `GET` | `/api/v1/documents/expiring` | `department:manage` | Tài liệu hết hạn |
| `GET` | `/api/v1/documents/unverified` | `department:manage` | Tài liệu chưa xác minh |

### Upload (R2)

| Method | Path | Permission | Mô tả |
|--------|------|------------|--------|
| `POST` | `/api/v1/uploads/presign` | đăng nhập | Xin URL upload (`kind: "doctor_document"`) |
| `POST` | `/api/v1/uploads/confirm` | đăng nhập | Xác nhận & nhận URL đọc |

### Statistics

| Method | Path | Permission | Mô tả |
|--------|------|------------|--------|
| `GET` | `/api/v1/doctors/{id}/statistics` | `department:manage` | Xem thống kê |
| `POST` | `/api/v1/doctors/{id}/statistics/recalculate` | `department:manage` | Tính lại thống kê |
| `GET` | `/api/v1/doctors/statistics/top-rated` | `department:manage` | Top bác sĩ đánh giá cao |
| `GET` | `/api/v1/doctors/statistics/most-active` | `department:manage` | Top bác sĩ nhiều lịch hẹn |

### Ratings

| Method | Path | Permission | Mô tả |
|--------|------|------------|--------|
| `POST` | `/api/v1/ratings` | `rating:write` | Tạo đánh giá |
| `GET` | `/api/v1/doctors/{id}/ratings` | `rating:read` | Xem đánh giá |
| `GET` | `/api/v1/doctors/{id}/ratings/distribution` | public | Phân bố đánh giá |
| `GET` | `/api/v1/ratings/{id}` | `rating:read` | Chi tiết đánh giá |
| `PATCH` | `/api/v1/ratings/{id}` | `rating:write` | Cập nhật đánh giá |
| `DELETE` | `/api/v1/ratings/{id}` | `department:manage` | Xóa đánh giá |

---

## 15. UI Components & Screen Flow

### 14.1 Danh sách Bác sĩ

```
┌─────────────────────────────────────────────────────────────┐
│ Quản lý Bác sĩ                              [+ Thêm bác sĩ] │
├─────────────────────────────────────────────────────────────┤
│ 🔍 Tìm kiếm...          │ Khoa: [Tất cả ▼] │ [Tìm kiếm] │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────┐│
│ │ 👤 BS. Nguyen Van A                                    ││
│ │    Tim mạch • Thạc sĩ                    🟢 Hoạt động  ││
│ │    📞 0912345678 • 📧 nvana@hospital.com               ││
│ │    📋 GPL: GD-00012345 (còn 5 năm)                     ││
│ │                                              [Chi tiết] ││
│ └─────────────────────────────────────────────────────────┘│
│ ┌─────────────────────────────────────────────────────────┐│
│ │ 👤 BS. Tran Thi B                                      ││
│ │    Nội tổng quát • Bác sĩ                  🟡 Nghỉ phép││
│ │    📞 0987654321                                       ││
│ │                                              [Chi tiết] ││
│ └─────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────┤
│                           Trang 1/5  [<] [1] [2] [3] [>]  │
└─────────────────────────────────────────────────────────────┘
```

**Components:**
- Search bar với debounce
- Filter dropdown: Khoa, Trạng thái (Hoạt động/Không hoạt động)
- Doctor card với avatar, info, quick actions
- Pagination

### 14.2 Form Tạo/Sửa Bác sĩ

```
┌─────────────────────────────────────────────────────────────┐
│ Thêm Bác sĩ Mới                                    [✕]    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ 📋 Thông tin cơ bản                                         │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ Họ tên *         [________________________]            ││
│ │ Khoa *           [Chọn khoa          ▼]                 ││
│ │ Chức danh        [________________________]            ││
│ └─────────────────────────────────────────────────────────┘│
│                                                             │
│ 📷 Thông tin cá nhân                                        │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ Số điện thoại   [________________________]            ││
│ │ Email           [________________________]            ││
│ │ Ngày sinh       [📅 Chọn ngày        ]                 ││
│ │ Giới tính       [Chọn giới tính     ▼]                 ││
│ │ Địa chỉ         [________________________]            ││
│ │ Ảnh đại diện   [📤 Upload ảnh       ]                 ││
│ └─────────────────────────────────────────────────────────┘│
│                                                             │
│ 🏥 Thông tin chuyên môn                                    │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ Số GPLHN *       [________________________]            ││
│ │ Ngày cấp GPL     [📅 Chọn ngày        ]                 ││
│ │ Ngày hết hạn     [📅 Chọn ngày        ]                 ││
│ │ Chuyên khoa      [________________________]            ││
│ │ CK phụ           [+ Thêm chuyên khoa phụ]              ││
│ │ Trình độ         [Đại học Y      +] [Thạc sĩ  +]      ││
│ │ Năm kinh nghiệm  [____15____]                          ││
│ │ Nơi đào tạo      [BV Bạch Mai   +] [BV TW     +]      ││
│ └─────────────────────────────────────────────────────────┘│
│                                                             │
│ 💼 Thông tin hành chính                                    │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ Loại hình      [Full-time      ▼]                      ││
│ │ Ngày vào làm   [📅 Chọn ngày        ]                   ││
│ │ KT HĐ           [📅 Chọn ngày        ]                 ││
│ │ ☐ Nhận bệnh nhân mới                                    ││
│ └─────────────────────────────────────────────────────────┘│
│                                                             │
│                              [Hủy]  [💾 Lưu bác sĩ]         │
└─────────────────────────────────────────────────────────────┘
```

### 14.3 Chi tiết Bác sĩ

```
┌─────────────────────────────────────────────────────────────┐
│ 👤 BS. Nguyen Van A                          [✏️ Sửa] [🗑️]│
├─────────────────────────────────────────────────────────────┤
│ ┌──────────────────┐  ┌───────────────────────────────────┐│
│ │                  │  │ Khoa: Tim mạch (CK-001)          ││
│ │   [Avatar]       │  │ Chức danh: Thạc sĩ                ││
│ │   120x120        │  │ 🟢 Hoạt động                      ││
│ │                  │  │ 📞 0912345678                     ││
│ └──────────────────┘  │ 📧 nvana@hospital.com              ││
│                       │ 📍 123 Nguyễn Trãi, Q1            ││
│                       └───────────────────────────────────┘│
├─────────────────────────────────────────────────────────────┤
│ [📋 Thông tin] [📄 Tài liệu] [📊 Thống kê] [⭐ Đánh giá] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ 📋 Giấy phép hành nghề                                     │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ Số GPL: GD-00012345    Ngày cấp: 15/01/2010           ││
│ │ ⚠️ Cảnh báo: Sắp hết hạn (còn 30 ngày)                 ││
│ └─────────────────────────────────────────────────────────┘│
│                                                             │
│ 🏥 Chuyên môn                                              │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ Chuyên khoa: Tim mạch                                    ││
│ │ CK phụ: Nội soi tim, Siêu âm tim                        ││
│ │ Kinh nghiệm: 15 năm                                     ││
│ │ Trình độ: ĐH Y Hà Nội, Thạc sĩ Tim mạch                ││
│ └─────────────────────────────────────────────────────────┘│
│                                                             │
│ 💼 Hành chính                                              │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ Full-time • Từ 01/03/2010                               ││
│ │ ☑️ Đang nhận bệnh nhân mới                              ││
│ └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### 14.4 Quản lý Tài liệu

```
┌─────────────────────────────────────────────────────────────┐
│ Tài liệu BS. Nguyen Van A                    [+ Thêm]   │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────┐│
│ │ 📄 Giấy phép hành nghề                    ✅ Đã xác minh││
│ │    Phát hành: 15/01/2010  •  Hết hạn: 15/01/2030      ││
│ │    [👁️ Xem] [📥 Tải] [✏️ Sửa] [🗑️]                    ││
│ └─────────────────────────────────────────────────────────┘│
│ ┌─────────────────────────────────────────────────────────┐│
│ │ 🎓 Bằng tốt nghiệp ĐH Y Hà Nội            ✅ Đã xác minh││
│ │    Phát hành: 30/06/2008                           [✏️] ││
│ └─────────────────────────────────────────────────────────┘│
│ ┌─────────────────────────────────────────────────────────┐│
│ │ 📜 Chứng chỉ hành nghề                    ❌ Chưa xác ││
│ │    [✅ Xác minh]                                      ││
│ └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### 14.5 Thống kê Bác sĩ

```
┌─────────────────────────────────────────────────────────────┐
│ Thống kê BS. Nguyen Van A                                  │
├─────────────────────────────────────────────────────────────┤
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│ │   📅     │ │   ✅     │ │   ⭐     │ │   💯     │      │
│ │   150    │ │   140    │ │   4.5    │ │   92.5   │      │
│ │Tổng lịch│ │Hoàn thành│ │Điểm TB   │ │Hài lòng  │      │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
│                                                             │
│ Tỷ lệ hoàn thành: ████████████████░░░░░ 93.3%             │
│ Tỷ lệ hủy:       ██░░░░░░░░░░░░░░░░░░░░ 6.7%             │
│                                                             │
│ Phân bố đánh giá:                                          │
│ ⭐⭐⭐⭐⭐ ████████████████████████████ 53                    │
│ ⭐⭐⭐⭐  ████████████░░░░░░░░░░░░░░░░ 30                   │
│ ⭐⭐⭐   ████░░░░░░░░░░░░░░░░░░░░░░░░ 10                   │
│ ⭐⭐    ███░░░░░░░░░░░░░░░░░░░░░░░░░░ 5                    │
│ ⭐      ██░░░░░░░░░░░░░░░░░░░░░░░░░░░ 2                    │
│                                        [🔄 Tính lại]       │
└─────────────────────────────────────────────────────────────┘
```

### 14.6 Đánh giá Bác sĩ

```
┌─────────────────────────────────────────────────────────────┐
│ Đánh giá BS. Nguyen Van A                                  │
├─────────────────────────────────────────────────────────────┤
│ ⭐ 4.5/5 (50 đánh giá)           [Xem phân bố đánh giá]  │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────┐│
│ │ ⭐⭐⭐⭐⭐  Nguyen Thi B                                  ││
│ │         "Bác sĩ rất tận tâm, khám kỹ lưỡng."            ││
│ │         09/07/2026                                       ││
│ └─────────────────────────────────────────────────────────┘│
│ ┌─────────────────────────────────────────────────────────┐│
│ │ ⭐⭐⭐⭐   Tran Van C                                    ││
│ │         "Khám nhanh, nhưng hơi đông."                    ││
│ │         08/07/2026                                       ││
│ └─────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────┤
│                           Trang 1/3  [<] [1] [2] [3] [>]  │
└─────────────────────────────────────────────────────────────┘
```

---

## 16. Lịch sử thay đổi

| Phiên bản | Thay đổi |
|-----------|----------|
| **1.1.0** | Thêm luồng upload tài liệu bác sĩ qua Cloudflare R2 (kind = `doctor_document`). BE tự xóa object cũ trên R2 khi PATCH/DELETE tài liệu. Cập nhật PATCH/DELETE Doctor để tự dọn dẹp avatar cũ trên R2. Thêm kind `doctor_avatar`. |
| **1.0.0** | Bản đầu: CRUD bác sĩ, quản lý tài liệu, thống kê, đánh giá |
