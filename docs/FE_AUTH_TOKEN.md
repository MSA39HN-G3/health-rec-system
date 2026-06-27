# Hướng dẫn FE: Token phiên, gọi API có bảo vệ & Đăng xuất

Sau khi đăng nhập Google thành công (xem [`FE_GOOGLE_LOGIN.md`](./FE_GOOGLE_LOGIN.md)),
BE cấp một **access token (JWT)**. FE dùng token này để gọi các API cần đăng nhập.
Khi đăng xuất, token bị đưa vào **blacklist** và không dùng được nữa.

---

## 1. Vòng đời token

```
Đăng nhập (callback)  ──►  nhận access_token  ──►  gọi API kèm "Authorization: Bearer <token>"
                                                          │
                                                          ▼
                                              Đăng xuất (/logout)
                                                          │
                                                          ▼
                                       token vào blacklist → mọi request sau bị 401
```

- Token có hạn dùng (mặc định **1 giờ**). Hết hạn → phải đăng nhập lại.
- Token là **stateless (JWT)**: BE không lưu session, chỉ lưu danh sách token đã thu hồi.
- Đăng xuất **thu hồi ngay** token hiện tại (không chờ hết hạn).

---

## 2. Lấy token (khi đăng nhập)

`POST /api/v1/auth/google/callback` trả về token trong `data`:

```jsonc
{
  "status": "success",
  "code": "200",                 // 201 nếu là user mới (onboard)
  "message": "Đăng nhập thành công.",
  "data": {
    "user": { "id": 1, "email": "user@gmail.com", "full_name": "...", ... },
    "is_new_user": false,
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "Bearer",
    "expires_at": "2026-06-27T10:00:00+00:00"
  },
  "meta": null
}
```

FE lưu `access_token` lại để dùng cho các request sau.

> **Lưu token ở đâu?** Đơn giản nhất là `localStorage`/`sessionStorage`. Cân nhắc
> rủi ro XSS; nếu cần an toàn cao hơn hãy dùng cookie `HttpOnly` (yêu cầu BE đổi cách
> phát token — hiện chưa hỗ trợ).

---

## 3. Gọi API cần đăng nhập

Đính token vào header `Authorization`:

```
Authorization: Bearer <access_token>
```

### API tham chiếu

| API | Method | Auth | Mô tả |
|---|---|---|---|
| `/api/v1/auth/me` | GET | ✅ Bearer | Lấy thông tin user của token hiện tại |
| `/api/v1/auth/logout` | POST | ✅ Bearer | Thu hồi token hiện tại (đăng xuất) |

**`GET /api/v1/auth/me` — thành công (200):**

```json
{
  "status": "success", "code": "200", "message": null,
  "data": { "user": { "id": 1, "email": "user@gmail.com", "full_name": "...", "picture": "...", "email_verified": true, "last_login_at": "..." } },
  "meta": null
}
```

**`POST /api/v1/auth/logout` — thành công (200):**

```json
{ "status": "success", "code": "200", "message": "Đăng xuất thành công.", "data": null, "meta": null }
```

---

## 4. Các lỗi xác thực (401)

Tất cả đều HTTP **401** với `message` khác nhau — FE nên xử lý chung: **xóa token + đưa về trang đăng nhập**.

| Tình huống | `message` (vi) |
|---|---|
| Không gửi header `Authorization` | Thiếu token xác thực. |
| Token sai/hỏng/không giải mã được | Token xác thực không hợp lệ. |
| Token hết hạn | Token xác thực đã hết hạn. |
| Token đã đăng xuất (nằm trong blacklist) | Token xác thực đã bị thu hồi. Vui lòng đăng nhập lại. |

Ví dụ body lỗi:

```json
{ "status": "error", "code": "401", "message": "Token xác thực đã bị thu hồi. Vui lòng đăng nhập lại.", "data": null, "meta": null }
```

---

## 5. Triển khai FE (ví dụ JavaScript)

### 5.1. Wrapper gọi API tự đính token & xử lý 401

```js
const API_BASE = "http://localhost:5000";

function getToken() {
  return localStorage.getItem("access_token");
}

async function apiFetch(path, options = {}) {
  const token = getToken();
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const body = await res.json().catch(() => null);

  // Token thiếu/hết hạn/bị thu hồi -> đăng xuất phía FE.
  if (res.status === 401) {
    localStorage.removeItem("access_token");
    window.location.href = "/login";
    return null;
  }
  return body;
}
```

### 5.2. Lưu token sau khi đăng nhập

```js
// Trong trang callback, sau khi POST /google/callback thành công:
if (body.status === "success") {
  localStorage.setItem("access_token", body.data.access_token);
  // (tuỳ chọn) lưu thời điểm hết hạn để chủ động làm mới phiên:
  localStorage.setItem("token_expires_at", body.data.expires_at);
  window.location.href = "/";
}
```

### 5.3. Lấy thông tin user hiện tại

```js
async function loadCurrentUser() {
  const body = await apiFetch("/api/v1/auth/me");
  if (body?.status === "success") {
    return body.data.user;
  }
  return null;
}
```

### 5.4. Đăng xuất

```js
async function logout() {
  // Báo BE thu hồi token (blacklist). Kể cả thất bại vẫn xoá token phía FE.
  await apiFetch("/api/v1/auth/logout", { method: "POST" });
  localStorage.removeItem("access_token");
  localStorage.removeItem("token_expires_at");
  window.location.href = "/login";
}
```

---

## 6. Ví dụ React (tóm tắt)

```jsx
// Bảo vệ route phía FE
function RequireAuth({ children }) {
  const [user, setUser] = useState(undefined); // undefined = đang kiểm tra
  useEffect(() => { loadCurrentUser().then(setUser); }, []);

  if (user === undefined) return <p>Đang tải…</p>;
  if (user === null) return <Navigate to="/login" replace />;
  return children;
}

// Nút đăng xuất
function LogoutButton() {
  return <button onClick={logout}>Đăng xuất</button>;
}
```

---

## 7. Cấu hình liên quan (BE)

| Biến môi trường | Mặc định | Ý nghĩa |
|---|---|---|
| `JWT_SECRET` | = `SECRET_KEY` | Khóa ký JWT. **Bắt buộc đổi** ở production. |
| `JWT_ALGORITHM` | `HS256` | Thuật toán ký |
| `JWT_EXPIRES` | `3600` | Hạn token (giây) |

---

## 8. Lưu ý quan trọng

- **Header phải đúng định dạng:** `Authorization: Bearer <token>` (có chữ `Bearer` và một dấu cách).
- **Không có refresh token:** khi token hết hạn (mặc định 1 giờ), người dùng phải đăng nhập lại. Nếu cần phiên dài hơn, tăng `JWT_EXPIRES` hoặc đề nghị BE bổ sung refresh token.
- **Đổi `JWT_SECRET` sẽ vô hiệu hoá toàn bộ token đang phát** (mọi người phải đăng nhập lại).
- **CORS:** FE phải chạy đúng origin trong `CORS_ORIGINS` của BE.
- **Đăng xuất 2 lần:** sau khi logout, gọi lại bất kỳ API bảo vệ nào (kể cả `/logout`) với token cũ đều trả 401 "đã bị thu hồi" — đúng như thiết kế.

---

## 9. Checklist tích hợp

- [ ] Lưu `access_token` sau khi đăng nhập thành công.
- [ ] Đính `Authorization: Bearer <token>` cho mọi request cần đăng nhập.
- [ ] Xử lý 401 tập trung: xoá token + chuyển về trang đăng nhập.
- [ ] Gọi `POST /logout` khi người dùng đăng xuất, rồi xoá token phía FE.
- [ ] (Tuỳ chọn) Theo dõi `expires_at` để chủ động yêu cầu đăng nhập lại trước khi hết hạn.
