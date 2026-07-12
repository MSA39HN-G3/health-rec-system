# Hướng dẫn FE: Quản lý Chuyên khoa (Department)

> **Phiên bản: 1.6.0** — Bỏ hoàn toàn khái niệm `head_doctor` trên Department và
> role `doctor` trên User (refactor 1a2b3c4d5e6f):
> - Cột `head_doctor_id` (FK tới `users`) đã được drop khỏi bảng `departments`.
> - Role `doctor` đã được xóa khỏi bảng `roles` + `role_permissions`/`user_roles`.
> - `staff` không còn "kèm trưởng khoa" — staff giờ quản lý tất cả bác sĩ (mọi khoa);
>   FE tự chọn khoa qua filter `department_id` nếu muốn giới hạn.
> - `is_active` đã thành **flag do FE set trực tiếp** (không còn phụ thuộc head_doctor).
>
> Phiên bản 1.5.1 (`?format=csv`), 1.4.x (avatar) giữ nguyên.

Module quản lý chuyên khoa (khoa). Bước đầu cung cấp 2 chức năng: **tạo khoa mới** và
**xem danh sách khoa**. Thông tin khoa được thiết kế kèm các trường phục vụ **AI/LLM gợi ý
định tuyến bệnh nhân** vào đúng khoa dựa trên triệu chứng.

> Tài liệu liên quan: [`FE_RBAC.md`](./FE_RBAC.md) (phân quyền),
> [`FE_AUTH_TOKEN.md`](./FE_AUTH_TOKEN.md) (token, gọi API có bảo vệ),
> [`FE_UPLOADS.md`](./FE_UPLOADS.md) (upload ảnh qua Cloudflare R2).

---

## 1. Quyền truy cập

Toàn bộ endpoint khoa yêu cầu `Authorization: Bearer <token>` và **permission `department:manage`**
(403 nếu thiếu). Permission này mặc định có ở role **`admin`** và **`staff`**.

> FE nên gate menu/nút "Quản lý khoa" theo `hasPermission("department:manage")`.
> Xem helper trong [`FE_RBAC.md`](./FE_RBAC.md) mục 3.

---

## 2. Mô hình dữ liệu khoa

Một khoa (`department`) gồm các trường:

| Trường | Kiểu | Bắt buộc | Ý nghĩa |
|---|---|:---:|---|
| `id` | int | — | Khóa chính (do BE sinh). |
| `code` | string (≤32) | — | **Mã khoa duy nhất do hệ thống tự sinh** dạng `CK-NNN` (vd `CK-001`). FE **không gửi** trường này. |
| `name` | string (≤255) | ✅ | Tên hiển thị (vd `Tim mạch`). |
| `location` | string (≤255) | — | Vị trí của khoa (vd `Tầng 3, Tòa nhà A`). |
| `avatar_object_key` | string (≤512) | — | **Khóa object trong R2** (sinh bởi `/api/v1/uploads/presign`). FE nên lưu/đọc field này để gắn với ảnh upload qua R2. Xem [`FE_UPLOADS.md`](./FE_UPLOADS.md). |
| `avatar_url` | string (≤512) \| null | — | **URL để hiển thị ảnh** — do BE tự derive từ `avatar_object_key` (presigned GET, mặc định TTL 1 giờ) hoặc đặt tay cho bucket public. FE không cần gửi field này; chỉ dùng để render thẻ `<img>`. |
| `description` | string (≤5000) | — | Mô tả giàu thông tin về khoa. *(Dùng cho AI semantic match.)* |
| `keywords` | string[] | — | Danh sách **triệu chứng** dạng tag (vd `chest_pain`, `hypertension`). Tối đa 50 phần tử, mỗi phần tử ≤64 ký tự. |
| `conditions` | string[] | — | Danh sách **bệnh lý điển hình** của khoa (vd `arrhythmia`). Tối đa 50 phần tử, mỗi phần tử ≤128 ký tự. |
| `techniques` | string[] | — | **Danh mục kĩ thuật chuyên môn** của khoa (vd `Nội soi tiêu hóa`, `Siêu âm tim`). Tối đa 100 phần tử, mỗi phần tử ≤255 ký tự. |
| `ai_metadata` | object | — | Metadata mở rộng tự do (vd `{ "icd10": ["I20-I25"], "age_group": "adult" }`). |
| `is_active` | bool | — | Khoa còn hoạt động hay không. **FE set trực tiếp** qua request body khi tạo (`POST /departments`) hoặc cập nhật (`PATCH /departments/{id}`). Mặc định `false` khi tạo. Không còn ràng buộc với "trưởng khoa". |
| `created_at` / `updated_at` | string (ISO) | — | Thời điểm tạo/cập nhật. |

### Vì sao có `keywords` / `conditions` / `description`?

Những trường này giúp **AI gợi ý đưa bệnh nhân vào khoa nào**:
- `keywords` + `conditions` là dữ liệu **có cấu trúc** → match nhanh theo triệu chứng/bệnh lý.
- `description` là văn bản **giàu ngữ nghĩa** → dùng cho so khớp ngữ nghĩa (semantic search) về sau.

> **Gợi ý nhập liệu cho FE:** nên cho nhập `keywords` / `conditions` dưới dạng **tag input**
> (mỗi tag là một chuỗi ngắn, không dấu cách thừa). `ai_metadata` là tùy chọn nâng cao,
> có thể ẩn sau mục "Cấu hình nâng cao".

---

## 3. Tạo khoa mới — `POST /api/v1/departments`

Cần permission `department:manage`.

### Request body

```jsonc
{
  "name": "Tim mạch",                     // bắt buộc
  "location": "Tầng 3, Tòa nhà A",        // tùy chọn — vị trí của khoa
  "description": "Khoa chẩn đoán và điều trị bệnh lý tim mạch.",
  "keywords": ["chest_pain", "palpitations", "hypertension"],
  "conditions": ["myocardial_infarction", "arrhythmia"],
  "ai_metadata": { "icd10": ["I20-I25"], "age_group": "adult" },
  "is_active": true                       // tùy chọn — mặc định false. Set trực tiếp không cần head_doctor.
}
```

> **Tối thiểu chỉ cần `name`.** Các trường `location`, `description`, `keywords`, `conditions`,
> `ai_metadata`, `is_active` đều **tùy chọn** (`is_active` mặc định `false` khi bỏ qua).
>
> ⚠️ **Không gửi `code`** (hệ thống tự sinh `CK-NNN`).
>
> 🆕 **`is_active` (mặc định `false`):** FE set trực tiếp qua body. **Không còn ràng buộc**
> với head_doctor (đã bỏ ở refactor 1a2b3c4d5e6f) — bật/tắt khoa thoải mái.

### Response — `201 Created`

```jsonc
{
  "status": "success",
  "code": "201",
  "message": "Tạo khoa thành công.",
  "data": {
    "id": 1,
    "code": "CK-001",
    "name": "Tim mạch",
    "location": "Tầng 3, Tòa nhà A",
    "description": "Khoa chẩn đoán và điều trị bệnh lý tim mạch.",
    "keywords": ["chest_pain", "palpitations", "hypertension"],
    "conditions": ["myocardial_infarction", "arrhythmia"],
    "ai_metadata": { "icd10": ["I20-I25"], "age_group": "adult" },
    "head_doctor_id": 2,
    "head_doctor": { "id": 2, "full_name": "BS. Nguyen Van A" },
    "is_active": true,
    "created_at": "2026-06-27T10:00:00+00:00",
    "updated_at": "2026-06-27T10:00:00+00:00"
  },
  "meta": null
}
```

### Không còn khái niệm `head_doctor` (refactor 1a2b3c4d5e6f)

Bắt đầu từ phiên bản 1.6.0:
- Cột `head_doctor_id` (FK tới `users`) đã được drop khỏi bảng `departments`.
- Role `doctor` đã bị xóa khỏi `roles` + `role_permissions` + `user_roles`.
- `is_active` không còn phụ thuộc `head_doctor_id` — FE set trực tiếp qua body.
- Staff quản lý **tất cả** bác sĩ (mọi khoa). Để giới hạn theo khoa,
  FE tự truyền filter `department_id` trong query (xem chi tiết tại
  `FE_DOCTOR.md`).

### Các lỗi có thể gặp

| HTTP | Khi nào | `message` |
|---|---|---|
| **409** | Mã khoa do hệ thống sinh bị trùng (hiếm gặp) | "Mã khoa này đã tồn tại." |
| **422** | Thiếu/sai field (vd thiếu `name`, `keywords` không phải mảng chuỗi) | "Dữ liệu không hợp lệ." (kèm `data` chi tiết theo field) |
| **403** | Thiếu permission `department:manage` | "Bạn không có quyền thực hiện hành động này." |

> Mã khoa do hệ thống tự sinh nên FE **không gặp lỗi 409 trùng mã** trong luồng thường.

Ví dụ body lỗi `422` (chi tiết theo từng field, reason code dạng máy đọc):

```jsonc
{
  "status": "error", "code": "422", "message": "Dữ liệu không hợp lệ.",
  "data": { "name": "required", "keywords": "invalid_item" },
  "meta": null
}
```

---

## 4. Danh sách khoa — `GET /api/v1/departments`

Cần permission `department:manage`. Hỗ trợ phân trang.

| Query | Mặc định | Ràng buộc |
|---|---|---|
| `page` | 1 | ≥ 1 |
| `size` | 20 | 1–100 |

```jsonc
// GET /api/v1/departments?page=1&size=20
{
  "status": "success", "code": "200", "message": null,
  "data": [
    {
      "id": 1, "code": "CK-001", "name": "Tim mạch",
      "location": "Tầng 3, Tòa nhà A",
      "keywords": ["chest_pain", "hypertension"],
      "conditions": ["arrhythmia"],
      "head_doctor": { "id": 2, "full_name": "BS. Nguyen Van A" },
      "is_active": true,
      "created_at": "2026-06-27T10:00:00+00:00",
      "updated_at": "2026-06-27T10:00:00+00:00"
    }
  ],
  "meta": { "page": 1, "size": 20, "totalPage": 1 }
}
```

> `data` là **mảng**; thông tin phân trang nằm ở `meta` (giống các API danh sách khác).

---

## 5. Thống kê khoa — `GET /api/v1/departments/stats`

Cần permission `department:manage`. Trả về số lượng khoa theo trạng thái — dùng cho thẻ
thống kê (dashboard).

```jsonc
// GET /api/v1/departments/stats
{
  "status": "success", "code": "200", "message": null,
  "data": {
    "total": 12,      // Tổng số khoa
    "active": 9,      // Số khoa đang hoạt động (is_active = true)
    "inactive": 3     // Số khoa tạm dừng (is_active = false)
  },
  "meta": null
}
```

> Luôn có `total === active + inactive` (đếm theo cờ `is_active` lưu trong DB —
> hoàn toàn do FE set trực tiếp qua body ở POST/PATCH).

---

## 6. Cập nhật khoa — `PATCH /api/v1/departments/{id}`

Cần permission `department:manage`. **Cập nhật từng phần (partial update):** chỉ những
field **có mặt trong body** mới bị thay đổi; field nào không gửi sẽ **giữ nguyên**.

### Request body — tất cả field đều tùy chọn

```jsonc
// PATCH /api/v1/departments/1  — ví dụ cập nhật ảnh + danh mục kĩ thuật chuyên môn
{
  "avatar_url": "https://cdn.example.com/dept/cardio.png",
  "techniques": ["Nội soi tiêu hóa", "Siêu âm tim", "Điện tâm đồ gắng sức"],
  "name": "Khoa Tim mạch",
  "location": "Tầng 3, Tòa nhà A",
  "description": "...",
  "keywords": ["chest_pain"],
  "conditions": ["arrhythmia"],
  "ai_metadata": { "age_group": "adult" },
  "is_active": true
}
```

| Trường | Quy tắc khi cập nhật |
|---|---|
| `name` | Nếu gửi: bắt buộc khác rỗng (≤255). **Không cho gửi `null`.** |
| `location` / `avatar_object_key` / `avatar_url` / `description` | Gửi chuỗi để đặt; gửi `null` để **xóa** giá trị. |
| `avatar_object_key` | Khóa object trong R2 (sinh từ `/api/v1/uploads/presign`). Khi set sẽ tự xoá cache URL; khi set `null` sẽ xoá ảnh. **BE cũng tự xóa object cũ trên R2** sau khi commit DB — FE không cần gọi API delete. Xem [`FE_DEPARTMENT_AVATAR_UPLOAD.md`](./FE_DEPARTMENT_AVATAR_UPLOAD.md) mục "Dọn dẹp avatar cũ". |
| `avatar_url` | URL ảnh đại diện (≤512). Tùy chọn, dùng khi muốn lưu URL public (custom domain). Bình thường FE chỉ cần gửi `avatar_object_key`. |
| `techniques` | Mảng chuỗi (≤100 phần tử, mỗi phần tử ≤255). Gửi mảng để **thay thế toàn bộ**; gửi `[]` để xóa hết. |
| `keywords` / `conditions` | Mảng chuỗi — thay thế toàn bộ danh sách hiện có. |
| `ai_metadata` | Object — thay thế toàn bộ. |
| `is_active` | Bật/tắt trực tiếp qua body (`true`/`false`/`null`). Mặc định giữ nguyên nếu không gửi. |

> ⚠️ **Không gửi `code`** (cố định, hệ thống cấp).
> Cũng không có `head_doctor_id` (đã bỏ ở refactor 1a2b3c4d5e6f).

### Response — `200 OK`

Trả về object khoa sau cập nhật (cùng cấu trúc như mục [3](#3-tạo-khoa-mới--post-apiv1departments)),
`message`: "Cập nhật khoa thành công."

### Các lỗi có thể gặp

| HTTP | Khi nào | `message` |
|---|---|---|
| **404** | `{id}` không tồn tại | "Không tìm thấy khoa." |
| **422** | Body rỗng (không có field nào) hoặc sai kiểu field | "Dữ liệu không hợp lệ." |
| **403** | Thiếu permission `department:manage` | "Bạn không có quyền thực hiện hành động này." |

---

---

## 8. Lưu ý quan trọng

- **`keywords` / `conditions` là mảng chuỗi**, không phải chuỗi phân tách dấu phẩy. Gửi sai kiểu → `422`.
- **Mã khoa (`code`) do hệ thống tự sinh** dạng `CK-NNN`, duy nhất và ổn định — FE chỉ hiển thị, không nhập/sửa.
- **`is_active` được FE set trực tiếp** qua body của `POST` hoặc `PATCH`. Mặc định `false` khi tạo.
  Không còn bất kỳ ràng buộc nào với "trưởng khoa" — bật/tắt khoa thoải mái.
- **Toggle enable/disable trên UI có thể là switch thật** (gửi `PATCH` với `is_active`) — đã không còn
  ràng buộc với head_doctor nên FE có thể chủ động bật/tắt.
- **Trường AI là nền tảng cho tính năng gợi ý sau này** — nên khuyến khích admin nhập đầy đủ
  `keywords`, `conditions`, `description` để chất lượng gợi ý định tuyến tốt hơn.

---

## 9. Checklist tích hợp

- [ ] Gate menu/route "Quản lý khoa" theo permission `department:manage`.
- [ ] Form tạo khoa: chỉ `name` bắt buộc; **không có ô `code`**; `keywords`/`conditions` dùng tag-input (mảng chuỗi); toggle `is_active` (mặc định tắt) — không có ràng buộc với trưởng khoa nữa.
- [ ] Toggle bật/tắt khoa trên UI gửi `PATCH` với `is_active: true|false`.
- [ ] Xử lý lỗi `422` (sai dữ liệu), `403` (thiếu permission).
- [ ] Màn hình danh sách khoa: phân trang qua `meta`, hiển thị `code` (`CK-NNN`), `location` và `is_active`.

---

## 10. Tóm tắt endpoint

| Method | Path | Permission | Mô tả |
|---|---|---|---|
| `POST` | `/api/v1/departments` | `department:manage` | Tạo khoa mới |
| `GET` | `/api/v1/departments` | `department:manage` | Danh sách khoa (phân trang) |
| `GET` | `/api/v1/departments/stats` | `department:manage` | Thống kê số lượng khoa (tổng/hoạt động/tạm dừng) |
| `GET` | `/api/v1/departments/{id}` | `department:manage` | **Chi tiết 1 khoa**. Chi tiết ở [`FE_DEPARTMENT_DETAIL.md`](./FE_DEPARTMENT_DETAIL.md). |
| `GET` | `/api/v1/departments/{id}/doctors` | `department:manage` | **Danh sách bác sĩ trực thuộc + stats** (compound endpoint: `stats` + `doctors[]` trong 1 response). `?format=csv` → download file CSV. Chi tiết ở [`FE_DEPARTMENT_DETAIL.md`](./FE_DEPARTMENT_DETAIL.md). |
| `PATCH` | `/api/v1/departments/{id}` | `department:manage` | Cập nhật từng phần (gồm ảnh đại diện, kĩ thuật chuyên môn) |

---

## 11. Lịch sử thay đổi

| Phiên bản | Thay đổi |
|---|---|
| **1.5.1** | Thêm `?format=csv` cho `GET /api/v1/departments/{id}/doctors` để download danh sách bác sĩ của khoa ra file CSV (BOM UTF-8, RFC 4180). Chi tiết ở [`FE_DEPARTMENT_DETAIL.md`](./FE_DEPARTMENT_DETAIL.md) mục 5. |
| **1.5.0** | Bổ sung 2 endpoint phục vụ màn "Chi tiết chuyên khoa": `GET /api/v1/departments/{id}` và `GET /api/v1/departments/{id}/doctors`. Chi tiết ở [`FE_DEPARTMENT_DETAIL.md`](./FE_DEPARTMENT_DETAIL.md). |
| **1.4.3** | Ghi nhận: PATCH `avatar_object_key` tự xóa object cũ trên R2 (FE không cần gọi API delete). Liên kết chi tiết sang `FE_DEPARTMENT_AVATAR_UPLOAD.md`. |
| **1.4.2** | Thêm trường `avatar_object_key` để gắn ảnh upload qua Cloudflare R2 (xem `FE_UPLOADS.md`). BE tự derive `avatar_url` presigned GET trong response. |
| **1.6.0** | Refactor lớn: bỏ `head_doctor_id` (cột FK tới `users.id` đã drop) và role `doctor`. `is_active` do FE set trực tiếp qua body POST/PATCH (không còn ràng buộc với trưởng khoa). Staff quản lý tất cả bác sĩ (mọi khoa). |
| **1.5.0** | Sửa tài liệu: role trưởng khoa giờ là `staff` (đã gộp từ `department_head`). |
