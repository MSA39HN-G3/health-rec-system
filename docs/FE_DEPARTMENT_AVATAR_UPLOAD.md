# Hướng dẫn FE: Cập nhật ảnh đại diện khoa (end-to-end)

> **Phiên bản: 1.2.0** — Mô tả hành vi dọn dẹp avatar cũ: khi PATCH
> `avatar_object_key` đổi key mới hoặc set về `null`, BE tự xóa object cũ
> trên R2 sau khi commit DB. FE không cần gọi thêm API delete. PATCH
> idempotent (gửi lặp lại cùng key không xóa nhầm). Phiên bản 1.1.0 (hook
> TS) và 1.0.0 (flow) giữ nguyên.
>
> Tài liệu gốc (nếu cần chi tiết từng bước):
> - [`FE_UPLOADS.md`](./FE_UPLOADS.md) — API upload R2 (presign/confirm).
> - [`FE_DEPARTMENT.md`](./FE_DEPARTMENT.md) — CRUD department + cập nhật partial.
> - [`FE_AUTH_TOKEN.md`](./FE_AUTH_TOKEN.md) — lấy `Authorization` header.
>
> Đối tượng: React/JS. Có 1 ví dụ hoàn chỉnh ở cuối tài liệu.

---

## 1. Tóm tắt endpoint

| Method | Path | Cần `Bearer`? | Permission | Mục đích trong luồng avatar |
|---|---|---|---|---|
| `POST` | `/api/v1/uploads/presign` | ✅ | đã đăng nhập | Xin URL đã ký để PUT file. |
| `PUT`  | URL trả về ở trên (R2, **không qua BE**) | ❌ | — | FE upload trực tiếp lên R2. |
| `POST` | `/api/v1/uploads/confirm` | ✅ | đã đăng nhập | BE HEAD kiểm tra đã có file + trả URL đọc. |
| `PATCH`| `/api/v1/departments/{id}` | ✅ | `department:manage` | Gắn `object_key` vào khoa. |

> Tất cả endpoint JSON đều trả theo envelope chung của dự án:
> `{ status, code, message, data, meta }` — truy cập `data` để lấy payload.

---

## 2. Đường tổng quan

```
┌────────┐  1. presign  ┌──────────┐
│  FE    │ ───────────▶ │   BE     │ → { object_key, url (signed PUT), headers }
│        │ ◀─────────── │          │
│        │  2. PUT file + headers
│        │ ────────────────────────▶ R2
│        │  3. confirm  ┌──────────┐
│        │ ───────────▶ │   BE     │ → { object_key, url (signed GET, TTL 1h) }
│        │ ◀─────────── │          │
│        │  4. PATCH department
│        │ ───────────▶ │   BE     │ → { departments: avatar_object_key/avatar_url }
└────────┘              └──────────┘
```

Mỗi bước có thể thất bại → FE cần hiển thị toast / disable nút save tương ứng.

---

## 3. Bước 1 — Xin URL upload

### Request

```http
POST /api/v1/uploads/presign HTTP/1.1
Authorization: Bearer <token>
Content-Type: application/json
Accept: application/json
Accept-Language: vi

{
  "kind": "department_avatar",
  "content_type": "image/png",
  "size": 524288,
  "filename": "cardio.png"      // tuỳ chọn
}
```

| Trường | Bắt buộc | Ý nghĩa |
|---|:---:|---|
| `kind` | ✅ | Hằng số `department_avatar` (giá trị duy nhất hiện được hỗ trợ). |
| `content_type` | ✅ | MIME trong whitelist: `image/jpeg`, `image/png`, `image/webp`, `application/pdf`. |
| `size` | ✅ | Byte. Phải `> 0` và `≤ R2_MAX_UPLOAD_BYTES` (mặc định 15 728 640 = 15 MB). |
| `filename` | ❌ | Chỉ phục vụ log BE. |

### Response — `200 OK`

```json
{
  "status": "success",
  "code": "200",
  "message": "Sinh URL upload thành công.",
  "data": {
    "kind": "department_avatar",
    "object_key": "department/4f1c2ab9...e8.png",
    "method": "PUT",
    "url": "https://<account>.r2.cloudflarestorage.com/health-rec-assets/department/<key>?X-Amz-...=...",
    "headers": { "Content-Type": "image/png" },
    "expires_in": 600
  },
  "meta": null
}
```

> ⚠️ **Bắt buộc phải lưu `data.object_key`** — đây là chìa khóa để gắn vào
> department ở bước 4. Presigned `url` chỉ sống `expires_in` giây (mặc định
> 600s = 10 phút).

### Lỗi có thể gặp

| HTTP | Mã `data` | Gợi ý xử lý FE |
|---|---|---|
| `400` | `errors.upload_kind_unsupported` | Toast "Loại upload không được hỗ trợ." |
| `400` | `errors.upload_content_type_unsupported` | Validate client trước khi gọi API. |
| `400` | `errors.upload_too_large` | Validate client trước khi gọi API. |
| `401` | `errors.auth_unauthorized` | Đăng nhập lại. |
| `503` | — | Thử lại sau, BE chưa cấu hình R2. |

---

## 4. Bước 2 — Upload trực tiếp lên R2

Dùng `fetch` (browser/node-fetch) hoặc `axios` PUT raw bytes:

```js
await fetch(presignData.url, {
  method: "PUT",
  headers: presignData.headers,     // { "Content-Type": "image/png" }
  body: file,                       // File / Blob, KHÔNG multipart
});
// status 200 = upload xong.
```

> ⚠️ **Không retry**: presigned URL chỉ dùng được 1 lần cho PUT trong TTL.
> Nếu `fetch` trả lỗi mạng → xin URL mới (bước 1) rồi PUT lại.
>
> ⚠️ **Giữ nguyên `Content-Type`** như lúc gọi `presign`. Bỏ qua → R2 sẽ
> từ chối vì chữ ký bất khớp (`403 SignatureDoesNotMatch`).
>
> File được upload hoàn toàn ngoài BE — không cần gửi `Authorization`.

### Lỗi có thể gặp

| HTTP/R2 | Nguyên nhân | Gợi ý FE |
|---|---|---|
| `403 SignatureDoesNotMatch` | Sai/thiếu header `Content-Type`. | Lấy đúng `data.headers`. |
| `403 RequestExpired` | URL hết hạn (>10 phút). | Xin `presign` mới + PUT lại. |
| `0` / `NetworkError` | Mạng lag / CORS. | Retry 1 lần với cùng URL. |

---

## 5. Bước 3 — Xác nhận & nhận URL đọc

### Request

```http
POST /api/v1/uploads/confirm HTTP/1.1
Authorization: Bearer <token>
Content-Type: application/json

{
  "kind": "department_avatar",
  "object_key": "department/4f1c2ab9...e8.png",
  "content_type": "image/png"
}
```

### Response — `200 OK`

```json
{
  "status": "success",
  "code": "200",
  "message": "Xác nhận upload thành công.",
  "data": {
    "kind": "department_avatar",
    "object_key": "department/4f1c2ab9...e8.png",
    "url": "https://...presigned-get...",
    "expires_in": 3600
  }
}
```

- `url` là **presigned GET** có TTL `R2_PRESIGN_GET_TTL` (mặc định 3600s = 1 giờ)
  khi bucket đặt private. Nếu BE cấu hình `R2_PUBLIC_HOST` thì `url` là URL
  public không ký — dùng trực tiếp.
- **Đừng lưu `url` này vĩnh viễn.** Sau khi hết hạn, FE chỉ cần gọi lại
  `GET /api/v1/departments/{id}`; BE tự derive URL mới từ `object_key`.

### Lỗi có thể gặp

| HTTP | Khi nào | Gợi ý FE |
|---|---|---|
| `404` `errors.upload_object_not_found` | Bước 2 chưa PUT xong, hoặc `object_key` sai shape. | Retry `confirm` sau khi đợi PUT xong. |
| `401` | Token hết hạn. | Refresh token rồi gọi lại. |

---

## 6. Bước 4 — Gắn avatar vào Department

### Request

```http
PATCH /api/v1/departments/{id} HTTP/1.1
Authorization: Bearer <token>
Content-Type: application/json

{ "avatar_object_key": "department/4f1c2ab9...e8.png" }
```

- **Xoá avatar**: gửi `null`:

```json
{ "avatar_object_key": null }
```

> FE không cần gửi `avatar_url` — BE tự derive khi trả response.

### Response — `200 OK` (data chứa department)

```json
{
  "status": "success",
  "code": "200",
  "message": "Cập nhật khoa thành công.",
  "data": {
    "id": 1,
    "code": "CK-001",
    "name": "Tim mạch",
    "avatar_object_key": "department/4f1c2ab9...e8.png",
    "avatar_url": "https://...presigned-get...",
    ...
  }
}
```

> ⚠️ **Cache**: mỗi lần gọi PATCH `avatar_object_key`, BE tự **xoá cache URL**
> trong DB và `to_dict()` lần kế tiếp sẽ ký lại presigned GET (TTL mới 1 giờ).

### Lỗi có thể gặp

| HTTP | Mã `data` | Khi nào |
|---|---|---|
| `403` | `errors.permission_denied` | User không có `department:manage`. |
| `404` | `errors.department_not_found` | Sai `id` / khoa đã xoá. |
| `400` | — | Validation body (vd `avatar_object_key` quá 512 ký tự). |

### Dọn dẹp avatar cũ trên R2 (BE tự làm — FE không cần gọi delete)

Khi `PATCH avatar_object_key` đổi sang key mới **hoặc** set về `null`, BE tự
xoá object cũ trên R2 ngay sau khi commit DB thành công. FE:

- **Không cần** gọi thêm endpoint nào để xóa avatar cũ.
- **Không cần** giữ URL presigned GET cũ — DB đã được xoá, lần render sau
  sẽ dùng URL mới.
- Trường hợp R2 tạm mất kết nối khi xóa: BE chỉ log warning, **không rollback**
  DB. File orphan trên R2 có thể dọn sau bằng lifecycle policy của bucket.

> PATCH idempotent: nếu FE gửi lặp lại cùng `avatar_object_key` đã có sẵn,
> BE **không xóa** gì cả (an toàn khi user click "Lưu" hai lần).

| Trước PATCH (`avatar_object_key`) | Body gửi | Object trên R2 |
|---|---|---|
| `null` | `department/xyz.png` | tạo `xyz.png` (không xóa gì) |
| `department/abc.png` | `department/xyz.png` | xóa `abc.png`, tạo `xyz.png` |
| `department/abc.png` | `abc.png` (giữ nguyên) | giữ nguyên (idempotent) |
| `department/abc.png` | `null` | xóa `abc.png` |
| `null` | `null` | giữ nguyên |

---

## 7. Hook & component React (drop-in)

Mục này cho bạn 3 file có thể copy nguyên xi vào project FE (TypeScript). Tất cả
phụ thuộc vào **một helper duy nhất** `apiFetch` — xem [`FE_AUTH_TOKEN.md`](./FE_AUTH_TOKEN.md).
Hook tự xử lý: validate client, presign, PUT trực tiếp lên R2, confirm, PATCH
department, fallback khi URL hết hạn, và trả về state để component bind.

### 7.1. `useAvatarUpload.ts` — hook chính

```ts
import { useCallback, useState } from "react";

// ====== Types theo envelope chung của BE ======
type ApiEnvelope<T> = {
  status: "success" | "error";
  code: string;
  message: string | null;
  data: T;
  meta: unknown;
};

type PresignResp = {
  kind: "department_avatar";
  object_key: string;
  method: "PUT";
  url: string;
  headers: Record<string, string>;
  expires_in: number;
};

type ConfirmResp = {
  kind: "department_avatar";
  object_key: string;
  url: string;
  expires_in: number;
};

type Department = {
  id: number;
  code: string;
  name: string;
  avatar_object_key: string | null;
  avatar_url: string | null;
  // ... các field khác không quan trọng với upload
};

// ====== Helper: gọi BE với Authorization ======
declare const apiFetch: <T = unknown>(
  path: string,
  init?: { method?: string; body?: BodyInit | null }
) => Promise<ApiEnvelope<T>>;

// ====== Ràng buộc khớp với app/config.py ======
const ALLOWED_CT = ["image/jpeg", "image/png", "image/webp"] as const;
const MAX_BYTES = 15 * 1024 * 1024; // R2_MAX_UPLOAD_BYTES mặc định

export type UploadStatus =
  | "idle"
  | "presigning"
  | "uploading"
  | "confirming"
  | "saving"
  | "done"
  | "error";

export class UploadAvatarError extends Error {
  readonly step: UploadStatus;
  readonly http?: number;
  readonly code?: string;
  constructor(step: UploadStatus, message: string, http?: number, code?: string) {
    super(message);
    this.step = step;
    this.http = http;
    this.code = code;
  }
}

function validate(file: File) {
  if (file.size <= 0 || file.size > MAX_BYTES) {
    throw new UploadAvatarError("presigning", "Tệp vượt quá 15 MB hoặc rỗng.");
  }
  const ct = (file.type || "").toLowerCase();
  if (!ALLOWED_CT.includes(ct as (typeof ALLOWED_CT)[number])) {
    throw new UploadAvatarError(
      "presigning",
      "Chỉ chấp nhận JPG, PNG, WEBP."
    );
  }
}

async function putToR2(url: string, headers: Record<string, string>, file: File) {
  // PUT raw bytes — KHÔNG multipart. Retry 1 lần khi mạng lag (NetworkError).
  // Không retry khi server trả >= 400 (chữ ký đã cháy).
  let res: Response;
  try {
    res = await fetch(url, { method: "PUT", headers, body: file });
  } catch {
    try {
      res = await fetch(url, { method: "PUT", headers, body: file });
    } catch (e) {
      throw new UploadAvatarError("uploading", "Mất kết nối tới R2.");
    }
  }
  if (!res.ok) {
    throw new UploadAvatarError(
      "uploading",
      `R2 từ chối (${res.status}).`,
      res.status
    );
  }
}

export function useAvatarUpload(departmentId: number) {
  const [status, setStatus] = useState<UploadStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [department, setDepartment] = useState<Department | null>(null);

  const reset = useCallback(() => {
    setStatus("idle");
    setError(null);
  }, []);

  const upload = useCallback(
    async (file: File) => {
      setError(null);
      try {
        validate(file);

        // 1) presign
        setStatus("presigning");
        const p = await apiFetch<PresignResp>("/api/v1/uploads/presign", {
          method: "POST",
          body: JSON.stringify({
            kind: "department_avatar",
            content_type: file.type,
            size: file.size,
            filename: file.name,
          }),
        });

        // 2) PUT thẳng lên R2
        setStatus("uploading");
        await putToR2(p.data.url, p.data.headers, file);

        // 3) confirm
        setStatus("confirming");
        await apiFetch<ConfirmResp>("/api/v1/uploads/confirm", {
          method: "POST",
          body: JSON.stringify({
            kind: "department_avatar",
            object_key: p.data.object_key,
            content_type: file.type,
          }),
        });

        // 4) PATCH department
        setStatus("saving");
        const d = await apiFetch<Department>(
          `/api/v1/departments/${departmentId}`,
          {
            method: "PATCH",
            body: JSON.stringify({ avatar_object_key: p.data.object_key }),
          }
        );
        setDepartment(d.data);
        setStatus("done");
        return d.data;
      } catch (e) {
        const msg =
          e instanceof UploadAvatarError
            ? e.message
            : e instanceof Error
            ? e.message
            : "Upload thất bại.";
        setError(msg);
        setStatus("error");
        throw e;
      }
    },
    [departmentId]
  );

  return { upload, status, error, department, reset };
}
```

### 7.2. `useDepartment.ts` — tự lấy lại URL khi ảnh hết hạn

`avatar_url` chỉ sống `R2_PRESIGN_GET_TTL` (mặc định 3600s). Hook này gọi lại
`GET /api/v1/departments/{id}` khi user click "Tải lại ảnh" hoặc khi `<img>`
vỡ (404 từ R2 vì URL hết hạn).

```tsx
import { useEffect, useState } from "react";

type Department = {
  id: number;
  avatar_object_key: string | null;
  avatar_url: string | null;
};

declare const apiFetch: <T = unknown>(
  path: string,
  init?: { method?: string; body?: BodyInit | null }
) => Promise<{ data: T }>;

export function useDepartment(departmentId: number) {
  const [data, setData] = useState<Department | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await apiFetch<Department>(`/api/v1/departments/${departmentId}`);
      setData(r.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Tải khoa thất bại.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [departmentId]);

  return { data, loading, error, refetch };
}
```

### 7.3. Component sử dụng cả hai hook

```tsx
import { useRef } from "react";
import {
  useAvatarUpload,
  UploadAvatarError,
} from "./useAvatarUpload";
import { useDepartment } from "./useDepartment";

const STATUS_LABEL: Record<string, string> = {
  idle: "Chọn ảnh",
  presigning: "Đang xin URL...",
  uploading: "Đang tải lên R2...",
  confirming: "Đang xác nhận...",
  saving: "Đang lưu...",
  done: "Xong",
};

export function DepartmentAvatarCard({ departmentId }: { departmentId: number }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const dept = useDepartment(departmentId);
  const upload = useAvatarUpload(departmentId);

  const busy =
    upload.status !== "idle" &&
    upload.status !== "done" &&
    upload.status !== "error";

  async function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      await upload.upload(file);
      await dept.refetch(); // lấy lại avatar_url mới
    } catch (e) {
      // Lỗi đã có trong upload.error. Log thêm step để debug.
      if (e instanceof UploadAvatarError) {
        console.error("Upload lỗi tại bước:", e.step, e.http);
      }
    } finally {
      // Cho phép chọn lại cùng 1 file nếu muốn retry
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div>
      <img
        src={dept.data?.avatar_url ?? "/placeholder-dept.png"}
        alt={dept.data?.name ?? ""}
        width={96}
        height={96}
        onError={() => {
          // URL hết hạn hoặc R2 lỗi — xin lại URL mới 1 lần.
          void dept.refetch();
        }}
      />

      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        disabled={busy}
        onChange={onPick}
      />

      <p aria-live="polite">
        {busy ? STATUS_LABEL[upload.status] : "Sẵn sàng"}
      </p>

      {upload.error && (
        <p role="alert" style={{ color: "crimson" }}>
          {upload.error}
        </p>
      )}
    </div>
  );
}
```

### 7.4. Bảng map trạng thái → UI

| `status`        | Nhãn tiếng Việt    | Spinner | Disable nút | Hành động cho phép |
|-----------------|--------------------|:------:|:-----------:|---------------------|
| `idle`          | (ẩn)               |   -    |     no      | chọn file           |
| `presigning`    | Đang xin URL...    |   ✓    |     yes     | -                   |
| `uploading`     | Đang tải lên R2... |   ✓    |     yes     | -                   |
| `confirming`    | Đang xác nhận...   |   ✓    |     yes     | -                   |
| `saving`        | Đang lưu...        |   ✓    |     yes     | -                   |
| `done`          | Xong               |   -    |     no      | chọn file mới       |
| `error`         | (xem `upload.error`)|  -    |     no      | chọn file mới       |

### 7.5. Bảng map lỗi từ BE → thông báo user

| Bước thất bại | HTTP / mã `data`                    | Thông báo gợi ý cho user              |
|---------------|--------------------------------------|----------------------------------------|
| client        | `size > 15 MB` hoặc `size = 0`      | "Tệp vượt quá 15 MB."                  |
| client        | `content_type` không nằm whitelist  | "Chỉ chấp nhận JPG, PNG, WEBP."        |
| presign       | `400 upload_kind_unsupported`        | "Loại upload không được hỗ trợ."       |
| presign       | `400 upload_content_type_unsupported`| "Định dạng tệp không được phép."       |
| presign       | `400 upload_too_large`               | "Tệp vượt quá kích thước cho phép."    |
| presign       | `401 auth_unauthorized`              | Điều hướng về trang đăng nhập.         |
| presign       | `503`                                | "Dịch vụ upload chưa sẵn sàng, thử lại sau." |
| uploading     | `403 SignatureDoesNotMatch`          | "Chữ ký không khớp — báo admin."       |
| uploading     | `403 RequestExpired`                 | Tự xin presign mới + PUT lại.          |
| uploading     | `0` / `NetworkError`                 | "Mất kết nối tới R2." (hook đã retry 1 lần) |
| confirming    | `404 upload_object_not_found`        | "Upload chưa tới R2 — thử lại."        |
| saving (PATCH)| `403 permission_denied`              | "Bạn không có quyền sửa khoa."         |
| saving (PATCH)| `404 department_not_found`           | "Khoa không tồn tại hoặc đã bị xoá."   |
| saving (PATCH)| `422`                                | Hiển thị message BE trả về.            |

---

## 8. Luồng hiển thị & làm mới URL

- URL đọc (`avatar_url`) chỉ sống 1 giờ. FE **đừng cache vĩnh viễn** —
  cứ mỗi lần render, dùng `avatar_url` mà BE trả trong payload gần nhất.
- Khi URL hết hạn:
  - Cách 1 (khuyến nghị): reload lại trang danh sách chi tiết khoa
    → `GET /api/v1/departments/{id}` → BE tự sinh presigned GET mới.
  - Cách 2: thêm icon "Refresh ảnh" gọi lại `GET /departments/{id}`.

---

## 9. Checklist triển khai nhanh

- [ ] `apiFetch` có kèm `Authorization: Bearer <token>` (xem `FE_AUTH_TOKEN.md`).
- [ ] Validate content-type & size trước khi gọi `presign` để né lỗi `400`.
- [ ] Lưu `object_key` sau bước 1; gắn vào bước 4.
- [ ] Khi đổi ảnh cũ sang ảnh mới: chỉ cần `PATCH avatar_object_key` mới — **BE
      tự xóa object cũ trên R2** (sau khi commit DB). FE không gọi thêm API
      delete. Nếu xóa R2 fail thì BE log warning, DB vẫn OK — orphan file có
      thể được dọn bằng lifecycle policy của bucket.
- [ ] Khi muốn **xoá** avatar: `PATCH { "avatar_object_key": null }` — BE
      xóa cả object cũ trên R2 và set cột về `null`.
- [ ] PATCH idempotent: gửi lặp lại cùng `avatar_object_key` không gây xóa nhầm.
- [ ] Ảnh lỗi → dùng placeholder fallback (`<img onError={...}>`).

---

## 10. Tài liệu liên quan

- [`FE_UPLOADS.md`](./FE_UPLOADS.md) — chi tiết API upload R2.
- [`FE_DEPARTMENT.md`](./FE_DEPARTMENT.md) — CRUD department + partial update.
- [`FE_AUTH_TOKEN.md`](./FE_AUTH_TOKEN.md) — header `Authorization`.

---

## 11. Lịch sử thay đổi

| Phiên bản | Thay đổi |
|---|---|
| **1.2.0** | Ghi nhận hành vi BE tự xóa avatar cũ trên R2 khi PATCH `avatar_object_key` (đổi key mới hoặc set `null`). Thêm bảng case trước/sau PATCH và cập nhật checklist. |
| **1.1.0** | Thay §7 bằng hook React TypeScript drop-in: `useAvatarUpload` (presign → PUT R2 → confirm → PATCH), `useDepartment` (tự refetch khi URL hết hạn), component `DepartmentAvatarCard`. Thêm bảng map trạng thái → UI và bảng map lỗi BE → thông báo user. |
| **1.0.0** | Tài liệu end-to-end cho FE: upload avatar qua R2 và gắn vào Department. |
