# Hướng dẫn FE: Phân quyền RBAC (role & permission)

> **Phiên bản: 1.4.0** — Bỏ role `patient` + 3 permission `rating:*` + toàn bộ
> tính năng đánh giá bác sĩ. Migration `1c2d3e4f5a6b`. Hệ thống giờ chỉ có 2
> role: `admin`, `staff`.
>
> Tài liệu liên quan: [`FE_GOOGLE_LOGIN.md`](./FE_GOOGLE_LOGIN.md) (đăng nhập),
> [`FE_AUTH_TOKEN.md`](./FE_AUTH_TOKEN.md) (token, gọi API có bảo vệ).

---

## 1. Lấy role & permission của user

Cả response đăng nhập (`/google/callback`) và `GET /api/v1/auth/me` đều trả về `user`
kèm `roles` và `permissions`:

```jsonc
{
  "status": "success",
  "data": {
    "user": {
      "id": 1,
      "email": "staff@hospital.com",
      "full_name": "Nguyen Van Staff",
      "roles": ["staff"],
      "permissions": ["record:read", "record:write"],
      "email_verified": true,
      "is_active": true,
      "last_login_at": "2026-06-27T10:00:00+00:00"
    }
  }
}
```

- `roles`: danh sách **tên role** user đang có (vd `["staff"]`, có thể nhiều). Role `doctor` đã bỏ từ 1.3.0.
- `permissions`: **gộp** mọi permission từ các role của user (đây là thứ FE nên dùng để gate UI).
- `is_active`: `false` nghĩa là tài khoản **bị vô hiệu hóa** — user không làm được gì (xem mục 4 & 5.4).
- User mới onboard: `roles: []`, `permissions: []` (chưa được admin gán).

> **Nên gate UI theo `permissions`, không theo `roles`.** Vì quyền của một role có thể
> thay đổi trong DB (admin gán/gỡ permission) mà không cần đổi code FE.

---

## 2. Bộ role & permission hiện có

### Roles
| Role | Ý nghĩa |
|---|---|
| `admin` | Quản trị, quản lý user & phân quyền |
| `staff` | Nhân viên (lễ tân, điều dưỡng, **và** trưởng khoa cũ) — sau 1.3.0 quản lý tất cả bác sĩ. |

> ⚠️ Từ 1.3.0 role `doctor` đã bị xóa. Từ 1.4.0 role `patient` cũng bị xóa
> cùng toàn bộ tính năng đánh giá.

### Permissions
| Permission | Ý nghĩa | Role mặc định có |
|---|---|---|
| `user:read` | Xem danh sách user | admin |
| `user:manage` | Gán/gỡ role cho user | admin |
| `role:manage` | Tạo role, gán/gỡ permission | admin |
| `record:read` | Xem hồ sơ sức khỏe | staff |
| `record:write` | Tạo/sửa hồ sơ sức khỏe | staff |
| `department:manage` | Quản lý khoa (xem [`FE_DEPARTMENT.md`](./FE_DEPARTMENT.md)) | admin, staff |

> Mapping trên là **mặc định khi seed**; admin có thể thay đổi qua API quản lý role.

---

## 3. Gate UI theo permission

### Helper kiểm tra quyền

```js
// Giả sử bạn lưu user hiện tại sau khi đăng nhập / gọi /me
let currentUser = null; // { roles: [...], permissions: [...] }

function hasPermission(...perms) {
  if (!currentUser) return false;
  const owned = new Set(currentUser.permissions);
  return perms.some((p) => owned.has(p));   // có ÍT NHẤT một quyền
}

function hasRole(...roles) {
  if (!currentUser) return false;
  const owned = new Set(currentUser.roles);
  return roles.some((r) => owned.has(r));
}
```

### Ví dụ ẩn/hiện nút

```js
if (hasPermission("user:manage")) {
  showMenuItem("Quản lý người dùng");
}
if (hasPermission("record:write")) {
  showButton("Tạo hồ sơ");
}
```

---

## 4. Xử lý 401 vs 403

| HTTP | Ý nghĩa | FE nên làm |
|---|---|---|
| **401** | Chưa đăng nhập / token sai/hết hạn/bị thu hồi | Xoá token → chuyển về trang đăng nhập |
| **403** | Đã đăng nhập nhưng **không đủ quyền** | Hiện thông báo "Bạn không có quyền…", KHÔNG đăng xuất |
| **403** (tài khoản bị vô hiệu hóa) | Tài khoản đã bị admin disable — chặn **mọi** thao tác | Xoá token → đưa về trang đăng nhập kèm thông báo bị khóa |

Body lỗi 403 (thiếu quyền):

```json
{ "status": "error", "code": "403", "message": "Bạn không có quyền thực hiện hành động này.", "data": null, "meta": null }
```

Body lỗi 403 (tài khoản bị vô hiệu hóa):

```json
{ "status": "error", "code": "403", "message": "Tài khoản của bạn đã bị vô hiệu hóa. Vui lòng liên hệ quản trị viên.", "data": null, "meta": null }
```

> **Lưu ý:** disable có hiệu lực **ngay lập tức** — token đang dùng của user bị khóa sẽ bị
> chặn ở request kế tiếp (BE kiểm tra trạng thái mỗi request), và user cũng **không đăng nhập lại được**.
> Vì 2 loại 403 có ý nghĩa khác nhau, FE nên phân biệt: nếu cần xử lý riêng "bị khóa"
> (đăng xuất hẳn) khác với "thiếu quyền" (chỉ báo lỗi), hãy đối chiếu `message` trả về.

Gợi ý wrapper gọi API (mở rộng từ `FE_AUTH_TOKEN.md`):

```js
async function apiFetch(path, options = {}) {
  const token = localStorage.getItem("access_token");
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
  const body = await res.json().catch(() => null);

  if (res.status === 401) {
    localStorage.removeItem("access_token");
    window.location.href = "/login";
    return null;
  }
  if (res.status === 403) {
    showError(body?.message || "Bạn không có quyền thực hiện hành động này.");
    return null;
  }
  return body;
}
```

---

## 5. API khu vực Admin

Tất cả yêu cầu `Authorization: Bearer <token>` và **permission tương ứng** (403 nếu thiếu).

### 5.1. Danh sách user — `GET /api/v1/admin/users`
Cần `user:read`. Hỗ trợ phân trang.

| Query | Mặc định | Ràng buộc |
|---|---|---|
| `page` | 1 | ≥ 1 |
| `size` | 20 | 1–100 |

```jsonc
// GET /api/v1/admin/users?page=1&size=20
{
  "status": "success", "code": "200", "message": null,
  "data": [ { "id": 1, "email": "...", "roles": ["staff"], "permissions": ["record:read","record:write"], ... } ],
  "meta": { "page": 1, "size": 20, "totalPage": 3 }
}
```

> `data` là **mảng**; thông tin phân trang nằm ở `meta`.

### 5.2. Gán role cho user — `POST /api/v1/admin/users/<id>/roles`
Cần `user:manage`. Body: `{ "role": "staff" }`

```jsonc
// 200 OK
{ "status": "success", "message": "Gán role cho user thành công.",
  "data": { "user": { "id": 2, "roles": ["staff"], "permissions": ["record:read","record:write"], ... } } }
```
Lỗi: `404` nếu user hoặc role không tồn tại; `422` nếu thiếu `role`. Role hợp lệ hiện tại: `admin`, `staff`, `patient` (role `doctor` đã bỏ ở 1.3.0).

### 5.3. Gỡ role khỏi user — `DELETE /api/v1/admin/users/<id>/roles/<role_name>`
Cần `user:manage`.

```jsonc
// DELETE /api/v1/admin/users/2/roles/staff  -> 200
{ "status": "success", "message": "Gỡ role khỏi user thành công.",
  "data": { "user": { "id": 2, "roles": [], "permissions": [], ... } } }
```

### 5.4. Bật/tắt (disable) tài khoản user — `PATCH /api/v1/admin/users/<id>/status`
Cần `user:manage`. Body: `{ "is_active": false }` để vô hiệu hóa, `true` để kích hoạt lại.

```jsonc
// PATCH /api/v1/admin/users/2/status   { "is_active": false }  -> 200
{ "status": "success", "message": "Cập nhật trạng thái user thành công.",
  "data": { "user": { "id": 2, "is_active": false, "roles": ["staff"], ... } } }
```

- Khi `is_active = false`: user bị chặn **mọi** thao tác ngay lập tức và không đăng nhập lại được.
- Lỗi `404` nếu user không tồn tại; `422` nếu thiếu/sai `is_active`.
- **`400`** nếu admin cố vô hiệu hóa **chính tài khoản của mình** (chống tự khóa):
  ```json
  { "status": "error", "code": "400", "message": "Bạn không thể vô hiệu hóa tài khoản của chính mình.", "data": null, "meta": null }
  ```

### 5.5. Danh sách role — `GET /api/v1/admin/roles`
Cần `role:manage`.

```jsonc
{ "status": "success",
  "data": [ { "id": 1, "name": "admin", "description": null, "permissions": ["role:manage","user:manage","user:read"] } ] }
```

### 5.6. Tạo role — `POST /api/v1/admin/roles`
Cần `role:manage`. Body: `{ "name": "nurse", "description": "Y tá" }`
→ `201 Created`. Lỗi `409` nếu tên role đã tồn tại.

### 5.7. Gán permission cho role — `POST /api/v1/admin/roles/<id>/permissions`
Cần `role:manage`. Body: `{ "permission": "record:read" }`

### 5.8. Gỡ permission khỏi role — `DELETE /api/v1/admin/roles/<id>/permissions/<permission_name>`
Cần `role:manage`.

### 5.9. Danh sách permission — `GET /api/v1/admin/permissions`
Cần `role:manage`. Trả về toàn bộ permission để admin chọn khi gán cho role.

---

## 6. Ví dụ React

### Gate component theo permission

```jsx
function Can({ perm, children }) {
  return hasPermission(perm) ? children : null;
}

// Dùng:
<Can perm="user:manage">
  <Link to="/admin/users">Quản lý người dùng</Link>
</Can>
```

### Bảo vệ route theo permission

```jsx
function RequirePermission({ perm, children }) {
  if (!currentUser) return <Navigate to="/login" replace />;
  if (!hasPermission(perm)) return <p>Bạn không có quyền truy cập trang này.</p>;
  return children;
}

// Dùng:
<Route path="/admin/users" element={
  <RequirePermission perm="user:read"><AdminUsers /></RequirePermission>
} />
```

### Màn hình admin gán role

```js
async function loadUsers(page = 1) {
  const body = await apiFetch(`/api/v1/admin/users?page=${page}&size=20`);
  return body ? { users: body.data, meta: body.meta } : null;
}

async function assignRole(userId, role) {
  const body = await apiFetch(`/api/v1/admin/users/${userId}/roles`, {
    method: "POST",
    body: JSON.stringify({ role }),
  });
  return body?.data?.user ?? null;
}

async function removeRole(userId, role) {
  const body = await apiFetch(`/api/v1/admin/users/${userId}/roles/${role}`, {
    method: "DELETE",
  });
  return body?.data?.user ?? null;
}

// Bật/tắt tài khoản (disable = isActive false)
async function setUserActive(userId, isActive) {
  const body = await apiFetch(`/api/v1/admin/users/${userId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ is_active: isActive }),
  });
  return body?.data?.user ?? null;
}
```

---

## 7. Lưu ý quan trọng

- **FE gate chỉ để trải nghiệm.** Luôn để BE là nơi chốt quyền — đừng giả định ẩn nút là an toàn.
- **Làm mới quyền sau khi đổi:** nếu admin đổi role/permission của user đang đăng nhập, FE chỉ thấy thay đổi sau khi gọi lại `GET /me` hoặc đăng nhập lại (permission nằm trong dữ liệu user, không nằm trong token).
- **User mới chưa có quyền:** sau onboard, `permissions` rỗng → FE nên hiện màn hình "Tài khoản chờ cấp quyền" thay vì lỗi.
- **Dùng `permissions` để gate, `roles` để hiển thị** (vd badge "Bác sĩ").
- **Tài khoản bị vô hiệu hóa:** khi user đang đăng nhập bị admin disable, request kế tiếp trả 403 → FE nên đăng xuất hẳn và báo bị khóa. Trong màn hình admin, nên hiển thị trạng thái `is_active` (vd badge "Đã khóa") và nút bật/tắt.

---

## 8. Checklist tích hợp

- [ ] Lưu `user` (kèm `roles`, `permissions`) sau khi đăng nhập; làm mới bằng `GET /me` khi cần.
- [ ] Viết helper `hasPermission()` / `hasRole()` và gate menu/nút/route theo `permissions`.
- [ ] Phân biệt 401 (đăng xuất) và 403 (báo thiếu quyền) trong wrapper gọi API.
- [ ] Màn hình admin: list user (phân trang qua `meta`), gán/gỡ role, quản lý role–permission.
- [ ] Màn hình admin: hiển thị `is_active` + nút bật/tắt tài khoản (ẩn nút tắt cho chính mình).
- [ ] Xử lý trạng thái user chưa có quyền (permissions rỗng) và tài khoản bị vô hiệu hóa (403).

---

## 10. Lịch sử thay đổi

| Phiên bản | Thay đổi |
|---|---|
| **1.4.0** | **Bỏ role `patient` + 3 permission `rating:*` + tính năng đánh giá bác sĩ**. Hệ thống chỉ còn 2 role (`admin`, `staff`). FE cần dọn các màn hình rating (danh sách, form tạo/sửa đánh giá). Migration `1c2d3e4f5a6b`. |
| **1.3.0** | **Bỏ role `doctor` và `head_doctor_id`**. Staff giờ quản lý tất cả bác sĩ (mọi khoa); UI gate theo permission không đổi. Migration `1a2b3c4d5e6f`. Cập nhật §2 Roles, §2 Permissions (record:* giờ chỉ ở staff), §5.2, §5.3. |
| **1.2.0** | Gộp role `department_head` vào `staff`. FE gate UI y hệt (permission không đổi). Tên role hiển thị: dùng `staff` thay cho `department_head`. |
| **1.1.0** | Thêm trạng thái tài khoản `is_active`: endpoint `PATCH /admin/users/<id>/status` (mục 5.4), trường `is_active` trong `user`, xử lý 403 khi tài khoản bị vô hiệu hóa, không cho admin tự khóa (400). |
| **1.0.0** | Bản đầu: roles & permissions (nhiều-nhiều), gate UI theo permission, API admin quản lý user/role/permission. |
```
