# Hướng dẫn FE: Token phiên, gọi API có bảo vệ & Đăng xuất

> **Phiên bản: 1.1.0** — Bổ sung **refresh token (opaque, rotation)**
> + **silent refresh** + **introspection** cho FE. Xem
> [§10 Introspect](#10-introspect-token), [§11 Refresh token](#11-refresh-token),
> [§12 Silent refresh](#12-silent-refresh--tự-làm-mới-trước-khi-hết-hạn),
> [§13 Logout nâng cao](#13-logout-nâng-cao). Xem [Lịch sử thay đổi](#15-lịch-sử-thay-đổi).
>
> Sau khi đăng nhập Google thành công (xem [`FE_GOOGLE_LOGIN.md`](./FE_GOOGLE_LOGIN.md)),
> BE cấp một **access token (JWT)** + **refresh token (opaque)**. FE dùng cặp
> token này để gọi các API cần đăng nhập và tự làm mới access token khi sắp hết hạn
> — không cần đăng nhập lại qua Google mỗi lần token hết hạn.
> Khi đăng xuất, cả hai token đều bị thu hồi.

---

## 1. Vòng đời token

```
Đăng nhập (callback)  ──►  nhận access_token + refresh_token  ──►  gọi API kèm "Authorization: Bearer <access>"
                                                                  │
                                                                  ▼
                                              Access sắp hết hạn → POST /auth/refresh { refresh_token }
                                                                  │
                                                                  ▼
                                              nhận access mới + refresh mới (xoay vòng)
                                                                  │
                                                                  ▼
                                                       Đăng xuất (/logout)
                                                                  │
                                                                  ▼
                              access vào blacklist + refresh bị revoke → mọi request sau bị 401
```

- **Access token (JWT)**: hạn ngắn (mặc định **1 giờ**). Stateless, BE verify bằng chữ ký.
- **Refresh token (opaque)**: hạn dài (mặc định **14 ngày**), BE lưu SHA-256 hash trong DB.
  Mỗi lần refresh → token cũ bị revoke + cấp token mới (rotation).
- **Reuse detection**: nếu FE dùng lại một refresh token đã bị revoke, BE sẽ
  thu hồi MỌI refresh token đang active của user (logout mọi thiết bị) → 401.
- **Logout**: BE blacklist access token hiện tại (jti) + revoke refresh token.
- Token là **stateless (JWT)**: BE không lưu session access, chỉ lưu danh sách access đã revoke
  và refresh token active.

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

FE **BẮT BUỘC** lưu cả 2 token:

- `access_token`: dùng để gọi API (đính vào `Authorization: Bearer`).
- `refresh_token`: dùng để làm mới access khi sắp hết hạn (xem §12).

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
| `/api/v1/auth/logout` | POST | ✅ Bearer | Thu hồi access + refresh token hiện tại (xem §13) |
| `/api/v1/auth/refresh` | POST | ❌ Public | Đổi refresh token lấy access mới + refresh mới (xem §11) |
| `/api/v1/auth/introspect` | POST | ❌ Public | Kiểm tra trạng thái token (xem §10) |

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

### 5.1. Wrapper gọi API tự đính token & tự làm mới khi sắp hết hạn

```js
const API_BASE = "http://localhost:5000";

// ============================================================
// Lưu trữ token
// ============================================================
const TokenStore = {
  getAccess()       { return localStorage.getItem("access_token"); },
  getAccessExp()    { return localStorage.getItem("access_expires_at"); },
  getRefresh()      { return localStorage.getItem("refresh_token"); },
  getRefreshExp()   { return localStorage.getItem("refresh_expires_at"); },

  set(access, refresh, accessExp, refreshExp) {
    localStorage.setItem("access_token", access);
    localStorage.setItem("expires_at", accessExp);
    localStorage.setItem("refresh_token", refresh);
    localStorage.setItem("refresh_expires_at", refreshExp);
  },

  clear() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("expires_at");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("refresh_expires_at");
  },
};

// ============================================================
// Silent refresh — chạy TRƯỚC khi access hết hạn ~60s
// ============================================================
async function silentRefresh() {
  const refresh = TokenStore.getRefresh();
  if (!refresh) return false;

  const res = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });

  if (res.status !== 200) {
    // Refresh token cũng hỏng (hết hạn / bị revoke / reuse-detected)
    // -> bắt buộc đăng nhập lại.
    return false;
  }

  const body = await res.json();
  const d = body.data;
  TokenStore.set(d.access_token, d.refresh_token, d.expires_at, d.refresh_expires_at);
  return true;
}

// True nếu access sắp hết hạn (< 60s). FE chủ động refresh trước.
function shouldRefresh() {
  const exp = TokenStore.getAccessExp();
  if (!exp) return false;
  const expMs = new Date(exp).getTime() - Date.now();
  return expMs < 60 * 1000;
}

// ============================================================
// apiFetch — tự đính Bearer + auto silent refresh + xử lý 401/403
// ============================================================
async function apiFetch(path, options = {}) {
  // 1. Nếu access sắp hết hạn -> refresh trước.
  if (shouldRefresh()) {
    const ok = await silentRefresh();
    if (!ok) {
      TokenStore.clear();
      window.location.href = "/login?reason=refresh_failed";
      return null;
    }
  }

  // 2. Gọi API với Bearer.
  const token = TokenStore.getAccess();
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  let res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  let body = await res.json().catch(() => null);

  // 3. Nhận 401 do access hết hạn -> thử refresh 1 lần rồi retry.
  if (res.status === 401 && TokenStore.getRefresh()) {
    const ok = await silentRefresh();
    if (ok) {
      const retryHeaders = {
        ...headers,
        Authorization: `Bearer ${TokenStore.getAccess()}`,
      };
      res = await fetch(`${API_BASE}${path}`, { ...options, headers: retryHeaders });
      body = await res.json().catch(() => null);
    } else {
      TokenStore.clear();
      window.location.href = "/login?reason=expired";
      return null;
    }
  }

  // 4. Sau khi retry (nếu có) mà vẫn 401 -> logout.
  if (res.status === 401) {
    TokenStore.clear();
    window.location.href = "/login?reason=expired";
    return null;
  }

  // 5. 403 với account_disabled -> logout (xem §10).
  if (res.status === 403 && body?.message?.includes("account_disabled")) {
    TokenStore.clear();
    window.location.href = "/login?reason=disabled";
    return null;
  }

  return body;
}
```

### 5.2. Lưu token sau khi đăng nhập

```js
// Trong trang callback, sau khi POST /google/callback thành công:
if (body.status === "success") {
  const d = body.data;
  TokenStore.set(
    d.access_token,
    d.refresh_token,
    d.expires_at,            // ISO datetime cho access
    d.refresh_expires_at,    // ISO datetime cho refresh
  );
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

### 5.4. Đăng xuất (một thiết bị)

```js
async function logout() {
  // Gửi cả access (qua Bearer) + refresh (trong body) để BE thu hồi cả 2.
  // Kể cả thất bại vẫn xoá token phía FE.
  await apiFetch("/api/v1/auth/logout", {
    method: "POST",
    body: JSON.stringify({
      refresh_token: TokenStore.getRefresh(),
    }),
  });
  TokenStore.clear();
  window.location.href = "/login";
}

// Đăng xuất MỌI thiết bị (vd "Bảo mật > Đăng xuất khỏi tất cả"):
async function logoutAllDevices() {
  await apiFetch("/api/v1/auth/logout", {
    method: "POST",
    body: JSON.stringify({ all_devices: true }),
  });
  TokenStore.clear();
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

// Hook React: tự động silent refresh khi access sắp hết hạn
function useSilentRefresh() {
  useEffect(() => {
    const id = setInterval(async () => {
      if (shouldRefresh()) {
        const ok = await silentRefresh();
        if (!ok) {
          TokenStore.clear();
          window.location.href = "/login?reason=refresh_failed";
        }
      }
    }, 30 * 1000); // check mỗi 30s
    return () => clearInterval(id);
  }, []);
}

// Hoặc refresh khi tab trở nên visible (sau khi user quay lại)
function useRefreshOnFocus() {
  useEffect(() => {
    const onVis = async () => {
      if (document.visibilityState === "visible" && shouldRefresh()) {
        await silentRefresh();
      }
    };
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);
}
```

---

## 7. Cấu hình liên quan (BE)

| Biến môi trường | Mặc định | Ý nghĩa |
|---|---|---|
| `JWT_SECRET` | = `SECRET_KEY` | Khóa ký JWT. **Bắt buộc đổi** ở production. |
| `JWT_ALGORITHM` | `HS256` | Thuật toán ký |
| `JWT_EXPIRES` | `3600` | Hạn access token (giây) = 1 giờ |
| `JWT_REFRESH_EXPIRES` | `1209600` | Hạn refresh token (giây) = 14 ngày |

---

## 8. Lưu ý quan trọng

- **Header phải đúng định dạng:** `Authorization: Bearer <token>` (có chữ `Bearer` và một dấu cách).
- **Refresh token rotation:** mỗi lần `/auth/refresh` thành công, FE nhận token MỚI và phải thay thế token cũ. **Không dùng lại refresh token cũ** — BE phát hiện reuse sẽ thu hồi toàn bộ session của user (xem §11.4).
- **Đổi `JWT_SECRET` sẽ vô hiệu hoá toàn bộ access token đang phát** (mọi người phải đăng nhập lại). Refresh token vẫn còn trong DB nhưng refresh sẽ trả 401 vì BE verify user state.
- **CORS:** FE phải chạy đúng origin trong `CORS_ORIGINS` của BE.
- **Đăng xuất 2 lần:** sau khi logout, gọi lại bất kỳ API bảo vệ nào (kể cả `/logout`) với token cũ đều trả 401 "đã bị thu hồi" — đúng như thiết kế.
- **Nhiều tab:** mỗi tab có instance `TokenStore` riêng. Nếu user logout ở tab A, tab B vẫn còn access cũ. Tab B sẽ tự logout khi gọi API (401) hoặc khi refresh thất bại.

---

## 9. Checklist tích hợp

- [ ] Lưu `access_token` + `refresh_token` sau khi đăng nhập thành công.
- [ ] Đính `Authorization: Bearer <access_token>` cho mọi request cần đăng nhập.
- [ ] Triển khai silent refresh (§12) hoặc auto retry khi 401 (§5.1).
- [ ] Xử lý 401 tập trung: thử refresh 1 lần, fail thì xoá token + về trang login.
- [ ] Phân biệt `errors.refresh_invalid` (hết hạn/revoke) và `errors.refresh_reuse_detected`
      (token bị lộ) — cả hai đều cần login lại.
- [ ] Gọi `POST /logout` với `refresh_token` trong body khi user đăng xuất.
- [ ] (Tuỳ chọn) Cung cấp "Đăng xuất khỏi tất cả thiết bị" với `{ all_devices: true }`.

---

## 10. Introspect token

`POST /api/v1/auth/introspect` — kiểm tra trạng thái một token (theo
[OAuth 2.0 RFC 7662](https://datatracker.ietf.org/doc/html/rfc7662)).
Đây là API **public** (không cần `Authorization`), vì nó chỉ kiểm tra
token không tiết lộ thông tin nhạy cảm.

### 10.1. Request

```jsonc
POST /api/v1/auth/introspect
Content-Type: application/json

{ "token": "<JWT hoặc opaque>" }
```

> **Lưu ý**: hiện tại BE chỉ introspect được **access token** (JWT).
> Refresh token (opaque) là chuỗi random không giải mã được — để kiểm tra
> refresh token, dùng `POST /auth/refresh` (xem §11).

### 10.2. Response — token KHÔNG active

```jsonc
{
  "status": "success",
  "data": {
    "active": false,
    "reason": "expired"  // "expired" | "invalid" | "revoked" | "user_not_found"
  }
}
```

| `reason` | Nghĩa |
|---|---|
| `expired` | Token hết hạn (theo `exp` claim) |
| `invalid` | Chữ ký sai, format sai, hoặc không phải JWT của BE |
| `revoked` | Token bị thu hồi (đã logout) |
| `user_not_found` | Token trỏ vào user không tồn tại |

### 10.3. Response — token active

```jsonc
{
  "status": "success",
  "data": {
    "active": true,
    "jti": "abc123...",
    "sub": "1",
    "type": "access",
    "iat": 1720780800,
    "exp": 1720784400,
    "expires_in": 3600,
    "user": {
      "id": 1,
      "email": "user@gmail.com",
      "full_name": "Nguyen Van A",
      "is_active": true,
      "roles": ["admin"],
      "permissions": ["user:read", "user:manage", ...]
    }
  }
}
```

### 10.4. Khi nào dùng?

- **Kiểm tra nhanh token có còn dùng được không** trước khi render UI nhạy cảm.
- **Reverse proxy / gateway** chặn request có token không active trước khi
  forward tới backend.
- **Debug** khi user báo "token vẫn còn nhưng request 401" — introspect cho biết
  lý do cụ thể (`revoked` / `user_not_found`).
- **KHÔNG dùng để gate UI** — dùng `GET /auth/me` thay thế (có cùng thông tin
  user + đảm bảo token còn dùng được trong request hiện tại).

### 10.5. Ví dụ FE

```js
async function introspect(token) {
  const res = await fetch(`${API_BASE}/api/v1/auth/introspect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
  const body = await res.json();
  return body.data; // { active: bool, reason?, user?, ... }
}

const info = await introspect(localStorage.getItem("access_token"));
if (!info.active) {
  // info.reason: 'expired' | 'invalid' | 'revoked' | 'user_not_found'
  TokenStore.clear();
  window.location.href = "/login?reason=" + info.reason;
}
```

---

## 11. Refresh token

### 11.1. Request

```jsonc
POST /api/v1/auth/refresh
Content-Type: application/json

{ "refresh_token": "<opaque token>" }
```

Endpoint **không cần** `Authorization` header — chính refresh token trong body
đóng vai trò xác thực.

### 11.2. Response thành công (200)

```jsonc
{
  "status": "success",
  "data": {
    "user": { "id": 1, "email": "...", "full_name": "...", ... },
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "Bearer",
    "expires_at": "2026-07-12T11:00:00+00:00",
    "refresh_token": "NEW-refresh-token-different-from-old",
    "refresh_expires_at": "2026-07-26T09:30:00+00:00"
  }
}
```

### 11.3. Response lỗi (401)

| `message` | Nghĩa | Action FE |
|---|---|---|
| `errors.refresh_invalid` | Refresh token sai/hết hạn/bị thu hồi | TokenStore.clear() → /login |
| `errors.refresh_reuse_detected` | Phát hiện tái sử dụng token đã revoke | **Tất cả session của user đã bị logout** (BE đã revoke toàn bộ refresh token + log cảnh báo). Bắt buộc login lại qua Google. |

### 11.4. Rotation policy (BẮT BUỘC tuân thủ)

Mỗi lần `/auth/refresh` thành công, BE cấp refresh token **MỚI** và **revoke**
token cũ. FE phải:

1. **Lưu token mới** thay cho token cũ ngay lập tức.
2. **KHÔNG BAO GIỜ** dùng lại refresh token đã nhận trước đó.

Nếu FE lỡ tay dùng lại token cũ (vd concurrent request, double-click, hay
lưu sai logic) → BE phát hiện reuse → thu hồi MỌI refresh token đang active
của user → user phải login lại qua Google. Đây là cơ chế **defense-in-depth**
chống lộ token: nếu attacker chôm được 1 token, dùng lại lần 2 → BE đóng băng
mọi phiên.

### 11.5. Edge case — Concurrent request

Khi 2 request cùng gọi `/refresh` với cùng refresh_token (vd 2 tab cùng lúc
mount):

- **Request A** đến trước → xoay vòng thành công → trả token mới.
- **Request B** đến sau với token cũ → BE phát hiện reuse → trả 401 reuse-detected
  → B mất phiên.

**Khuyến nghị**: FE chỉ gọi `/refresh` **tuần tự** — dùng mutex / Promise queue
để tránh 2 request song song. Pattern đơn giản: lưu `refreshPromise` ở module
level, nếu có rồi thì `await` thay vì gọi lại.

```js
let refreshPromise = null;

async function silentRefresh() {
  if (refreshPromise) return refreshPromise; // share cùng Promise

  refreshPromise = (async () => {
    try {
      // ... logic gọi /auth/refresh ...
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}
```

### 11.6. Refresh token hết hạn

- `JWT_REFRESH_EXPIRES` mặc định 14 ngày.
- Hết hạn → `POST /refresh` trả 401 `errors.refresh_invalid` → FE bắt buộc login lại qua Google.
- User có thể vào "Bảo mật > Phiên đăng nhập" để xem danh sách thiết bị đang
  đăng nhập (xem §13 logout all-devices).

---

## 12. Silent refresh — tự làm mới trước khi hết hạn

### 12.1. Tại sao cần?

Access token có hạn 1 giờ. Nếu user đang dùng app lúc token hết hạn → request
fail (401) → UX kém (màn hình trắng, mất state).

**Silent refresh**: trước khi access hết hạn ~60s, FE tự gọi `/auth/refresh`
lấy token mới. User không nhận ra.

### 12.2. Khi nào refresh?

| Trigger | Cách |
|---|---|
| **Trước mỗi request** nếu `now + 60s > expires_at` | Trong wrapper `apiFetch` (xem §5.1) |
| **Định kỳ** mỗi 30s | `setInterval` ở root component |
| **Khi tab trở nên visible** | Hook `useRefreshOnFocus` (§6) |
| **Sau khi nhận 401** | Auto retry 1 lần trong `apiFetch` (§5.1) |

Khuyến nghị kết hợp **3 trigger đầu** + **auto retry khi 401** = an toàn nhất.

### 12.3. Khoảng đệm (refresh skew)

Không refresh sát giờ (`expires_at - 0`) vì clock skew có thể làm request
fail. Khoảng đệm **60s** là hợp lý:

- Access TTL: 3600s (1h)
- Refresh khi: còn lại < 60s → refresh ở phút thứ 59
- Refresh latency: ~100-300ms → đủ an toàn

### 12.4. Ví dụ — Singleton refresh

```js
// auth.ts (module-level singleton)
let refreshInFlight = null;
let refreshSubscribers = [];

function notifyRefreshed(newTokens) {
  refreshSubscribers.forEach((cb) => cb(newTokens));
  refreshSubscribers = [];
}

export async function silentRefresh() {
  const refresh = TokenStore.getRefresh();
  if (!refresh) return null;

  // Có 1 request đang refresh rồi -> chờ.
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
      });

      if (res.status !== 200) return null;

      const body = await res.json();
      const d = body.data;
      TokenStore.set(d.access_token, d.refresh_token, d.expires_at, d.refresh_expires_at);
      notifyRefreshed({
        access: d.access_token,
        refresh: d.refresh_token,
        accessExp: d.expires_at,
        refreshExp: d.refresh_expires_at,
      });
      return TokenStore.getAccess();
    } catch (e) {
      return null;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

// apiFetch tự động refresh + retry
async function apiFetch(path, options = {}) {
  if (shouldRefresh()) {
    const access = await silentRefresh();
    if (!access) {
      TokenStore.clear();
      window.location.href = "/login?reason=refresh_failed";
      return null;
    }
  }
  // ... gọi fetch như bình thường, attach Bearer ...
}
```

---

## 13. Logout nâng cao

### 13.1. Logout 1 thiết bị

```jsonc
POST /api/v1/auth/logout
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "refresh_token": "<optional - refresh token hiện tại>"  // optional
}
```

- Cần `Authorization: Bearer <access>` để BE xác thực (qua decorator `require_auth`).
- Nếu body có `refresh_token` → BE cũng revoke refresh token này.
- Nếu body không có → BE chỉ blacklist access token. Refresh token vẫn active
  cho đến khi hết hạn (14 ngày). Nếu attacker chôm được refresh token → vẫn
  refresh được → **luôn gửi `refresh_token` khi logout**.

### 13.2. Logout mọi thiết bị (all devices)

```jsonc
POST /api/v1/auth/logout
Authorization: Bearer <access_token>
Content-Type: application/json

{ "all_devices": true }
```

- BE thu hồi MỌI refresh token đang active của user.
- Access token hiện tại vẫn dùng được đến khi hết hạn (TTL ngắn), nhưng
  không refresh được nữa → phải login lại qua Google ở lần hết hạn kế tiếp.
- **Không** blacklist access token vì có thể ảnh hưởng user hợp lệ đang dùng.
- Dùng cho chức năng "Bảo mật > Đăng xuất khỏi tất cả thiết bị".

### 13.3. Response

```jsonc
{ "status": "success", "message": "Đăng xuất thành công.", "data": null, "meta": null }
```

### 13.4. Flow đề xuất FE

```ts
// 1. User bấm "Đăng xuất"
async function onLogoutClick() {
  await logout();           // gọi §13.1
  navigate("/login");
}

// 2. User bấm "Đăng xuất khỏi tất cả thiết bị"
async function onLogoutAllClick() {
  if (!confirm("Đăng xuất khỏi tất cả thiết bị?")) return;
  await logoutAllDevices(); // gọi §13.2
  navigate("/login");
}
```

### 13.5. Tự động logout khi bị admin disable

Khi admin `PATCH /admin/users/<id>/status { is_active: false }`:
- Access token hiện tại: lần request kế tiếp → 403 `errors.account_disabled`
  (xem §4 lỗi 403 trong RBAC §11.5).
- Refresh token: lần refresh kế tiếp → 401 `errors.refresh_invalid`.

FE xử lý 2 case này trong wrapper `apiFetch` (§5.1) bằng cách clear TokenStore
và redirect về `/login?reason=disabled`.

---

## 14. Mapping các `message` key — FE xử lý tập trung

| Message key | HTTP | Ý nghĩa | Action FE |
|---|---|---|---|
| `errors.token_missing` | 401 | Không gửi Authorization header | Clear token → /login |
| `errors.token_invalid` | 401 | Chữ ký sai, format sai | Clear token → /login |
| `errors.token_expired` | 401 | Access token hết hạn | Thử refresh 1 lần, fail thì clear → /login |
| `errors.token_revoked` | 401 | Token đã bị thu hồi (logout) | Clear token → /login |
| `errors.account_disabled` | 403 | User bị admin disable | Clear token → /login?reason=disabled |
| `errors.refresh_invalid` | 401 | Refresh token sai/hết hạn/revoke | Clear token → /login |
| `errors.refresh_reuse_detected` | 401 | Tái sử dụng refresh token — bị logout mọi thiết bị | Clear token → /login (hiển thị thông báo "Phiên đăng nhập đã bị đóng do phát hiện hoạt động bất thường") |

---

## 15. Lịch sử thay đổi

| Phiên bản | Thay đổi |
|---|---|
| **1.1.0** | Thêm **refresh token (opaque, rotation)**. Endpoint mới `POST /auth/refresh`. Cập nhật `POST /auth/google/callback` trả `refresh_token` + `refresh_expires_at`. Cập nhật `POST /auth/logout` nhận body `{ refresh_token, all_devices }`. Endpoint `POST /auth/introspect` đã có sẵn (RFC 7662) — bổ sung tài liệu §10. Migration `8b9c0d1e2f3a` thêm bảng `refresh_tokens`. |
| **1.0.0** | Tài liệu đầu: access token (JWT), gọi API có bảo vệ, đăng xuất. |
