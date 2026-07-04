# Hướng dẫn FE: Upload tệp qua Cloudflare R2

> **Phiên bản: 1.1.0** — Thêm mô tả dọn dẹp object: khi `object_key` không còn
> được tham chiếu bởi entity nghiệp vụ (vd PATCH `avatar_object_key` đổi key
> mới hoặc set `null`), **BE tự xóa object cũ trên R2** ngay sau khi commit DB.
> FE không cần gọi API delete. Xem chi tiết mục 6 và mục 7.
> Thiết kế direct-upload: FE gọi BE để lấy **presigned PUT URL**, FE tự `PUT`
> thẳng lên R2, sau đó gọi lại BE để BE `HEAD` kiểm tra và trả về **URL đọc**
> (presigned GET nếu bucket private). Không streaming qua BE nên không tốn
> băng thông server.

Module upload cung cấp 2 endpoint cho mọi loại object:

| Method | Path | Mục đích |
|---|---|---|
| `POST` | `/api/v1/uploads/presign` | Xin URL upload đã ký (PUT). |
| `POST` | `/api/v1/uploads/confirm` | Xác nhận object đã lên R2 & nhận URL đọc. |

Toàn bộ endpoint yêu cầu `Authorization: Bearer <token>` (đăng nhập). Hiện
hỗ trợ 1 loại `kind`:

- `department_avatar` — ảnh đại diện khoa, dùng cho `departments.avatar_object_key`.

> Tài liệu liên quan: [`FE_DEPARTMENT.md`](./FE_DEPARTMENT.md) (cập nhật
> `avatar_object_key`), [`FE_AUTH_TOKEN.md`](./FE_AUTH_TOKEN.md) (token).

---

## 1. Cấu hình BE (chỉ dành cho backend/admin)

Biến môi trường bắt buộc trong `.env` (xem `.env.example`):

```
R2_ACCOUNT_ID=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET=health-rec-assets
R2_PRESIGN_PUT_TTL=600         # 10 phút cho PUT
R2_PRESIGN_GET_TTL=3600        # 1 giờ cho GET
R2_MAX_UPLOAD_BYTES=15728640   # 15 MB
R2_ALLOWED_CONTENT_TYPES=image/jpeg,image/png,image/webp,application/pdf
R2_PUBLIC_HOST=                # để trống -> private bucket (mặc định)
                               # hoặc assets.example.com nếu muốn dùng public URL
```

---

## 2. Flow tích hợp (FE)

```
┌────────┐  1. presign  ┌──────────┐
│  FE    │ ───────────▶ │   BE     │  -> BE sinh object_key + presigned PUT URL
│        │ ◀─────────── │          │  <- { object_key, url, headers, expires_in }
│        │              └──────────┘
│        │  2. PUT file + headers
│        │ ─────────────────────────────────▶ R2 bucket
│        │
│        │  3. confirm  ┌──────────┐
│        │ ───────────▶ │   BE     │  -> BE HEAD object để chắc chắn tồn tại
│        │ ◀─────────── │          │  <- { object_key, url (presigned GET), expires_in }
└────────┘              └──────────┘
```

Bước 4 — FE lưu `object_key` vào entity tương ứng qua API nghiệp vụ
(vd `PATCH /api/v1/departments/{id}` với `avatar_object_key`).

---

## 3. Xin URL upload — `POST /api/v1/uploads/presign`

### Request body

```jsonc
{
  "kind": "department_avatar",   // loại object (xem mục danh sách kind ở trên)
  "content_type": "image/png",   // mime type — phải nằm trong whitelist
  "size": 524288,                // byte — phải ≤ R2_MAX_UPLOAD_BYTES
  "filename": "cardio.png"       // tùy chọn, chỉ phục vụ log
}
```

### Response — `200 OK`

```jsonc
{
  "status": "success",
  "code": "200",
  "message": "Sinh URL upload thành công.",
  "data": {
    "kind": "department_avatar",
    "object_key": "department/4f1c2a...e8.png",
    "method": "PUT",
    "url": "https://<accountid>.r2.cloudflarestorage.com/health-rec-assets/department/...?...signature...",
    "headers": { "Content-Type": "image/png" },
    "expires_in": 600
  },
  "meta": null
}
```

### Các lỗi có thể gặp

| HTTP | Khi nào | `message` |
|---|---|---|
| **400** | `kind` không được hỗ trợ | "Loại upload không được hỗ trợ." |
| **400** | `content_type` ngoài whitelist | "Định dạng tệp không được phép." |
| **400** | `size ≤ 0` hoặc `size > R2_MAX_UPLOAD_BYTES` | "Tệp vượt quá kích thước cho phép." |
| **401** | Thiếu/invalid token | "Token xác thực không hợp lệ / đã hết hạn." |
| **503** | BE chưa cấu hình R2 | — |

---

## 4. Upload lên R2 (FE thao tác trực tiếp)

Sau khi nhận `data.url` & `data.headers`, FE dùng `fetch`/`axios` PUT file:

```js
const file = input.files[0];           // File chọn từ <input type="file">
const { url, headers } = presigned;

await fetch(url, {
  method: "PUT",
  headers,
  body: file,                          // raw bytes, KHÔNG multipart
});
// status 200 nghĩa là upload thành công.
```

> ⚠️ Phải giữ nguyên `Content-Type` đúng như lúc gọi `presign`. Bỏ header này
> → R2 từ chối vì chữ ký không khớp.
>
> ⚠️ Chỉ PUT **đúng một lần**, không retry vì URL có TTL (`expires_in`).

---

## 5. Xác nhận upload — `POST /api/v1/uploads/confirm`

### Request body

```jsonc
{
  "kind": "department_avatar",
  "object_key": "department/4f1c2a...e8.png",
  "content_type": "image/png"        // tùy chọn
}
```

### Response — `200 OK`

```jsonc
{
  "status": "success",
  "code": "200",
  "message": "Xác nhận upload thành công.",
  "data": {
    "kind": "department_avatar",
    "object_key": "department/4f1c2a...e8.png",
    "url": "https://...presigned-get...",
    "expires_in": 3600
  },
  "meta": null
}
```

- `url` là **presigned GET** có TTL `R2_PRESIGN_GET_TTL` (mặc định 1 giờ).
  Sau khi hết hạn FE phải gọi lại `GET /departments/{id}` để nhận URL mới (BE
  sẽ tự sinh lại từ `avatar_object_key` đã lưu DB).

### Các lỗi có thể gặp

| HTTP | Khi nào | `message` |
|---|---|---|
| **404** | Object không tồn tại trong R2 (FE chưa PUT hoặc sai key) | "Không tìm thấy object trong kho lưu trữ." |
| **404** | `object_key` không đúng định dạng (vd chứa `..`) | "Không tìm thấy object trong kho lưu trữ." |
| **401** | Thiếu/invalid token | "Token xác thực không hợp lệ / đã hết hạn." |
| **503** | R2 chưa cấu hình hoặc tạm mất kết nối | — |

---

## 6. Gắn vào Department

Sau khi có `object_key`, FE gọi `PATCH /api/v1/departments/{id}` để lưu:

```jsonc
// PATCH /api/v1/departments/1
{ "avatar_object_key": "department/4f1c2a...e8.png" }
```

Để **xoá** avatar: gửi `null`.

```jsonc
{ "avatar_object_key": null }
```

> FE không cần gửi `avatar_url` nữa — BE tự sinh URL đọc từ `object_key` khi
> trả response. Xem mục "Lưu ý" trong [`FE_DEPARTMENT.md`](./FE_DEPARTMENT.md).

### BE tự xóa object cũ trên R2 (FE không cần gọi delete)

Upload lần đầu thì không có gì để xóa. Nhưng từ lần thứ 2 trở đi, khi
`object_key` mới thay thế object_key cũ (hoặc set về `null`), BE sẽ:

1. Cập nhật cột `avatar_object_key` trong DB và commit.
2. Ngay sau commit, gọi `boto3.delete_object` trên R2 với key cũ.
3. Nếu xóa R2 lỗi (mất mạng, R2 tạm down): **chỉ log warning**, không
   rollback DB. File orphan có thể dọn sau bằng lifecycle policy của bucket.

FE:

- **Không cần** gọi thêm bất kỳ endpoint nào để xóa avatar cũ.
- **Không cần** lưu URL presigned GET cũ — DB đã clear cache, response kế
  tiếp sẽ dùng URL mới (do `to_dict()` tự derive từ `object_key` mới).
- **Idempotent**: PATCH với cùng `avatar_object_key` đã có sẵn → BE không
  xóa gì cả, an toàn khi user click "Lưu" hai lần.

| Trước PATCH (`avatar_object_key`) | Body gửi | Object cũ trên R2 |
|---|---|---|
| `null` | `department/xyz.png` | giữ nguyên (lần đầu) |
| `department/abc.png` | `department/xyz.png` | **xóa `abc.png`** |
| `department/abc.png` | `abc.png` (giữ nguyên) | giữ nguyên (idempotent) |
| `department/abc.png` | `null` | **xóa `abc.png`** |
| `null` | `null` | giữ nguyên |

Nếu sau này có thêm `kind` mới (vd `doctor_avatar`), cơ chế dọn dẹp tương
tự: trong service của entity tương ứng, snapshot `old_object_key` trước khi
gán, gọi `delete_object(old_object_key)` sau `commit()`, bọc `try/except`
để lỗi R2 không rollback DB.

---

## 7. Ví dụ tích hợp (JS / React)

```js
async function uploadDepartmentAvatar(departmentId, file) {
  // 1) Xin presigned PUT URL.
  const presign = await apiFetch(`/api/v1/uploads/presign`, {
    method: "POST",
    body: JSON.stringify({
      kind: "department_avatar",
      content_type: file.type || "image/png",
      size: file.size,
      filename: file.name,
    }),
  });
  if (!presign) return null;
  const { object_key, url, headers } = presign.data;

  // 2) PUT thẳng lên R2.
  const putRes = await fetch(url, { method: "PUT", headers, body: file });
  if (!putRes.ok) {
    throw new Error(`Upload R2 failed: ${putRes.status}`);
  }

  // 3) BE xác nhận + trả URL đọc.
  const confirm = await apiFetch(`/api/v1/uploads/confirm`, {
    method: "POST",
    body: JSON.stringify({
      kind: "department_avatar",
      object_key,
      content_type: file.type || "image/png",
    }),
  });
  if (!confirm) return null;

  // 4) Lưu object_key vào department.
  const dept = await apiFetch(`/api/v1/departments/${departmentId}`, {
    method: "PATCH",
    body: JSON.stringify({ avatar_object_key: object_key }),
  });
  return dept?.data ?? null;
}
```

---

## 8. Checklist tích hợp

- [ ] Đặt biến môi trường R2 trên BE trước khi go-live; **không commit secret**.
- [ ] Frontend: validate phía client `content_type` & `size` để khỏi gọi
      `presign` khi đã biết sẽ bị 400.
- [ ] Khi nhận `expires_in`, hiển thị đếm ngược hoặc cảnh báo trước khi URL hết hạn.
- [ ] Xử lý lỗi `404` ở `confirm` (object chưa lên R2) → retry upload.
- [ ] Lưu `object_key` (chuỗi) vào form/department, **không** lưu URL có chữ ký.
- [ ] Khi đổi ảnh mới: chỉ cần `PATCH avatar_object_key` — **BE tự xóa object
      cũ trên R2**, FE không gọi thêm API delete.
- [ ] Khi muốn **xoá** ảnh: `PATCH { "avatar_object_key": null }` — BE xóa cả
      object trên R2 lẫn cột DB.
- [ ] Không cần retry khi PATCH trả 200 nhưng BE log warning về xóa R2 —
      orphan file sẽ được dọn bằng lifecycle policy của bucket.

---

## 9. Tóm tắt endpoint

| Method | Path | Permission | Mô tả |
|---|---|---|---|
| `POST` | `/api/v1/uploads/presign` | đăng nhập (bất kỳ role) | Sinh URL upload đã ký. |
| `POST` | `/api/v1/uploads/confirm` | đăng nhập (bất kỳ role) | Xác nhận object đã upload & nhận URL đọc. |

> **Không có endpoint `DELETE` cho object.** Khi `object_key` không còn được
> tham chiếu (vd PATCH `avatar_object_key` đổi key mới hoặc `null`), BE tự
> xóa object cũ trên R2. FE chỉ cần PATCH entity nghiệp vụ như bình thường.

---

## 10. Lịch sử thay đổi

| Phiên bản | Thay đổi |
|---|---|
| **1.1.0** | Bổ sung mô tả dọn dẹp object: BE tự xóa object cũ trên R2 khi `object_key` không còn được tham chiếu (vd PATCH `avatar_object_key` đổi key mới hoặc `null`). FE không cần gọi API delete; lỗi xóa R2 chỉ log warning, không rollback. Cập nhật checklist và bảng case. |
| **1.0.0** | Thiết kế direct-upload với R2: 2 endpoint presign/confirm, hỗ trợ `department_avatar`. Bucket mặc định private (BE ký GET có TTL). |
