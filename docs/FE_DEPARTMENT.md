# Hướng dẫn FE: Quản lý Chuyên khoa (Department)

> **Phiên bản: 1.0.0** — Bản đầu: thêm mới & xem danh sách chuyên khoa, chọn trưởng khoa.
> Xem [Lịch sử thay đổi](#9-lịch-sử-thay-đổi).

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
| `code` | string (≤32) | ✅ | **Mã khoa duy nhất** (vd `CARDIO`). Dùng để tham chiếu ổn định. |
| `name` | string (≤255) | ✅ | Tên hiển thị (vd `Tim mạch`). |
| `description` | string (≤5000) | — | Mô tả giàu thông tin về khoa. *(Dùng cho AI semantic match.)* |
| `keywords` | string[] | — | Danh sách **triệu chứng** dạng tag (vd `chest_pain`, `hypertension`). Tối đa 50 phần tử, mỗi phần tử ≤64 ký tự. |
| `conditions` | string[] | — | Danh sách **bệnh lý điển hình** của khoa (vd `arrhythmia`). Tối đa 50 phần tử, mỗi phần tử ≤128 ký tự. |
| `ai_metadata` | object | — | Metadata mở rộng tự do (vd `{ "icd10": ["I20-I25"], "age_group": "adult" }`). |
| `head_doctor_id` | int \| null | — | ID **trưởng khoa** (tham chiếu user). Có thể bỏ trống, bổ nhiệm sau. |
| `head_doctor` | object \| null | — | Thông tin rút gọn của trưởng khoa: `{ "id", "full_name" }`. |
| `is_active` | bool | — | Khoa còn hoạt động hay không. |
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
  "code": "CARDIO",                       // bắt buộc, duy nhất
  "name": "Tim mạch",                     // bắt buộc
  "description": "Khoa chẩn đoán và điều trị bệnh lý tim mạch.",
  "keywords": ["chest_pain", "palpitations", "hypertension"],
  "conditions": ["myocardial_infarction", "arrhythmia"],
  "ai_metadata": { "icd10": ["I20-I25"], "age_group": "adult" },
  "head_doctor_id": 2                     // tùy chọn — ID của một user là bác sĩ
}
```

> Các trường `description`, `keywords`, `conditions`, `ai_metadata`, `head_doctor_id` đều **tùy chọn**.
> Tối thiểu chỉ cần `code` và `name`.

### Response — `201 Created`

```jsonc
{
  "status": "success",
  "code": "201",
  "message": "Tạo khoa thành công.",
  "data": {
    "id": 1,
    "code": "CARDIO",
    "name": "Tim mạch",
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

### Các lỗi có thể gặp

| HTTP | Khi nào | `message` |
|---|---|---|
| **409** | `code` đã tồn tại | "Mã khoa này đã tồn tại." |
| **404** | `head_doctor_id` không trỏ tới user nào | "Không tìm thấy trưởng khoa được chọn." |
| **400** | User được chọn **không phải bác sĩ** | "Người dùng được chọn phải có role bác sĩ." |
| **422** | Thiếu/sai field (vd thiếu `code`, `keywords` không phải mảng chuỗi) | "Dữ liệu không hợp lệ." (kèm `data` chi tiết theo field) |
| **403** | Thiếu permission `department:manage` | "Bạn không có quyền thực hiện hành động này." |

Ví dụ body lỗi `422` (chi tiết theo từng field, reason code dạng máy đọc):

```jsonc
{
  "status": "error", "code": "422", "message": "Dữ liệu không hợp lệ.",
  "data": { "code": "required", "keywords": "invalid_item" },
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
      "id": 1, "code": "CARDIO", "name": "Tim mạch",
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

## 5. Ví dụ tích hợp (JS)

Dùng wrapper `apiFetch` mô tả trong [`FE_RBAC.md`](./FE_RBAC.md) mục 4.

```js
// Lấy danh sách khoa (phân trang)
async function loadDepartments(page = 1) {
  const body = await apiFetch(`/api/v1/departments?page=${page}&size=20`);
  return body ? { departments: body.data, meta: body.meta } : null;
}

// Tạo khoa mới
async function createDepartment(payload) {
  // payload: { code, name, description?, keywords?, conditions?, ai_metadata?, head_doctor_id? }
  const body = await apiFetch(`/api/v1/departments`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return body?.data ?? null; // null nếu lỗi (đã được wrapper xử lý hiển thị)
}
```

### Gợi ý form tạo khoa (React)

```jsx
// keywords/conditions nên dùng tag-input -> mảng chuỗi
const [form, setForm] = useState({
  code: "", name: "", description: "",
  keywords: [], conditions: [], ai_metadata: {}, head_doctor_id: null,
});

async function onSubmit() {
  // Loại bỏ field rỗng để body gọn (BE coi như không gửi)
  const payload = { code: form.code.trim(), name: form.name.trim() };
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

## 6. Lưu ý quan trọng

- **`keywords` / `conditions` là mảng chuỗi**, không phải chuỗi phân tách dấu phẩy. Gửi sai kiểu → `422`.
- **Mã khoa (`code`) là duy nhất** và nên ổn định (không đổi sau khi tạo) vì là điểm tham chiếu.
- **Side effect khi gán trưởng khoa:** user được chọn sẽ **được nâng quyền** lên `department_head`
  ngay lập tức. Nếu user đang đăng nhập, quyền mới chỉ thấy sau khi gọi lại `GET /me` (xem `FE_RBAC.md`).
- **Trường AI là nền tảng cho tính năng gợi ý sau này** — nên khuyến khích admin nhập đầy đủ
  `keywords`, `conditions`, `description` để chất lượng gợi ý định tuyến tốt hơn.

---

## 7. Checklist tích hợp

- [ ] Gate menu/route "Quản lý khoa" theo permission `department:manage`.
- [ ] Form tạo khoa: `code` + `name` bắt buộc; `keywords`/`conditions` dùng tag-input (mảng chuỗi).
- [ ] Ô chọn trưởng khoa: chỉ liệt kê user có role `doctor`; cho phép để trống.
- [ ] Xử lý lỗi: `409` (trùng mã), `400` (không phải bác sĩ), `404` (không tìm thấy user), `422` (sai dữ liệu).
- [ ] Màn hình danh sách khoa: phân trang qua `meta`, hiển thị `head_doctor` và `is_active`.

---

## 8. Tóm tắt endpoint

| Method | Path | Permission | Mô tả |
|---|---|---|---|
| `POST` | `/api/v1/departments` | `department:manage` | Tạo khoa mới |
| `GET` | `/api/v1/departments` | `department:manage` | Danh sách khoa (phân trang) |

---

## 9. Lịch sử thay đổi

| Phiên bản | Thay đổi |
|---|---|
| **1.0.0** | Bản đầu: tạo khoa (`POST /departments`) với trường phục vụ AI (`keywords`, `conditions`, `description`, `ai_metadata`), chọn trưởng khoa (tùy chọn, phải là bác sĩ, tự cấp role `department_head`); danh sách khoa (`GET /departments`). |
