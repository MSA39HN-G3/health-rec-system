# Hướng dẫn FE: Form Tạo mới & Chỉnh sửa Bác sĩ

> **Phiên bản: 1.1.0** — Tài liệu chuyên biệt cho **2 màn hình form**:
> - Tạo mới bác sĩ → `POST /api/v1/doctors`
> - Chỉnh sửa thông tin bác sĩ → `PATCH /api/v1/doctors/{id}`
>
> Bao gồm toàn bộ field trong form + upload avatar qua Cloudflare R2. Các endpoint
> không thuộc form (list, detail, delete, search, statistics, documents)
> xem [`FE_DOCTOR.md`](./FE_DOCTOR.md).
>
> Tài liệu liên quan:
> - [`FE_DOCTOR.md`](./FE_DOCTOR.md) — model `Doctor` đầy đủ & tất cả endpoint
> - [`FE_UPLOADS.md`](./FE_UPLOADS.md) — flow upload R2 (presign → PUT → confirm)
> - [`FE_DEPARTMENT_AVATAR_UPLOAD.md`](./FE_DEPARTMENT_AVATAR_UPLOAD.md) — pattern upload avatar (tương tự doctor_avatar)
> - [`FE_RBAC.md`](./FE_RBAC.md) — quyền `department:manage` (staff & admin)
> - [`FE_AUTH_TOKEN.md`](./FE_AUTH_TOKEN.md) — Bearer token & 401/403

---

## 1. Phạm vi 2 màn hình form

### 1.1 Màn "Thêm bác sĩ mới"

| Item | Mô tả |
|---|---|
| Route | `/staff/doctors/new` |
| API | `POST /api/v1/doctors` |
| Permission | `department:manage` |
| Kết quả thành công | Toast "Đã tạo bác sĩ." → redirect về danh sách |
| Kết quả lỗi | interceptor toast tự động, highlight field lỗi (422) |

### 1.2 Màn "Chỉnh sửa bác sĩ"

| Item | Mô tả |
|---|---|
| Route | `/staff/doctors/:id/edit` |
| API | `GET /api/v1/doctors/{id}` (load lần đầu) → `PATCH /api/v1/doctors/{id}` |
| Permission | `department:manage` |
| Kết quả thành công | Toast "Đã cập nhật bác sĩ." → quay về chi tiết bác sĩ |
| Kết quả lỗi | interceptor toast tự động |

---

## 2. Layout form & nhóm trường

Form chia 5 khối (theo cấu trúc `Doctor` model đã chốt ở `FE_DOCTOR.md` §2):

| # | Khối | Bắt buộc tối thiểu |
|---|---|---|
| 1 | Thông tin cơ bản | `full_name`, `department_id` |
| 2 | Thông tin cá nhân (kèm avatar) | — |
| 3 | Thông tin chuyên môn | — |
| 5 | Thông tin hành chính | — |
| 4 | Cấu hình hệ thống (`is_active`) | — |

> **Lưu ý**: khối "4" (avatar) đã được gộp vào khối "2" (cá nhân) vì cùng nhóm UI.
> Khối "5" (hành chính) là khối cuối. Không có khối "4" riêng.

---

## 3. Endpoint `POST /api/v1/doctors` — Tạo bác sĩ mới

### 3.1 Request

```http
POST /api/v1/doctors HTTP/1.1
Authorization: Bearer <access_token>
Content-Type: application/json
```

Toàn bộ endpoint yêu cầu `department:manage` (403 nếu thiếu).

### 3.2 Body — tất cả field đều là **tùy chọn ngoại trừ `full_name` và `department_id`**

```jsonc
{
  // ===== Khối 1 — Thông tin cơ bản =====
  "full_name": "Nguyễn Văn A",         // bắt buộc
  "department_id": 1,                   // bắt buộc — FK tới Department
  "title": "Thạc sĩ",                   // chức danh

  // ===== Khối 2 — Thông tin cá nhân =====
  "phone": "0912345678",
  "email": "nvana@hospital.com",
  "avatar_object_key": "doctor/avatar/4f1c2a....png",  // từ flow upload R2
  "date_of_birth": "1980-05-15",        // ISO date (YYYY-MM-DD)
  "gender": "male",                      // "male" | "female" | "other"
  "address": "123 Nguyễn Trãi, Q1, TP.HCM",

  // ===== Khối 3 — Chuyên môn =====
  "license_number": "GD-00012345",
  "license_issue_date": "2010-01-15",
  "license_expiry_date": "2030-01-15",
  "specialization": "Tim mạch",
  "sub_specializations": ["Nội soi tim", "Siêu âm tim"],
  "education": ["Đại học Y Hà Nội", "Thạc sĩ Tim mạch"],
  "experience_years": 15,
  "training_institutions": ["BV Bạch Mai", "BV Trung ương"],

  // ===== Khối 5 — Hành chính =====
  "employment_type": "full_time",        // "full_time" | "part_time" | "contract"
  "hire_date": "2010-03-01",
  "contract_end_date": "2030-03-01",
  "is_accepting_new_patients": true
}
```

> **`is_active`** không gửi ở POST — BE mặc định `true` (xem §3.5).
> **`is_active = false` ngay khi tạo** hiếm gặp, cần nghiệp vụ đặc biệt — nếu cần, PATCH sau.

### 3.3 Response — `201 Created`

```jsonc
{
  "status": "success",
  "code": "201",
  "message": "Tạo bác sĩ thành công.",
  "data": {
    "id": 1,
    "full_name": "Nguyễn Văn A",
    "department_id": 1,
    "department": { "id": 1, "name": "Tim mạch", "code": "CK-001" },
    "title": "Thạc sĩ",
    "phone": "0912345678",
    "email": "nvana@hospital.com",
    "avatar_object_key": "doctor/avatar/4f1c2a....png",
    "avatar_url": "https://r2.example.com/doctor/avatar/4f1c2a....png?X-Amz-Expires=3600",
    "date_of_birth": "1980-05-15",
    "gender": "male",
    "address": "...",
    "license_number": "GD-00012345",
    // ... toàn bộ field
    "is_active": true,
    "is_accepting_new_patients": true,
    "created_at": "2026-07-12T10:00:00+00:00",
    "updated_at": "2026-07-12T10:00:00+00:00"
  },
  "meta": null
}
```

### 3.4 Validation rules (BE side — FE có thể validate sớm)

| Trường | Ràng buộc |
|---|---|
| `full_name` | bắt buộc khác rỗng, ≤ 255 ký tự |
| `department_id` | bắt buộc, `> 0`, FK tới `departments.id` |
| `email` | định dạng email nếu gửi |
| `date_of_birth` / `license_*` / `hire_date` / `contract_end_date` | ISO date `YYYY-MM-DD` |
| `gender` | ∈ `{male, female, other}` |
| `employment_type` | ∈ `{full_time, part_time, contract}` |
| `experience_years` | số nguyên ≥ 0 |
| `sub_specializations` / `education` / `training_institutions` | mảng chuỗi, mỗi phần tử ≤ 255 ký tự |

### 3.5 Mặc định BE tự set khi tạo

| Trường | Mặc định |
|---|---|
| `is_active` | `true` |
| `is_accepting_new_patients` | `true` |
| `avatar_url` | derive từ `avatar_object_key` (presigned GET, TTL 1h); `null` nếu không gửi key |
| `sub_specializations` / `education` / `training_institutions` | `[]` nếu không gửi |

### 3.6 Các lỗi thường gặp

| HTTP | `code` | Khi nào | FE nên làm |
|:---:|---|---|---|
| **201** | — | Tạo thành công | toast + redirect |
| **403** | `PERM_001` / `errors.forbidden` | Thiếu permission `department:manage` | hiện "Bạn không có quyền…" |
| **422** | `errors.department_not_found` | `department_id` không tồn tại | highlight field `department_id` |
| **422** | `errors.doctor_duplicate_license` | `license_number` đã tồn tại ở bác sĩ khác | highlight field `license_number`, gợi ý "Số GPL này đã thuộc về bác sĩ khác." |
| **422** | `errors.doctor_duplicate_email` | `email` đã được dùng bởi bác sĩ khác (case-insensitive) | highlight `email` |
| **422** | `errors.invalid_date_format` | `date_of_birth` / `license_*_date` / `hire_date` / `contract_end_date` sai format | highlight field ngày |
| **422** | `VAL_001` (`invalid_choice`) | `gender` ∉ `{male,female,other}` hoặc `employment_type` ∉ `{full_time,part_time,contract}` | highlight field tương ứng |
| **422** | `VAL_001` (`invalid_list` / `invalid_item`) | Mảng (`sub_specializations`, `education`, `training_institutions`) không hợp lệ | highlight field tương ứng |

Ví dụ body lỗi 422:

```jsonc
{
  "status": "error",
  "code": "422",
  "message": "Dữ liệu không hợp lệ.",
  "data": {
    "full_name": "required",
    "department_id": "required",
    "license_number": "duplicate"
  },
  "meta": null
}
```

---

## 4. Endpoint `PATCH /api/v1/doctors/{id}` — Chỉnh sửa

### 4.1 Request

```http
PATCH /api/v1/doctors/1 HTTP/1.1
Authorization: Bearer <access_token>
Content-Type: application/json
```

Cần `department:manage`.

### 4.2 Body — **partial update** (tất cả field đều tùy chọn)

```jsonc
// Ví dụ chỉ cập nhật vài field
{
  "full_name": "Nguyễn Văn B",
  "title": "Phó Giáo sư",
  "phone": "0987654321",
  "license_expiry_date": "2035-01-15",
  "sub_specializations": ["Nội soi tim", "Phẫu thuật tim"],
  "is_accepting_new_patients": false
}
```

### 4.3 Quy tắc từng trường

| Nhóm | Trường | Quy tắc |
|---|---|---|
| Required | `full_name`, `department_id` | **Không cho gửi `null`** nếu muốn giữ — bỏ qua key để giữ nguyên |
| Nullable | `phone`, `email`, `date_of_birth`, `gender`, `address`, `license_number`, `license_issue_date`, `license_expiry_date`, `specialization`, `employment_type`, `hire_date`, `contract_end_date`, `is_accepting_new_patients` | Bỏ qua = giữ nguyên. Gửi chuỗi/giá trị để thay. Gửi `null` để **xóa** (với field cho phép null trong DB). |
| Arrays | `sub_specializations`, `education`, `training_institutions` | Mảng chuỗi — **thay thế toàn bộ**. Gửi `[]` để xóa hết. |
| Avatar | `avatar_object_key` | Gửi key mới để đổi ảnh. Gửi `null` để xóa ảnh. **BE tự xóa object cũ trên R2** sau commit DB. Idempotent: gửi đúng key hiện tại → BE không xóa gì. |
| Trạng thái | `is_active` | `true` / `false`. Bỏ qua = giữ nguyên. **FE set trực tiếp qua form** (không còn ràng buộc `head_doctor` sau refactor 1a2b3c4d5e6f). |

### 4.4 Response — `200 OK`

```jsonc
{
  "status": "success",
  "code": "200",
  "message": "Cập nhật bác sĩ thành công.",
  "data": { /* doctor object đầy đủ sau cập nhật */ },
  "meta": null
}
```

### 4.5 Body rỗng (không có field nào gửi)

`PATCH /doctors/1` với body `{}` → `422 "Dữ liệu không hợp lệ."`.
FE nên disable nút "Lưu" khi người dùng chưa thay đổi gì (so sánh với giá trị ban đầu).

### 4.6 Các lỗi thường gặp

| HTTP | `code` | Khi nào | FE nên làm |
|:---:|---|---|---|
| **200** | — | Cập nhật thành công | toast + đóng form hoặc quay lại detail |
| **403** | `errors.forbidden` | Thiếu `department:manage` | hiện "Bạn không có quyền…" |
| **404** | `errors.doctor_not_found` | `doctor_id` không tồn tại hoặc đã soft-delete | hiện "Không tìm thấy bác sĩ." + nút quay lại |
| **422** | `errors.doctor_duplicate_license` | Đổi sang `license_number` đã thuộc bác sĩ khác | highlight `license_number` |
| **422** | `errors.doctor_duplicate_email` | Đổi sang `email` đã thuộc bác sĩ khác (case-insensitive) | highlight `email` |
| **422** | `errors.department_not_found` | `department_id` mới không tồn tại | highlight `department_id` |
| **422** | `errors.invalid_date_format` | Một trong các trường ngày sai format | highlight field ngày |
| **422** | `VAL_001` (`invalid_choice`) | `gender` / `employment_type` không hợp lệ | highlight field tương ứng |
| **422** | `VAL_001` (`invalid_list` / `invalid_item`) | Mảng không hợp lệ | highlight field tương ứng |
| **422** | `VAL_001` (`_body: no_fields`) | Body rỗng — không có field nào để cập nhật | hiện "Không có thay đổi nào để lưu." (FE nên disable nút Lưu) |

---

## 5. Lookup endpoints để populate dropdown trong form

Form cần load **danh sách khoa** để user chọn `department_id`. Khi vào form
mode "edit", load **chi tiết bác sĩ** để pre-fill.

### 5.1 Lấy danh sách khoa (cho dropdown "Khoa")

| Item | Giá trị |
|---|---|
| API | `GET /api/v1/departments?page=1&size=100` |
| Permission | `department:manage` |
| Caching | FE cache 5 phút (hoặc SWR revalidate khi mở form) |

Xem chi tiết response: [`FE_DEPARTMENT.md` §4](./FE_DEPARTMENT.md).

Lưu ý: có thể dùng `?size=100` (max) trong form vì dropdown hiếm khi > 100 khoa.
Nếu muốn filter chỉ lấy khoa đang hoạt động (`is_active = true`) → truyền query
filter nếu BE hỗ trợ; nếu chưa, FE tự filter ở client sau khi load.

### 5.2 Lấy chi tiết bác sĩ (cho mode Edit)

| Item | Giá trị |
|---|---|
| API | `GET /api/v1/doctors/{id}` |
| Permission | `department:manage` |
| Optional query | `include_stats=true` (không cần cho form; `include_ratings` đã bỏ từ refactor 1c2d3e4f5a6b) |

Response trả full doctor object — pre-fill vào form state.

Khi BE trả `404 doctor_not_found` → form nên hiển thị "Không tìm thấy bác sĩ"
kèm nút "Quay lại danh sách".

---

## 6. Upload avatar bác sĩ qua Cloudflare R2

`avatar_object_key` cần được upload qua R2 **trước** khi gửi lên BE
(khi tạo mới hoặc khi đổi ảnh ở edit mode).

### 6.1 Kind sử dụng

| `kind` | Mục đích | Field lưu |
|---|---|---|
| `doctor_avatar` | Ảnh đại diện bác sĩ | `doctors.avatar_object_key` |

Pattern giống `department_avatar` xem [`FE_DEPARTMENT_AVATAR_UPLOAD.md`](./FE_DEPARTMENT_AVATAR_UPLOAD.md).

### 6.2 Flow 4 bước

```
┌────────┐  1. presign  ┌──────────┐
│  FE    │ ───────────▶ │   BE     │  → { object_key, url (PUT), headers }
│        │ ◀─────────── │          │
│        │  2. PUT file + headers
│        │ ────────────────────────▶ R2
│        │  3. confirm  ┌──────────┐
│        │ ───────────▶ │   BE     │  → { object_key, url (GET, TTL 1h) }
│        │ ◀─────────── │          │
│        │  4. PATCH /doctors/{id} { avatar_object_key }
│        │ ───────────▶ │   BE     │  → doctor mới với avatar_url
└────────┘              └──────────┘
```

> Khi **edit**: bước 4 là `PATCH` ngay (không chờ user bấm "Lưu" form chính) — đây
> là pattern thống nhất với `department_avatar` (avatar auto-save).
>
> Khi **create**: có 2 lựa chọn:
> - (a) Upload avatar trước, lưu `object_key` trong state form, gửi kèm `POST /doctors`.
> - (b) Tạo bác sĩ không avatar, sau khi tạo xong dùng nút "Đổi ảnh" → `PATCH`
>   `avatar_object_key`. (Khuyến nghị — tránh upload rồi user hủy form.)

### 6.3 Bước 1 — Xin URL upload

```http
POST /api/v1/uploads/presign HTTP/1.1
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "kind": "doctor_avatar",
  "content_type": "image/png",
  "size": 524288,
  "filename": "bs-anh.png"
}
```

| Field | Bắt buộc | Ý nghĩa |
|---|:---:|---|
| `kind` | ✅ | Hằng số `doctor_avatar` |
| `content_type` | ✅ | MIME trong whitelist: `image/jpeg`, `image/png`, `image/webp` |
| `size` | ✅ | Byte, `> 0` và `≤ R2_MAX_UPLOAD_BYTES` (mặc định **15 MB** — nhưng avatar nên giới hạn **≤ 5 MB** ở FE) |
| `filename` | ❌ | Chỉ phục vụ log BE |

**Response** trả `object_key` dạng `doctor/avatar/<uuid>.<ext>`. Lưu key này
trong state form.

### 6.4 Bước 2 — Upload thẳng lên R2

```js
await fetch(presignData.url, {
  method: "PUT",
  headers: presignData.headers,   // { "Content-Type": "image/png" }
  body: file,
});
```

> ⚠️ **Không retry**: presigned PUT URL chỉ dùng được 1 lần trong TTL (10 phút).
> Nếu lỗi mạng → xin URL mới (bước 1) rồi PUT lại.
>
> ⚠️ **Giữ nguyên `Content-Type`** khớp với lúc presign. Bỏ qua → R2 từ chối
> (`403 SignatureDoesNotMatch`).

### 6.5 Bước 3 — Xác nhận & nhận URL đọc

```http
POST /api/v1/uploads/confirm HTTP/1.1
Content-Type: application/json

{
  "kind": "doctor_avatar",
  "object_key": "doctor/avatar/4f1c2a....png",
  "content_type": "image/png"
}
```

**Response**:

```jsonc
{
  "status": "success",
  "data": {
    "kind": "doctor_avatar",
    "object_key": "doctor/avatar/4f1c2a....png",
    "url": "https://...presigned-get...",
    "expires_in": 3600
  }
}
```

`url` chỉ sống `expires_in` giây (1 giờ). Khi hết hạn, `GET /doctors/{id}`
sẽ trả BE-derive URL mới từ `object_key`.

### 6.6 Bước 4 — PATCH `avatar_object_key` lên bác sĩ

**Edit mode** (bác sĩ đã tồn tại):

```http
PATCH /api/v1/doctors/1 HTTP/1.1
Content-Type: application/json

{
  "avatar_object_key": "doctor/avatar/4f1c2a....png"
}
```

**Create mode** (gửi kèm POST):

```http
POST /api/v1/doctors HTTP/1.1
Content-Type: application/json

{
  "full_name": "Nguyễn Văn A",
  "department_id": 1,
  "avatar_object_key": "doctor/avatar/4f1c2a....png"
  // ... các field khác
}
```

### 6.7 BE tự xóa object cũ trên R2

Cơ chế dọn dẹp giống `department_avatar`:

| Trước PATCH (`object_key`) | Body gửi | Object trên R2 |
|---|---|---|
| `null` | `doctor/avatar/xyz.png` | tạo mới, không xóa gì |
| `doctor/avatar/abc.png` | `doctor/avatar/xyz.png` | xóa `abc.png`, tạo `xyz.png` |
| `doctor/avatar/abc.png` | `doctor/avatar/abc.png` (giữ nguyên) | idempotent — giữ nguyên |
| `doctor/avatar/abc.png` | `null` | xóa `abc.png`, set field về `null` |
| `null` | `null` | giữ nguyên |

Lỗi R2 chỉ log warning, không rollback DB. File orphan có thể dọn sau qua
lifecycle policy của bucket.

### 6.8 Ràng buộc kích thước & mime

| Ràng buộc | FE validate | BE validate |
|---|:---:|:---:|
| File ≤ 15 MB | ✅ | ✅ |
| MIME ∈ `{image/jpeg, image/png, image/webp}` | ✅ | ✅ |
| Avatar nên ≤ 5 MB | ✅ (khuyến nghị UX) | — |

> **Lưu ý**: avatar KHÔNG chấp nhận `application/pdf` (chỉ dành cho
> `doctor_document`). FE nên check MIME ở client trước khi presign.

---

## 7. Mapping field form ↔ payload

### 7.1 Bảng mapping UI ↔ API

| UI (form) | Key state | Key payload | Ghi chú |
|---|---|---|---|
| `Họ tên *` | `full_name` | `full_name` | trim trước khi gửi |
| `Khoa *` (dropdown) | `department_id` (number) | `department_id` | map từ `GET /departments` |
| `Chức danh` | `title` | `title` | trim |
| `Số điện thoại` | `phone` | `phone` | trim, validate pattern nếu cần |
| `Email` | `email` | `email` | trim + validate định dạng |
| `Ngày sinh` (date picker) | `date_of_birth` | `date_of_birth` | format `YYYY-MM-DD` |
| `Giới tính` (select) | `gender` | `gender` | map enum → nhãn VN |
| `Địa chỉ` | `address` | `address` | trim |
| `Số GPLHN` | `license_number` | `license_number` | trim |
| `Ngày cấp GPL` (date picker) | `license_issue_date` | `license_issue_date` | format `YYYY-MM-DD` |
| `Ngày hết hạn GPL` (date picker) | `license_expiry_date` | `license_expiry_date` | phải sau `license_issue_date` |
| `Chuyên khoa chính` | `specialization` | `specialization` | trim |
| `Chuyên khoa phụ` (tag input) | `sub_specializations` | `sub_specializations` | mảng chuỗi |
| `Trình độ học vấn` (tag input) | `education` | `education` | mảng chuỗi |
| `Số năm kinh nghiệm` (number) | `experience_years` | `experience_years` | số nguyên ≥ 0 |
| `Nơi đào tạo` (tag input) | `training_institutions` | `training_institutions` | mảng chuỗi |
| `Loại hợp đồng` (select) | `employment_type` | `employment_type` | map enum |
| `Ngày vào làm` (date picker) | `hire_date` | `hire_date` | format `YYYY-MM-DD` |
| `Ngày kết thúc HĐ` (date picker) | `contract_end_date` | `contract_end_date` | phải sau `hire_date` |
| `Đang nhận bệnh nhân mới` (switch) | `is_accepting_new_patients` | `is_accepting_new_patients` | bool |
| `Trạng thái hoạt động` (switch) | `is_active` | `is_active` (PATCH only) | Edit mode; Create không gửi |
| `Ảnh đại diện` (uploader) | `avatar_object_key` | `avatar_object_key` | upload R2 trước |

### 7.2 Enum mapping cho select

```ts
const GENDER_LABEL: Record<string, string> = {
  male: 'Nam',
  female: 'Nữ',
  other: 'Khác',
}

const EMPLOYMENT_LABEL: Record<string, string> = {
  full_time: 'Toàn thời gian',
  part_time: 'Bán thời gian',
  contract: 'Hợp đồng',
}
```

---

## 8. Hành vi form theo mode

### 8.1 Create mode (`/staff/doctors/new`)

1. State form khởi tạo rỗng:
   - `full_name` = `''`, `department_id` = `null`
   - Tất cả trường khác = `null` / `[]` / `false`
   - `is_active` KHÔNG hiển thị (BE mặc định `true`)
2. Dropdown `Khoa` load từ `GET /departments?size=100`.
3. User upload avatar → lưu `avatar_object_key` vào state.
4. Nút "Lưu bác sĩ" → validate FE → `POST /doctors`.
5. Sau 201 → toast "Đã tạo bác sĩ <full_name>." → `navigate('/staff/doctors')`.

### 8.2 Edit mode (`/staff/doctors/:id/edit`)

1. Mount → `GET /doctors/:id` → pre-fill toàn bộ state form.
2. Trong khi edit:
   - **Toggle `is_active`** — FE quyết định bật/tắt tự do (không còn ràng buộc với trưởng khoa sau refactor 1a2b3c4d5e6f).
   - **Đổi `department_id`** — cho phép chuyển khoa trực thuộc.
   - **Đổi avatar** — auto-save (PATCH riêng `avatar_object_key` ngay sau khi upload xong) — **không** nằm trong payload PATCH form chính. Pattern tương tự `department_avatar`.
3. User bấm "Lưu thay đổi" → so sánh state hiện tại với `original` → PATCH chỉ các field khác.
4. Sau 200 → toast "Đã cập nhật bác sĩ." → `navigate('/staff/doctors/:id')`.

### 8.3 Quy tắc build payload PATCH (chỉ gửi field khác giá trị gốc)

```ts
function buildPatchPayload(form, original) {
  const payload: Record<string, unknown> = {}

  // String fields: gửi nếu khác (sau trim)
  if (form.full_name.trim() !== original.full_name.trim())
    payload.full_name = form.full_name.trim()

  // Date fields: gửi nếu khác; null nếu rỗng; chuyển undefined thành skip
  if (form.date_of_birth !== (original.date_of_birth ?? null))
    payload.date_of_birth = form.date_of_birth

  // Number fields: ép kiểu
  if (form.experience_years !== (original.experience_years ?? null))
    payload.experience_years = form.experience_years

  // Arrays: so sánh từng phần tử
  if (!arrayEqual(form.sub_specializations, original.sub_specializations ?? []))
    payload.sub_specializations = form.sub_specializations

  // Booleans: chỉ gửi nếu khác
  if (form.is_active !== original.is_active)
    payload.is_active = form.is_active

  return payload
}
```

> **KHÔNG gửi `avatar_object_key` ở payload PATCH này** — avatar đã được PATCH
> riêng qua `onSaveAvatar` callback ngay sau upload. Đây là pattern "auto-save
> avatar + manual-save form" giống `department_avatar`.

---

## 9. Ví dụ payload hoàn chỉnh

### 9.1 POST tạo mới (đầy đủ các field)

```jsonc
POST /api/v1/doctors
{
  "full_name": "Nguyễn Văn A",
  "department_id": 1,
  "title": "Thạc sĩ",

  "phone": "0912345678",
  "email": "nvana@hospital.com",
  "avatar_object_key": "doctor/avatar/4f1c2a-...-8a9b.png",
  "date_of_birth": "1980-05-15",
  "gender": "male",
  "address": "123 Nguyễn Trãi, Q1, TP.HCM",

  "license_number": "GD-00012345",
  "license_issue_date": "2010-01-15",
  "license_expiry_date": "2030-01-15",
  "specialization": "Tim mạch",
  "sub_specializations": ["Nội soi tim", "Siêu âm tim"],
  "education": ["Đại học Y Hà Nội", "Thạc sĩ Tim mạch"],
  "experience_years": 15,
  "training_institutions": ["BV Bạch Mai", "BV Trung ương"],

  "employment_type": "full_time",
  "hire_date": "2010-03-01",
  "contract_end_date": "2030-03-01",
  "is_accepting_new_patients": true
}
```

### 9.2 PATCH chỉ một vài field

```jsonc
PATCH /api/v1/doctors/1
{
  "title": "Phó Giáo sư",
  "license_expiry_date": "2035-01-15",
  "is_accepting_new_patients": false
}
```

### 9.3 PATCH xóa một field nullable

```jsonc
PATCH /api/v1/doctors/1
{
  "phone": null,           // xóa SĐT
  "sub_specializations": [] // xóa hết CK phụ
}
```

---

## 10. Checklist triển khai FE

### 10.1 Form chung

- [ ] Route `/staff/doctors/new` → POST.
- [ ] Route `/staff/doctors/:id/edit` → GET (pre-fill) + PATCH.
- [ ] Gate route theo `hasPermission('department:manage')`.
- [ ] Permission thiếu → hiển thị "Bạn không có quyền truy cập trang này." (KHÔNG redirect login — đã đăng nhập rồi).
- [ ] Permission `null` → redirect `/login`.
- [ ] Intercept 401 → interceptor đã xử lý (xoá token + redirect login).
- [ ] Intercept 403 → interceptor đã toast — không cần làm gì thêm.

### 10.2 Field validation (FE validate sớm)

- [ ] `full_name` không rỗng, ≤ 255 ký tự.
- [ ] `department_id` là số dương đã chọn.
- [ ] `date_of_birth` (nếu có) — `< today`.
- [ ] `license_expiry_date` (nếu có) — sau `license_issue_date`.
- [ ] `contract_end_date` (nếu có) — sau `hire_date`.
- [ ] `gender` ∈ {male, female, other} hoặc rỗng.
- [ ] `employment_type` ∈ {full_time, part_time, contract} hoặc rỗng.
- [ ] `experience_years` là số nguyên ≥ 0.
- [ ] `email` đúng định dạng nếu gửi.
- [ ] Ngày tháng format `YYYY-MM-DD` trước khi gửi.

### 10.3 Create flow

- [ ] Load `GET /departments?size=100` cho dropdown.
- [ ] Disable "Lưu" khi form chưa hợp lệ (FE validate).
- [ ] Click "Lưu" → POST → loading spinner.
- [ ] 201 → toast "Đã tạo bác sĩ <tên>." → `navigate('/staff/doctors')`.
- [ ] 422 → map `data[error_field]` → set field error, focus vào field đầu tiên lỗi.

### 10.4 Edit flow

- [ ] Mount → GET doctor → pre-fill form.
- [ ] Nút "Lưu thay đổi" disable khi không có thay đổi.
- [ ] Click "Lưu" → PATCH → loading spinner.
- [ ] 200 → toast "Đã cập nhật bác sĩ." → `navigate('/staff/doctors/:id')`.
- [ ] 404 → hiện "Không tìm thấy bác sĩ." + nút quay lại.
- [ ] 422 → map errors.

### 10.5 Avatar upload (auto-save pattern)

- [ ] Component `AvatarUploader` cho bác sĩ (tương tự `department_avatar`).
- [ ] Khi upload xong → `PATCH /doctors/:id` với `avatar_object_key` ngay (không chờ Lưu form).
- [ ] Khi clear avatar → `PATCH /doctors/:id` với `avatar_object_key: null`.
- [ ] Hiển thị spinner / disable control trong quá trình upload.
- [ ] Validate MIME `{jpeg, png, webp}` + size ≤ 5 MB ở client trước khi presign.
- [ ] Presigned PUT URL chỉ dùng 1 lần; nếu lỗi → retry từ đầu (presign mới).
- [ ] Sau khi PATCH avatar thành công → parent refetch hoặc cập nhật state `avatar_url` để preview dùng TTL mới.

---

## 11. Lỗi thường gặp & gợi ý xử lý

| Bước | HTTP / Mã | Gợi ý xử lý FE |
|---|---|---|
| Submit form | 401 `auth_unauthorized` | Interceptor đã xử lý (xoá token + về login). |
| Submit form | 403 `permission_denied` | Hiện toast "Bạn không có quyền thực hiện hành động này." |
| Submit form | 404 `department_not_found` | Highlight field `department_id`: "Khoa không tồn tại hoặc đã bị xoá." |
| Submit form | 400 `doctor_duplicate_license` | Highlight `license_number`: "Số GPL này đã thuộc về bác sĩ khác." |
| Submit form | 422 `VAL_001` | Map `data` theo field → set field error. |
| Submit form | 422 body rỗng | Hiện "Không có thay đổi nào để lưu." (FE nên disable nút Lưu). |
| Presign | 400 `upload_kind_unsupported` | Toast "Loại upload không được hỗ trợ." → kiểm tra `kind: "doctor_avatar"`. |
| Presign | 400 `upload_content_type_unsupported` | Toast "Định dạng ảnh không được phép (chỉ JPG, PNG, WEBP)." |
| Presign | 400 `upload_too_large` | Toast "Tệp vượt quá 15 MB." |
| PUT lên R2 | 403 `SignatureDoesNotMatch` | Bỏ sót `Content-Type` header — lấy lại đúng từ `presign.headers`. |
| PUT lên R2 | 403 `RequestExpired` | URL đã hết hạn (sau 10 phút) → presign lại. |
| PUT lên R2 | 0 / NetworkError | Toast "Mất kết nối tới dịch vụ lưu trữ — thử lại." |
| Confirm | 404 `upload_object_not_found` | Upload chưa tới R2 — toast "Upload chưa hoàn tất — thử lại." |
| Confirm | 503 | Toast "Dịch vụ upload chưa sẵn sàng, thử lại sau." |
| PATCH avatar | 404 `doctor_not_found` | Hiện "Bác sĩ không tồn tại hoặc đã bị xoá." |

---

## 12. Ví dụ hook/service layer (drop-in)

```ts
// services/doctor.service.ts
import { client } from './client'
import type {
  Doctor,
  DoctorCreatePayload,
  DoctorUpdatePayload,
  ApiResponse,
  ApiMeta,
} from '@/types/api'

export const doctorService = {
  /** GET /api/v1/departments?size=100 — lấy danh sách khoa cho dropdown Khoa. */
  async listDepartmentsForSelect(): Promise<Department[]> {
    const res = await client.get<ApiResponse<Department[]>>(
      '/api/v1/departments?size=100',
    )
    return res.data.data ?? []
  },

  /** GET /api/v1/doctors/{id} — lấy chi tiết bác sĩ để pre-fill form edit. */
  async getDoctor(id: number): Promise<Doctor> {
    const res = await client.get<ApiResponse<Doctor>>(
      `/api/v1/doctors/${id}`,
    )
    if (!res.data.data) throw new Error('Không tìm thấy bác sĩ')
    return res.data.data
  },

  /** POST /api/v1/doctors — tạo bác sĩ mới. */
  async createDoctor(payload: DoctorCreatePayload): Promise<Doctor> {
    const res = await client.post<ApiResponse<Doctor>>(
      '/api/v1/doctors',
      payload,
    )
    if (!res.data.data) throw new Error('Tạo bác sĩ thất bại')
    return res.data.data
  },

  /** PATCH /api/v1/doctors/{id} — cập nhật từng phần. */
  async updateDoctor(
    id: number,
    changes: DoctorUpdatePayload,
  ): Promise<Doctor> {
    const res = await client.patch<ApiResponse<Doctor>>(
      `/api/v1/doctors/${id}`,
      changes,
    )
    if (!res.data.data) throw new Error('Cập nhật bác sĩ thất bại')
    return res.data.data
  },

  /** PATCH avatar riêng (auto-save). */
  async updateDoctorAvatar(
    id: number,
    objectKey: string | null,
  ): Promise<Doctor> {
    return this.updateDoctor(id, { avatar_object_key: objectKey })
  },
}
```

```ts
// Ví dụ buildPatchPayload cho edit mode
function buildDoctorPatchPayload(form, original) {
  const p = {}

  if (form.full_name.trim() !== original.full_name.trim())
    p.full_name = form.full_name.trim()

  if (form.department_id !== original.department_id)
    p.department_id = form.department_id

  if ((form.title ?? '') !== (original.title ?? ''))
    p.title = form.title ?? null

  // ... các field khác — so sánh và gửi khác giá trị gốc

  if (form.is_active !== original.is_active)
    p.is_active = form.is_active

  return p
}
```

---

## 13. Tóm tắt endpoint

| Method | Path | Permission | Mục đích trong form |
|---|---|---|---|
| `POST` | `/api/v1/doctors` | `department:manage` | Tạo bác sĩ mới |
| `GET` | `/api/v1/doctors/{id}` | `department:manage` | Pre-fill form edit |
| `PATCH` | `/api/v1/doctors/{id}` | `department:manage` | Cập nhật form edit (gồm cả đổi/xoá avatar) |
| `GET` | `/api/v1/departments?size=100` | `department:manage` | Populate dropdown Khoa |
| `POST` | `/api/v1/uploads/presign` | đăng nhập | Xin URL upload avatar (`kind: "doctor_avatar"`) |
| `POST` | `/api/v1/uploads/confirm` | đăng nhập | Xác nhận upload & nhận URL đọc |

---

## 14. Lịch sử thay đổi

| Phiên bản | Thay đổi |
|---|---|
| **1.0.0** | Bản đầu: tài liệu chuyên biệt cho 2 màn form Tạo mới & Chỉnh sửa bác sĩ. Bao gồm 2 endpoint `POST /doctors`, `PATCH /doctors/{id}` + lookup `GET /departments` + upload avatar `kind: "doctor_avatar"`. Tham chiếu `FE_DOCTOR.md` cho phần list/detail/stats/rating/documents. |
| **1.1.0** | Cập nhật theo các refactor BE gần đây:<br>• Bỏ mọi tham chiếu tới tính năng `rating` (đã xóa ở migration `1c2d3e4f5a6b`) và `include_ratings` query param không còn tồn tại.<br>• Bổ sung validate trùng `email` ở POST/PATCH — case-insensitive — trả `422 errors.doctor_duplicate_email`.<br>• Bảng mã lỗi §3.6 & §4.6 viết lại với `code` chính xác từ i18n (`errors.department_not_found`, `errors.doctor_duplicate_license`, `errors.doctor_duplicate_email`, `errors.invalid_date_format`, `VAL_001 invalid_choice`/`invalid_list`/`invalid_item`).<br>• Bổ sung key mới trong i18n: `messages.doctor_created`, `messages.doctor_updated`, `messages.doctor_deleted`.<br>• Bump version doc lên 1.1.0. |
