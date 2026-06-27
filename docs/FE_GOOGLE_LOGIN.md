# Hướng dẫn FE tích hợp Đăng nhập Google

Tài liệu này mô tả cách Frontend (FE) tích hợp chức năng đăng nhập Google với
Backend (BE) của hệ thống. Luồng dùng OAuth2 Authorization Code, **FE tự quản lý
`state`** để chống CSRF.

---

## 1. Tổng quan luồng

```
┌────┐                                                   ┌────┐        ┌────────┐
│ FE │                                                   │ BE │        │ Google │
└─┬──┘                                                   └─┬──┘        └───┬────┘
  │ 1. Sinh `state` ngẫu nhiên, lưu vào sessionStorage     │               │
  │                                                        │               │
  │ 2. window.location = /api/v1/auth/google/url?state=…   │               │
  │───────────────────────────────────────────────────────>               │
  │                          3. BE lưu state, trả 302 redirect ──────────────>
  │ 4. Trình duyệt tới trang đăng nhập Google                              │
  │<───────────────────────────────────────────────────────────────────────
  │ 5. User đăng nhập & đồng ý                                             │
  │       6. Google redirect về GOOGLE_REDIRECT_URI?code=…&state=… ──────────
  │<───────────────────────────────────────────────────────────────────────
  │ 7. FE so khớp `state` nhận về với state đã lưu (chống CSRF)            │
  │                                                        │               │
  │ 8. POST /api/v1/auth/google/callback {code, state}     │               │
  │───────────────────────────────────────────────────────>               │
  │                          9. BE verify state + đổi code lấy token ────────>
  │                       10. BE trả về thông tin user (JSON chuẩn hóa)    │
  │<───────────────────────────────────────────────────────                │
```

> **Quan trọng:** Bước 2 phải dùng **điều hướng top-level** (`window.location.href`),
> KHÔNG dùng `fetch()`/`axios` — vì BE trả về 302 redirect sang Google, gọi bằng
> fetch sẽ bị chặn CORS.

---

## 2. Cấu hình cần biết

| Mục | Giá trị mặc định (dev) | Ghi chú |
|---|---|---|
| Base URL của BE | `http://localhost:5000` | |
| `GOOGLE_REDIRECT_URI` | `http://localhost:3000/auth/google/callback` | URL **trang FE** xử lý callback. Phải khớp **tuyệt đối** với khai báo trên Google Cloud Console. |
| CORS origin được phép | `http://localhost:3000` | FE phải chạy đúng origin này (xem `CORS_ORIGINS`). |
| Hạn dùng của `state` | 600 giây (10 phút) | Quá hạn phải bắt đầu lại từ đầu. |

`state` là chuỗi 1 lần dùng (single-use): mỗi lần login phải sinh state mới.

---

## 3. API tham chiếu

### 3.1. Bắt đầu đăng nhập — `GET /api/v1/auth/google/url`

Chuyển hướng người dùng tới Google.

| | |
|---|---|
| Method | `GET` |
| Query param | `state` (bắt buộc, độ dài 8–128 ký tự) |
| Phản hồi | **302** redirect tới trang đăng nhập Google |

Lỗi nếu thiếu/không hợp lệ `state` (gọi trực tiếp, không qua redirect trình duyệt):

```json
{ "status": "error", "code": "422", "message": "Validation failed.",
  "data": { "state": "required" }, "meta": null }
```

### 3.2. Hoàn tất đăng nhập — `POST /api/v1/auth/google/callback`

| | |
|---|---|
| Method | `POST` |
| Body (JSON) | `{ "authorization_code": "...", "state": "..." }` |
| Header gợi ý | `Content-Type: application/json` |

**Thành công (200):**

```json
{
  "status": "success",
  "code": "200",
  "message": "Đăng nhập thành công.",
  "data": {
    "user": {
      "id": 1,
      "email": "user@gmail.com",
      "full_name": "Nguyen Van A",
      "picture": "https://...",
      "email_verified": true,
      "last_login_at": "2026-06-27T09:00:00+00:00"
    }
  },
  "meta": null
}
```

**Các lỗi thường gặp:**

| HTTP | `code` | Khi nào | message (vi) |
|---|---|---|---|
| 422 | `"422"` | Thiếu `authorization_code` hoặc `state` | Dữ liệu không hợp lệ. |
| 401 | `"401"` | `state` sai/hết hạn/đã dùng | State đăng nhập không hợp lệ hoặc đã hết hạn. Vui lòng thử lại. |
| 401 | `"401"` | `code` của Google sai/hết hạn | Mã ủy quyền của Google không hợp lệ hoặc đã hết hạn. |
| 429 | `"429"` | Gọi quá nhiều lần | Quá nhiều yêu cầu. Vui lòng thử lại sau. |
| 500 | `"500"` | BE chưa cấu hình Google | Đăng nhập Google chưa được cấu hình trên máy chủ. |

> Endpoint callback bị giới hạn ~10 request/phút mỗi IP. Khi bị chặn (429) sẽ có
> header `Retry-After` (số giây nên chờ).

---

## 4. Định dạng response chung

Mọi response của API đều có cấu trúc thống nhất:

```jsonc
{
  "status": "success" | "error",
  "code": "string",              // mã trạng thái dạng chuỗi
  "message": "string",
  "data": {} | [] | null,        // dữ liệu hoặc chi tiết lỗi
  "meta": { "page": 0, "size": 0, "totalPage": 0 } | null
}
```

FE nên kiểm tra `status` (hoặc HTTP status code) để phân nhánh xử lý.

### Đa ngôn ngữ
- Thêm `?lang=vi` / `?lang=en` vào URL, hoặc gửi header `Accept-Language: vi`.
- `message` trong response sẽ trả về đúng ngôn ngữ tương ứng.

---

## 5. Triển khai FE (ví dụ JavaScript thuần)

### 5.1. Trang Login — bấm "Đăng nhập với Google"

```js
const API_BASE = "http://localhost:5000";

// Sinh chuỗi state ngẫu nhiên đủ dài.
function generateState() {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

function loginWithGoogle() {
  const state = generateState();
  // Lưu state để so khớp khi Google trả về (chống CSRF).
  sessionStorage.setItem("oauth_state", state);

  // Điều hướng top-level (KHÔNG dùng fetch) — BE sẽ 302 sang Google.
  window.location.href =
    `${API_BASE}/api/v1/auth/google/url?state=${encodeURIComponent(state)}`;
}

// Gắn vào nút bấm
document.getElementById("btn-google-login")
  .addEventListener("click", loginWithGoogle);
```

### 5.2. Trang Callback — tại `GOOGLE_REDIRECT_URI`

Đây là trang FE (vd route `/auth/google/callback`) mà Google redirect về kèm
`?code=...&state=...`.

```js
const API_BASE = "http://localhost:5000";

async function handleGoogleCallback() {
  const params = new URLSearchParams(window.location.search);
  const code = params.get("code");
  const returnedState = params.get("state");
  const error = params.get("error"); // user từ chối cấp quyền

  if (error) {
    showError("Bạn đã hủy đăng nhập Google.");
    return;
  }

  // 1) So khớp state (chống CSRF) — bắt buộc.
  const savedState = sessionStorage.getItem("oauth_state");
  sessionStorage.removeItem("oauth_state");
  if (!returnedState || returnedState !== savedState) {
    showError("State không hợp lệ. Vui lòng đăng nhập lại.");
    return;
  }

  // 2) Gửi code + state lên BE để hoàn tất đăng nhập.
  try {
    const res = await fetch(`${API_BASE}/api/v1/auth/google/callback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // credentials: "include", // bật nếu BE dùng cookie/session
      body: JSON.stringify({ authorization_code: code, state: returnedState }),
    });

    const body = await res.json();

    if (body.status === "success") {
      const user = body.data.user;
      // TODO: lưu thông tin user, điều hướng vào trang chính.
      console.log("Đăng nhập thành công:", user);
      window.location.href = "/";
    } else {
      // body.message đã được dịch theo ngôn ngữ request.
      showError(body.message);
    }
  } catch (e) {
    showError("Không kết nối được máy chủ. Vui lòng thử lại.");
  }
}

function showError(msg) {
  // TODO: hiển thị thông báo lỗi trên UI
  alert(msg);
}

handleGoogleCallback();
```

---

## 6. Ví dụ với React (tóm tắt)

```jsx
// LoginButton.jsx
function LoginButton() {
  const onClick = () => {
    const state = generateState();
    sessionStorage.setItem("oauth_state", state);
    window.location.href =
      `${API_BASE}/api/v1/auth/google/url?state=${encodeURIComponent(state)}`;
  };
  return <button onClick={onClick}>Đăng nhập với Google</button>;
}

// GoogleCallback.jsx — đặt tại route khớp GOOGLE_REDIRECT_URI
function GoogleCallback() {
  useEffect(() => { handleGoogleCallback(); }, []);
  return <p>Đang xử lý đăng nhập…</p>;
}
```

---

## 7. Checklist tích hợp

- [ ] FE chạy đúng origin có trong `CORS_ORIGINS` của BE (mặc định `http://localhost:3000`).
- [ ] Route callback của FE khớp **tuyệt đối** với `GOOGLE_REDIRECT_URI` và với khai báo trên Google Cloud Console.
- [ ] Sinh `state` mới mỗi lần login, lưu vào `sessionStorage`.
- [ ] Dùng `window.location.href` để gọi API `/google/url` (không dùng fetch).
- [ ] So khớp `state` trả về trước khi gọi `/google/callback`.
- [ ] Xử lý đủ các nhánh lỗi (422 / 401 / 429 / 500) theo `status` và `message`.
- [ ] Hoàn tất trong vòng 10 phút (hạn của `state`).
```
