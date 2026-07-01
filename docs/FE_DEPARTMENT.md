# Hướng dẫn FE: Quản lý Chuyên khoa (Department)

> **Phiên bản: 1.3.0** — Thêm API cập nhật khoa (ảnh đại diện, kĩ thuật chuyên môn) và
> API thống kê. Mã khoa do hệ thống tự sinh (`CK-NNN`), trạng thái hoạt động suy ra từ trưởng khoa.
> Xem [Lịch sử thay đổi](#11-lịch-sử-thay-đổi).

Module quản lý chuyên khoa (khoa). Bước đầu cung cấp 2 chức năng: **tạo khoa mới** và
**xem danh sách khoa**. Thông tin khoa được thiết kế kèm các trường phục vụ **AI/LLM gợi ý
định tuyến bệnh nhân** vào đúng khoa dựa trên triệu chứng.

> Tài liệu liên quan: [`FE_RBAC.md`](./FE_RBAC.md) (phân quyền),
> [`FE_AUTH_TOKEN.md`](./FE_AUTH_TOKEN.md) (token, gọi API có bảo vệ).

---

## 1. Quyền truy cập

Toàn bộ endpoint khoa yêu cầu `Authorization: Bearer <token>` và **permission `department:manage`**
(403 nếu thiếu). Permission này mặc định có ở role **`admin`** và **`department_head`**.

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
| `avatar_url` | string (≤512) \| null | — | **Ảnh đại diện** của khoa (URL). Tùy chọn. |
| `description` | string (≤5000) | — | Mô tả giàu thông tin về khoa. *(Dùng cho AI semantic match.)* |
| `keywords` | string[] | — | Danh sách **triệu chứng** dạng tag (vd `chest_pain`, `hypertension`). Tối đa 50 phần tử, mỗi phần tử ≤64 ký tự. |
| `conditions` | string[] | — | Danh sách **bệnh lý điển hình** của khoa (vd `arrhythmia`). Tối đa 50 phần tử, mỗi phần tử ≤128 ký tự. |
| `techniques` | string[] | — | **Danh mục kĩ thuật chuyên môn** của khoa (vd `Nội soi tiêu hóa`, `Siêu âm tim`). Tối đa 100 phần tử, mỗi phần tử ≤255 ký tự. |
| `ai_metadata` | object | — | Metadata mở rộng tự do (vd `{ "icd10": ["I20-I25"], "age_group": "adult" }`). |
| `head_doctor_id` | int \| null | — | ID **trưởng khoa** (tham chiếu user). Có thể bỏ trống, bổ nhiệm sau. |
| `head_doctor` | object \| null | — | Thông tin rút gọn của trưởng khoa: `{ "id", "full_name" }`. |
| `is_active` | bool | — | Khoa còn hoạt động hay không. **Được suy ra: `true` khi và chỉ khi có trưởng khoa** (`head_doctor_id != null`). FE **không gửi** trường này. |
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
  "head_doctor_id": 2                     // tùy chọn — ID của một user là bác sĩ
}
```

> **Tối thiểu chỉ cần `name`.** Các trường `location`, `description`, `keywords`, `conditions`,
> `ai_metadata`, `head_doctor_id` đều **tùy chọn**.
>
> ⚠️ **Không gửi `code`** (hệ thống tự sinh `CK-NNN`) và **không gửi `is_active`**
> (được suy ra từ `head_doctor_id`). Nếu gửi, BE sẽ **bỏ qua**.

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

### Quy tắc về trưởng khoa (`head_doctor_id`)

- **Tùy chọn**: có thể tạo khoa trước, bổ nhiệm trưởng khoa sau.
- User được chọn **phải đang là bác sĩ** (có role `doctor`), nếu không sẽ trả **400**.
- Khi gán thành công, hệ thống **tự động cấp thêm role `department_head`** cho user đó.
  → Sau thao tác này, trưởng khoa sẽ có thêm quyền của `department_head` (xem `FE_RBAC.md`).
- **Quyết định `is_active`:** khoa được tạo với `is_active = true` **khi và chỉ khi** có
  `head_doctor_id`; nếu tạo khoa không có trưởng khoa thì `is_active = false`.

### Các lỗi có thể gặp

| HTTP | Khi nào | `message` |
|---|---|---|
| **404** | `head_doctor_id` không trỏ tới user nào | "Không tìm thấy trưởng khoa được chọn." |
| **400** | User được chọn **không phải bác sĩ** | "Người dùng được chọn phải có role bác sĩ." |
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

> Luôn có `total === active + inactive`. Nhắc lại: một khoa `active` ⇔ có trưởng khoa
> (`head_doctor_id != null`).

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
  "head_doctor_id": 5
}
```

| Trường | Quy tắc khi cập nhật |
|---|---|
| `name` | Nếu gửi: bắt buộc khác rỗng (≤255). **Không cho gửi `null`.** |
| `location` / `avatar_url` / `description` | Gửi chuỗi để đặt; gửi `null` để **xóa** giá trị. |
| `avatar_url` | URL ảnh đại diện (≤512). Tùy chọn. |
| `techniques` | Mảng chuỗi (≤100 phần tử, mỗi phần tử ≤255). Gửi mảng để **thay thế toàn bộ**; gửi `[]` để xóa hết. |
| `keywords` / `conditions` | Mảng chuỗi — thay thế toàn bộ danh sách hiện có. |
| `ai_metadata` | Object — thay thế toàn bộ. |
| `head_doctor_id` | Gửi `id` để đổi trưởng khoa; gửi `null` để **bỏ trưởng khoa**. |

> ⚠️ **Không gửi `code`** (cố định, hệ thống cấp) và **không gửi `is_active`**.
> Khi `head_doctor_id` thay đổi, BE **tự tính lại** `is_active` theo quy tắc iff:
> đặt trưởng khoa → `is_active = true`; bỏ trưởng khoa (`null`) → `is_active = false`.
> Đổi trưởng khoa sang một bác sĩ mới cũng **tự cấp role `department_head`** cho người đó.

### Response — `200 OK`

Trả về object khoa sau cập nhật (cùng cấu trúc như mục [3](#3-tạo-khoa-mới--post-apiv1departments)),
`message`: "Cập nhật khoa thành công."

### Các lỗi có thể gặp

| HTTP | Khi nào | `message` |
|---|---|---|
| **404** | `{id}` không tồn tại | "Không tìm thấy khoa." |
| **404** | `head_doctor_id` không trỏ tới user nào | "Không tìm thấy trưởng khoa được chọn." |
| **400** | User được chọn **không phải bác sĩ** | "Người dùng được chọn phải có role bác sĩ." |
| **422** | Body rỗng (không có field nào) hoặc sai kiểu field | "Dữ liệu không hợp lệ." |
| **403** | Thiếu permission `department:manage` | "Bạn không có quyền thực hiện hành động này." |

---

## 7. Ví dụ tích hợp (JS)

Dùng wrapper `apiFetch` mô tả trong [`FE_RBAC.md`](./FE_RBAC.md) mục 4.

```js
// Lấy danh sách khoa (phân trang)
async function loadDepartments(page = 1) {
  const body = await apiFetch(`/api/v1/departments?page=${page}&size=20`);
  return body ? { departments: body.data, meta: body.meta } : null;
}

// Lấy thống kê số lượng khoa cho dashboard
async function loadDepartmentStats() {
  const body = await apiFetch(`/api/v1/departments/stats`);
  return body?.data ?? null; // { total, active, inactive }
}

// Tạo khoa mới
async function createDepartment(payload) {
  // payload: { name, location?, description?, keywords?, conditions?, ai_metadata?, head_doctor_id? }
  // Lưu ý: KHÔNG gửi code (BE tự sinh CK-NNN) và is_active (BE suy ra từ head_doctor_id).
  const body = await apiFetch(`/api/v1/departments`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return body?.data ?? null; // null nếu lỗi (đã được wrapper xử lý hiển thị)
}

// Cập nhật khoa (partial) — chỉ gửi field cần đổi
async function updateDepartment(id, changes) {
  // changes: bất kỳ tập con nào của
  //   { name?, location?, avatar_url?, description?, keywords?, conditions?,
  //     techniques?, ai_metadata?, head_doctor_id? }
  // Gửi null cho location/avatar_url/description/head_doctor_id để xóa giá trị.
  const body = await apiFetch(`/api/v1/departments/${id}`, {
    method: "PATCH",
    body: JSON.stringify(changes),
  });
  return body?.data ?? null;
}
```

### Gợi ý form tạo khoa (React)

```jsx
// keywords/conditions nên dùng tag-input -> mảng chuỗi
// Không có ô nhập code/is_active: BE tự sinh mã & suy ra trạng thái.
const [form, setForm] = useState({
  name: "", location: "", description: "",
  keywords: [], conditions: [], ai_metadata: {}, head_doctor_id: null,
});

async function onSubmit() {
  // Loại bỏ field rỗng để body gọn (BE coi như không gửi)
  const payload = { name: form.name.trim() };
  if (form.location) payload.location = form.location.trim();
  if (form.description) payload.description = form.description;
  if (form.keywords.length) payload.keywords = form.keywords;
  if (form.conditions.length) payload.conditions = form.conditions;
  if (Object.keys(form.ai_metadata).length) payload.ai_metadata = form.ai_metadata;
  if (form.head_doctor_id) payload.head_doctor_id = form.head_doctor_id;

  const dept = await createDepartment(payload);
  if (dept) showSuccess(`Đã tạo khoa ${dept.name}`);
}
```

### Chọn trưởng khoa

Trưởng khoa phải là **bác sĩ**. FE nên lấy danh sách user có role `doctor` để đổ vào ô chọn:

```js
// Tận dụng API admin (cần user:read) để lấy user, lọc theo role doctor
async function loadDoctors() {
  const body = await apiFetch(`/api/v1/admin/users?page=1&size=100`);
  return body ? body.data.filter((u) => u.roles.includes("doctor")) : [];
}
```

> Nếu tài khoản đang dùng không có `user:read`, có thể bỏ qua bước chọn trưởng khoa khi tạo
> và bổ nhiệm sau (tính năng bổ nhiệm sẽ bổ sung ở phiên bản kế tiếp).

---

## 8. Lưu ý quan trọng

- **`keywords` / `conditions` là mảng chuỗi**, không phải chuỗi phân tách dấu phẩy. Gửi sai kiểu → `422`.
- **Mã khoa (`code`) do hệ thống tự sinh** dạng `CK-NNN`, duy nhất và ổn định — FE chỉ hiển thị, không nhập/sửa.
- **`is_active` không nhập tay:** khoa bật hoạt động ⇔ có trưởng khoa. Muốn khoa active ngay khi tạo → phải gửi `head_doctor_id`.
- **Side effect khi gán trưởng khoa:** user được chọn sẽ **được nâng quyền** lên `department_head`
  ngay lập tức. Nếu user đang đăng nhập, quyền mới chỉ thấy sau khi gọi lại `GET /me` (xem `FE_RBAC.md`).
- **Trường AI là nền tảng cho tính năng gợi ý sau này** — nên khuyến khích admin nhập đầy đủ
  `keywords`, `conditions`, `description` để chất lượng gợi ý định tuyến tốt hơn.

---

## 9. Checklist tích hợp

- [ ] Gate menu/route "Quản lý khoa" theo permission `department:manage`.
- [ ] Form tạo khoa: chỉ `name` bắt buộc; **không có ô `code`/`is_active`**; `keywords`/`conditions` dùng tag-input (mảng chuỗi).
- [ ] Ô chọn trưởng khoa: chỉ liệt kê user có role `doctor`; cho phép để trống (khoa sẽ ở trạng thái `is_active = false`).
- [ ] Xử lý lỗi: `400` (không phải bác sĩ), `404` (không tìm thấy user), `422` (sai dữ liệu).
- [ ] Màn hình danh sách khoa: phân trang qua `meta`, hiển thị `code` (`CK-NNN`), `location`, `head_doctor` và `is_active`.

---

## 10. Tóm tắt endpoint

| Method | Path | Permission | Mô tả |
|---|---|---|---|
| `POST` | `/api/v1/departments` | `department:manage` | Tạo khoa mới |
| `GET` | `/api/v1/departments` | `department:manage` | Danh sách khoa (phân trang) |
| `GET` | `/api/v1/departments/stats` | `department:manage` | Thống kê số lượng khoa (tổng/hoạt động/tạm dừng) |
| `PATCH` | `/api/v1/departments/{id}` | `department:manage` | Cập nhật từng phần (gồm ảnh đại diện, kĩ thuật chuyên môn) |

---

## 11. Lịch sử thay đổi

| Phiên bản | Thay đổi |
|---|---|
| **1.3.0** | Thêm endpoint cập nhật `PATCH /departments/{id}` (partial update). Bổ sung trường `avatar_url` (ảnh đại diện) và `techniques` (danh mục kĩ thuật chuyên môn). Đổi trưởng khoa khi cập nhật sẽ tự tính lại `is_active`. |
| **1.2.0** | Thêm endpoint thống kê `GET /departments/stats` trả về `total` / `active` / `inactive`. |
| **1.1.0** | Mã khoa (`code`) chuyển sang **do hệ thống tự sinh** dạng `CK-NNN` (FE không gửi nữa). Thêm trường `location` (vị trí). `is_active` được **suy ra**: `true` ⇔ có `head_doctor_id`. Bỏ lỗi `409` trùng mã khỏi luồng tạo. |
| **1.0.0** | Bản đầu: tạo khoa (`POST /departments`) với trường phục vụ AI (`keywords`, `conditions`, `description`, `ai_metadata`), chọn trưởng khoa (tùy chọn, phải là bác sĩ, tự cấp role `department_head`); danh sách khoa (`GET /departments`). |
