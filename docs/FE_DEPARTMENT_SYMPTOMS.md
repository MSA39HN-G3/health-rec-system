# Hướng dẫn FE: Lấy triệu chứng theo chuyên khoa (`GET /api/v1/symptoms`)

> **Phiên bản: 1.0.0** — Bổ sung query `department_id` để lọc danh sách triệu chứng
> theo chuyên khoa. Trước 1.0.0, `GET /api/v1/symptoms` không nhận `department_id`
> (chỉ lọc theo `category_id`, `is_active`).

Tài liệu này mô tả cách FE dùng `GET /api/v1/symptoms` để lấy **danh sách triệu chứng
của 1 chuyên khoa** — phục vụ màn hình quản trị kiểu:

> Khoa Tim mạch đang phụ trách các triệu chứng: Đau ngực, Hồi hộp, Khó thở…

---

## 1. Đối tượng & quyền truy cập

| Hành động | Endpoint | Permission | Mặc định có ở role |
|---|---|---|---|
| Xem danh sách triệu chứng (kể cả lọc theo khoa) | `GET /api/v1/symptoms` | _không yêu cầu_ | mọi user đăng nhập |
| Tạo / sửa / xóa triệu chứng | `POST/PATCH/DELETE /api/v1/symptoms/{id}` | `symptom:manage` | `admin` |
| Tạo / sửa / xóa nhóm triệu chứng | `POST/PATCH/DELETE /api/v1/symptoms/categories/{id}` | `symptom:manage` | `admin` |

Endpoint lọc theo khoa trong tài liệu này (`GET /api/v1/symptoms?department_id=…`)
**không yêu cầu permission** — chỉ cần `Authorization: Bearer <token>` hợp lệ.

> Tài liệu liên quan: [`FE_RBAC.md`](./FE_RBAC.md) (phân quyền),
> [`FE_DEPARTMENT.md`](./FE_DEPARTMENT.md) (quản lý khoa),
> [`FE_AUTH_TOKEN.md`](./FE_AUTH_TOKEN.md) (token).

---

## 2. Tóm tắt endpoint

| Mục đích | Method + Path | Permission |
|---|---|---|
| Lấy danh sách triệu chứng (lọc được theo khoa) | `GET /api/v1/symptoms` | _không_ |
| Lấy chi tiết 1 triệu chứng | `GET /api/v1/symptoms/{id}` | _không_ |
| Tạo triệu chứng mới | `POST /api/v1/symptoms` | `symptom:manage` |
| Cập nhật triệu chứng | `PATCH /api/v1/symptoms/{id}` | `symptom:manage` |
| Vô hiệu hóa triệu chứng | `DELETE /api/v1/symptoms/{id}` | `symptom:manage` |
| Lấy danh sách nhóm triệu chứng | `GET /api/v1/symptoms/categories` | _không_ |

> Chỉ endpoint **`GET /api/v1/symptoms`** (lọc theo khoa) nằm trong phạm vi tài liệu
> này. Các endpoint khác giữ nguyên hành vi như phiên bản trước — xem chú thích ở mục 7.

---

## 3. Lấy triệu chứng theo chuyên khoa — `GET /api/v1/symptoms`

### 3.1 Query parameters

| Query | Kiểu | Bắt buộc | Mặc định | Ràng buộc | Mô tả |
|---|---|---|---|---|---|
| `page` | integer | không | `1` | ≥ 1 | Số trang |
| `size` | integer | không | `20` | 1–100 | Số phần tử / trang |
| `category_id` | integer | không | — | — | Lọc theo ID nhóm triệu chứng |
| `is_active` | boolean | không | — | — | `true` = chỉ lấy triệu chứng đang hoạt động, `false` = chỉ lấy đã vô hiệu, bỏ trống = lấy tất cả |
| **`department_id`** | integer | không | — | ≥ 1 | **ID chuyên khoa — lấy triệu chứng đang được gán cho khoa này** |

> Khi truyền `department_id` không tồn tại, API trả **404** với message key
> `errors.department_not_found` (xem mục 6.2).

### 3.2 Quy tắc lọc `department_id`

- Truyền `department_id` → kết quả chỉ chứa triệu chứng **đang được map** với khoa đó
  trong bảng `symptom_department_map`.
- Kết hợp được với `category_id` và `is_active` (cả 3 filter compose bằng phép AND).
- Một triệu chứng có thể được gán cho nhiều khoa — query chỉ trả về 1 row mỗi
  triệu chứng (không nhân bản theo số khoa).
- Không truyền `department_id` → trả về **tất cả** triệu chứng (giống phiên bản cũ).

### 3.3 Request ví dụ

```http
GET /api/v1/symptoms?department_id=1&page=1&size=20 HTTP/1.1
Host: api.example.com
Authorization: Bearer <token>
Accept: application/json
```

```http
GET /api/v1/symptoms?department_id=1&category_id=3&is_active=true HTTP/1.1
Host: api.example.com
Authorization: Bearer <token>
```

### 3.4 Response thành công — `200 OK`

```jsonc
// GET /api/v1/symptoms?department_id=1&page=1&size=20
{
  "status": "success",
  "code": "200",
  "message": null,
  "data": [
    {
      "id": 12,
      "code": "CHEST_PAIN",
      "name": "Đau ngực",
      "description": "Đau vùng ngực, có thể lan ra cánh tay trái.",
      "category": {
        "id": 3,
        "name": "Triệu chứng tim mạch",
        "description": null
      },
      "synonyms": ["đau thắt ngực", "tức ngực"],
      "is_active": true,
      "created_at": "2026-06-27T10:00:00+00:00",
      "updated_at": "2026-07-01T08:30:00+00:00"
    },
    {
      "id": 18,
      "code": "PALPITATION",
      "name": "Hồi hộp, đánh trống ngực",
      "description": null,
      "category": { "id": 3, "name": "Triệu chứng tim mạch", "description": null },
      "synonyms": [],
      "is_active": true,
      "created_at": "2026-06-28T03:12:00+00:00",
      "updated_at": "2026-06-28T03:12:00+00:00"
    }
  ],
  "meta": {
    "page": 1,
    "size": 20,
    "totalPage": 1
  }
}
```

> `data` là **mảng** phẳng các `Symptom`, **không** chứa `weight` / `note` của bảng
> `symptom_department_map`. Nếu sau này cần trọng số mapping, BE sẽ thêm endpoint mới
> `GET /api/v1/departments/{id}/symptoms` (xem mục 7).

### 3.5 Response lỗi — `404 Not Found`

`department_id` không tồn tại:

```jsonc
{
  "status": "error",
  "code": "404",
  "message": "Không tìm thấy khoa.",
  "data": null,
  "error_details": { "key": "errors.department_not_found" }
}
```

`department_id` không hợp lệ (`< 1` hoặc không phải số) → **422 Validation**.

---

## 4. Use case gợi ý cho FE

### 4.1 Màn hình "Triệu chứng của khoa X"

1. User mở chi tiết khoa `id=1` (Tim mạch).
2. Tab "Triệu chứng" gọi:

   ```ts
   GET /api/v1/symptoms?department_id=1&is_active=true&page=1&size=50
   ```

3. Hiển thị danh sách `data[]`. Phân trang bằng `meta.totalPage`.
4. Mỗi dòng có thể click → gọi `GET /api/v1/symptoms/{id}` để xem chi tiết
   (nếu cần thêm `description` / `synonyms`).

### 4.2 Tìm triệu chứng để thêm vào khoa

1. User bấm "Thêm triệu chứng cho khoa này".
2. Modal tìm kiếm gọi `GET /api/v1/symptoms?page=1&size=20&q=...` (lưu ý: **không**
   truyền `department_id` để lấy tất cả triệu chứng, kể cả đã gán cho khoa khác).
3. Sau khi chọn triệu chứng, gọi API tạo mapping
   (xem chú thích mục 7 — hiện chưa có endpoint CRUD `symptom_department_map`
   trong bản 1.0.0; nếu cần, liên hệ BE để bổ sung).

### 4.3 Lọc gộp theo khoa + nhóm

```ts
// Lấy triệu chứng tim mạch đang active trong khoa Tim mạch
GET /api/v1/symptoms?department_id=1&category_id=3&is_active=true
```

---

## 5. Code mẫu

### 5.1 React Query / SWR

```ts
type Symptom = {
  id: number;
  code: string;
  name: string;
  description: string | null;
  category: { id: number; name: string; description: string | null } | null;
  synonyms: string[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

type Paginated<T> = {
  data: T[];
  meta: { page: number; size: number; totalPage: number };
};

async function listSymptoms(params: {
  page?: number;
  size?: number;
  category_id?: number;
  is_active?: boolean;
  department_id?: number;          // 1.0.0+
} = {}): Promise<Paginated<Symptom>> {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null) qs.set(k, String(v));
  });
  const res = await fetch(`/api/v1/symptoms?${qs}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

// Hook: triệu chứng của khoa
function useDepartmentSymptoms(departmentId: number, page = 1) {
  return useQuery({
    queryKey: ["symptoms", "by-department", departmentId, page],
    queryFn: () => listSymptoms({ department_id: departmentId, page, size: 50 }),
    enabled: Number.isFinite(departmentId),
  });
}
```

### 5.2 Axios

```ts
const res = await axios.get<Paginated<Symptom>>("/api/v1/symptoms", {
  params: { department_id: 1, page: 1, size: 20 },
  headers: { Authorization: `Bearer ${token}` },
});
const items = res.data.data;
const totalPage = res.data.meta.totalPage;
```

---

## 6. Lỗi thường gặp

### 6.1 401 — Chưa đăng nhập / token hết hạn

```jsonc
{ "status": "error", "code": "401", "message": "Unauthorized.", "data": null }
```

→ Refresh token và thử lại (xem [`FE_AUTH_TOKEN.md`](./FE_AUTH_TOKEN.md)).

### 6.2 404 — `department_id` không tồn tại

```jsonc
{ "status": "error", "code": "404",
  "message": "Không tìm thấy khoa.",
  "error_details": { "key": "errors.department_not_found" } }
```

→ FE nên kiểm tra `department_id` hợp lệ trước khi gọi (vd truy vấn từ
`GET /api/v1/departments` rồi mới mở tab triệu chứng). Không hiển thị lỗi
này như crash — chỉ ẩn tab hoặc hiện "Khoa không tồn tại".

### 6.3 422 — `department_id` không hợp lệ

Truyền `department_id=0`, `department_id=-1`, hoặc `department_id=abc` →
trả 422 với `error_details.field = "department_id"` (lỗi validation chung).

→ FE chỉ nên truyền số nguyên dương lấy từ danh sách khoa.

### 6.4 200 nhưng `data: []`

Có 3 nguyên nhân:

1. Khoa `department_id=X` chưa được gán triệu chứng nào trong bảng
   `symptom_department_map` → đúng kỳ vọng, hiển thị empty state.
2. Khoa chỉ gán triệu chứng đã `is_active=false` mà FE lọc `is_active=true` → bỏ
   filter `is_active` để kiểm tra.
3. Tất cả triệu chứng của khoa đó nằm ở trang khác (vượt `page` hiện tại) → kiểm
   tra `meta.totalPage` và tăng `page`.

---

## 7. Lưu ý & định hướng tiếp theo

- **Bản 1.0.0 chỉ thêm filter `department_id` cho `GET /api/v1/symptoms`.**
  Response vẫn là danh sách `Symptom` phẳng; **chưa trả `weight` / `note`** từ
  bảng `symptom_department_map`.
- Endpoint CRUD cho `symptom_department_map`
  (vd `POST /api/v1/departments/{id}/symptoms` để gán triệu chứng + weight,
  `DELETE` để bỏ gán) **chưa có trong bản 1.0.0** — model bảng đã sẵn sàng trong
  DB nhưng route/service chưa được implement. Nếu cần, yêu cầu BE bổ sung trong
  sprint tiếp theo.
- Phạm vi `category_id` không thay đổi so với phiên bản trước — vẫn filter theo
  `SymptomCategory.id` của chính triệu chứng (không phải nhóm của khoa).
