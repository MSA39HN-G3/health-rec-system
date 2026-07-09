# Hướng dẫn FE: Upload tài liệu bác sĩ (end-to-end)

> **Phiên bản: 1.0.0** — Bản đầu: mô tả luồng direct-upload tài liệu bác sĩ
> (giấy phép hành nghề, bằng cấp, chứng chỉ, hợp đồng, ...) qua Cloudflare R2.
> BE tự xóa object cũ trên R2 khi PATCH/DELETE tài liệu — FE không cần gọi
> thêm API delete. PATCH idempotent (gửi lặp lại cùng key không xóa nhầm).
>
> Tài liệu gốc (nếu cần chi tiết từng bước):
> - [`FE_UPLOADS.md`](./FE_UPLOADS.md) — API upload R2 (presign/confirm).
> - [`FE_DOCTOR.md`](./FE_DOCTOR.md) — CRUD doctor + quản lý tài liệu.
> - [`FE_AUTH_TOKEN.md`](./FE_AUTH_TOKEN.md) — lấy `Authorization` header.
> - [`FE_DEPARTMENT_AVATAR_UPLOAD.md`](./FE_DEPARTMENT_AVATAR_UPLOAD.md) — flow tương tự cho avatar khoa.
>
> Đối tượng: React/JS. Có 1 ví dụ hook + component hoàn chỉnh ở cuối tài liệu.

---

## 1. Tóm tắt endpoint

| Method | Path | Cần `Bearer`? | Permission | Mục đích trong luồng tài liệu |
|--------|------|---|---|---|
| `POST` | `/api/v1/uploads/presign` | ✅ | đã đăng nhập | Xin URL đã ký để PUT file. |
| `PUT`  | URL trả về ở trên (R2, **không qua BE**) | ❌ | — | FE upload trực tiếp lên R2. |
| `POST` | `/api/v1/uploads/confirm` | ✅ | đã đăng nhập | BE HEAD kiểm tra đã có file + trả URL đọc. |
| `POST` | `/api/v1/doctors/{id}/documents` | ✅ | `department:manage` | Tạo tài liệu với `object_key`. |
| `PATCH`| `/api/v1/doctors/{id}/documents/{doc_id}` | ✅ | `department:manage` | Cập nhật tài liệu (gồm `object_key` mới). |
| `DELETE`| `/api/v1/doctors/{id}/documents/{doc_id}` | ✅ | `department:manage` | Xóa tài liệu (BE tự cleanup R2). |

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
│        │  4. POST /doctors/{id}/documents
│        │ ───────────▶ │   BE     │ → { document với object_key + url }
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
  "kind": "doctor_document",
  "content_type": "application/pdf",
  "size": 1048576,
  "filename": "license.pdf"
}
```

| Trường | Bắt buộc | Ý nghĩa |
|--------|:--------:|---------|
| `kind` | ✅ | Hằng số `doctor_document` (giá trị duy nhất dành cho tài liệu bác sĩ). |
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
    "kind": "doctor_document",
    "object_key": "doctor/document/4f1c2a....pdf",
    "method": "PUT",
    "url": "https://<account>.r2.cloudflarestorage.com/health-rec-assets/doctor/document/...?X-Amz-...=...",
    "headers": { "Content-Type": "application/pdf" },
    "expires_in": 600
  },
  "meta": null
}
```

> ⚠️ **Bắt buộc phải lưu `data.object_key`** — đây là chìa khóa để gắn vào
> tài liệu ở bước 4. Presigned `url` chỉ sống `expires_in` giây (mặc định
> 600s = 10 phút).
>
> **Các kind được hỗ trợ hiện tại:**
> - `department_avatar` → prefix `department/`
> - `doctor_avatar` → prefix `doctor/avatar/`
> - `doctor_document` → prefix `doctor/document/`

### Lỗi có thể gặp

| HTTP | Mã `data` | Gợi ý xử lý FE |
|------|-----------|-----------------|
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
  headers: presignData.headers,     // { "Content-Type": "application/pdf" }
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
|---------|-------------|-----------|
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
  "kind": "doctor_document",
  "object_key": "doctor/document/4f1c2a....pdf",
  "content_type": "application/pdf"
}
```

### Response — `200 OK`

```json
{
  "status": "success",
  "code": "200",
  "message": "Xác nhận upload thành công.",
  "data": {
    "kind": "doctor_document",
    "object_key": "doctor/document/4f1c2a....pdf",
    "url": "https://...presigned-get...",
    "expires_in": 3600
  }
}
```

- `url` là **presigned GET** có TTL `R2_PRESIGN_GET_TTL` (mặc định 3600s = 1 giờ)
  khi bucket đặt private. Nếu BE cấu hình `R2_PUBLIC_HOST` thì `url` là URL
  public không ký — dùng trực tiếp.
- **Đừng lưu `url` này vĩnh viễn.** Sau khi hết hạn, FE chỉ cần gọi lại
  `GET /api/v1/doctors/{id}/documents/{doc_id}`; BE tự derive URL mới từ `object_key`.

### Lỗi có thể gặp

| HTTP | Khi nào | Gợi ý FE |
|------|---------|----------|
| `404` `errors.upload_object_not_found` | Bước 2 chưa PUT xong, hoặc `object_key` sai shape. | Retry `confirm` sau khi đợi PUT xong. |
| `401` | Token hết hạn. | Refresh token rồi gọi lại. |

---

## 6. Bước 4 — Tạo / cập nhật tài liệu

### 6.1. Tạo tài liệu mới — `POST /api/v1/doctors/{doctor_id}/documents`

```http
POST /api/v1/doctors/1/documents HTTP/1.1
Authorization: Bearer <token>
Content-Type: application/json

{
  "document_type": "license",          // bắt buộc: license | degree | certificate | contract | id_card | other
  "title": "Giấy phép hành nghề",     // bắt buộc (1-255 ký tự)
  "object_key": "doctor/document/4f1c2a....pdf",
  "issue_date": "2010-01-15",          // tùy chọn (ISO date)
  "expiry_date": "2030-01-15"          // tùy chọn (ISO date)
}
```

**Lưu ý đặc biệt:** Mỗi bác sĩ chỉ có **1 giấy phép hành nghề**
(`document_type: "license"`). Tạo license mới khi đã có sẽ trả lỗi `400`:

```json
{
  "status": "error",
  "code": "400",
  "message": "Dữ liệu không hợp lệ.",
  "data": {
    "document_type": "duplicate_license",
    "message": "Bác sĩ đã có giấy phép hành nghề. Vui lòng cập nhật tài liệu hiện có."
  }
}
```

**Response — `201 Created`:**

```json
{
  "status": "success",
  "code": "201",
  "message": null,
  "data": {
    "id": 5,
    "doctor_id": 1,
    "document_type": "license",
    "title": "Giấy phép hành nghề",
    "object_key": "doctor/document/4f1c2a....pdf",
    "url": "https://...presigned-get...",
    "issue_date": "2010-01-15",
    "expiry_date": "2030-01-15",
    "is_verified": false,
    "is_expiring_soon": false,
    "created_at": "2026-07-09T10:00:00+00:00",
    "updated_at": "2026-07-09T10:00:00+00:00"
  },
  "meta": null
}
```

### 6.2. Cập nhật tài liệu — `PATCH /api/v1/doctors/{doctor_id}/documents/{doc_id}`

```http
PATCH /api/v1/doctors/1/documents/5 HTTP/1.1
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "Giấy phép hành nghề (gia hạn)",
  "object_key": "doctor/document/new-key.pdf",
  "expiry_date": "2035-01-15",
  "is_verified": true
}
```

Tất cả field đều tùy chọn. Khi gửi `object_key` mới:
- **BE tự xóa object cũ trên R2** sau khi commit DB thành công.
- **BE cũng xóa cache `url`** → `to_dict()` lần kế tiếp tự derive presigned GET mới.

### 6.3. Xóa tài liệu — `DELETE /api/v1/doctors/{doctor_id}/documents/{doc_id}`

```http
DELETE /api/v1/doctors/1/documents/5 HTTP/1.1
Authorization: Bearer <token>
```

**Response:**

```json
{ "status": "success", "code": "200", "message": "Xóa tài liệu thành công", "data": null, "meta": null }
```

> Khi xóa tài liệu, **BE tự xóa object trên R2** (best-effort) sau khi commit DB.
> FE không cần gọi thêm API delete.

### 6.4. Các lỗi có thể gặp

| HTTP | Mã `data` / `message` | Khi nào |
|------|-----------------------|---------|
| `403` | `errors.permission_denied` | User không có `department:manage`. |
| `404` | `errors.not_found` | `doctor_id` / `doc_id` không tồn tại. |
| `400` | `document_type: duplicate_license` | Đã có license → phải PATCH thay vì POST. |
| `422` | field validation | Thiếu/sai kiểu field. |

---

## 7. Dọn dẹp object cũ trên R2 (BE tự làm — FE không cần gọi delete)

Tương tự avatar khoa, cơ chế dọn dẹp object cũ áp dụng cho tài liệu bác sĩ:

- **PATCH `object_key` đổi sang key mới** → BE tự xóa object cũ trên R2 sau khi commit DB.
- **PATCH `object_key: null`** → BE tự xóa object cũ + set cột về `null`.
- **DELETE tài liệu** → BE tự xóa object trên R2 (best-effort) sau khi commit DB.
- **PATCH idempotent**: gửi cùng `object_key` đã có sẵn → BE **không xóa** gì cả (an toàn khi user click "Lưu" hai lần).
- **Lỗi R2** chỉ log warning, **không rollback** DB. File orphan có thể dọn sau bằng lifecycle policy của bucket.

| Trước PATCH (`object_key`) | Body gửi | Object trên R2 |
|---|---|---|
| `null` | `doctor/document/xyz.pdf` | tạo `xyz.pdf` (không xóa gì) |
| `doctor/document/abc.pdf` | `doctor/document/xyz.pdf` | xóa `abc.pdf`, tạo `xyz.pdf` |
| `doctor/document/abc.pdf` | `abc.pdf` (giữ nguyên) | giữ nguyên (idempotent) |
| `doctor/document/abc.pdf` | `null` | xóa `abc.pdf` |
| `null` | `null` | giữ nguyên |

> PATCH idempotent: nếu FE gửi lặp lại cùng `object_key` đã có sẵn,
> BE **không xóa** gì cả (an toàn khi user click "Lưu" hai lần).

---

## 8. Hook & component React (drop-in)

Mục này cho bạn 3 file có thể copy nguyên xi vào project FE (TypeScript). Tất cả
phụ thuộc vào **một helper duy nhất** `apiFetch` — xem [`FE_AUTH_TOKEN.md`](./FE_AUTH_TOKEN.md).
Hook tự xử lý: validate client, presign, PUT trực tiếp lên R2, confirm, POST tài liệu,
fallback khi URL hết hạn, và trả về state để component bind.

### 8.1. `useDoctorDocumentUpload.ts` — hook chính

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
  kind: "doctor_document";
  object_key: string;
  method: "PUT";
  url: string;
  headers: Record<string, string>;
  expires_in: number;
};

type ConfirmResp = {
  kind: "doctor_document";
  object_key: string;
  url: string;
  expires_in: number;
};

type DoctorDocument = {
  id: number;
  doctor_id: number;
  document_type: string;
  title: string;
  object_key: string | null;
  url: string | null;
  issue_date: string | null;
  expiry_date: string | null;
  is_verified: boolean;
  is_expiring_soon: boolean;
  created_at: string;
  updated_at: string | null;
};

type CreateDocumentPayload = {
  document_type: string;
  title: string;
  object_key: string;
  issue_date?: string;
  expiry_date?: string;
};

// ====== Helper: gọi BE với Authorization ======
declare const apiFetch: <T = unknown>(
  path: string,
  init?: { method?: string; body?: BodyInit | null }
) => Promise<ApiEnvelope<T>>;

// ====== Ràng buộc khớp với app/config.py ======
const ALLOWED_CT = [
  "image/jpeg",
  "image/png",
  "image/webp",
  "application/pdf",
] as const;
const MAX_BYTES = 15 * 1024 * 1024; // R2_MAX_UPLOAD_BYTES mặc định

export type UploadStatus =
  | "idle"
  | "presigning"
  | "uploading"
  | "confirming"
  | "saving"
  | "done"
  | "error";

export class UploadDocumentError extends Error {
  readonly step: UploadStatus;
  readonly http?: number;
  readonly code?: string;
  constructor(
    step: UploadStatus,
    message: string,
    http?: number,
    code?: string
  ) {
    super(message);
    this.step = step;
    this.http = http;
    this.code = code;
  }
}

function validate(file: File) {
  if (file.size <= 0 || file.size > MAX_BYTES) {
    throw new UploadDocumentError(
      "presigning",
      "Tệp vượt quá 15 MB hoặc rỗng."
    );
  }
  const ct = (file.type || "").toLowerCase();
  if (!ALLOWED_CT.includes(ct as (typeof ALLOWED_CT)[number])) {
    throw new UploadDocumentError(
      "presigning",
      "Chỉ chấp nhận JPG, PNG, WEBP, PDF."
    );
  }
}

async function putToR2(
  url: string,
  headers: Record<string, string>,
  file: File
) {
  // PUT raw bytes — KHÔNG multipart. Retry 1 lần khi mạng lag (NetworkError).
  // Không retry khi server trả >= 400 (chữ ký đã cháy).
  let res: Response;
  try {
    res = await fetch(url, { method: "PUT", headers, body: file });
  } catch {
    try {
      res = await fetch(url, { method: "PUT", headers, body: file });
    } catch (e) {
      throw new UploadDocumentError("uploading", "Mất kết nối tới R2.");
    }
  }
  if (!res.ok) {
    throw new UploadDocumentError(
      "uploading",
      `R2 từ chối (${res.status}).`,
      res.status
    );
  }
}

export function useDoctorDocumentUpload(doctorId: number) {
  const [status, setStatus] = useState<UploadStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [document, setDocument] = useState<DoctorDocument | null>(null);

  const reset = useCallback(() => {
    setStatus("idle");
    setError(null);
  }, []);

  const upload = useCallback(
    async (params: {
      file: File;
      documentType: string;
      title: string;
      issueDate?: string;
      expiryDate?: string;
    }) => {
      const { file, documentType, title, issueDate, expiryDate } = params;
      setError(null);
      try {
        validate(file);

        // 1) presign
        setStatus("presigning");
        const p = await apiFetch<PresignResp>("/api/v1/uploads/presign", {
          method: "POST",
          body: JSON.stringify({
            kind: "doctor_document",
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
            kind: "doctor_document",
            object_key: p.data.object_key,
            content_type: file.type,
          }),
        });

        // 4) POST tạo tài liệu
        setStatus("saving");
        const payload: CreateDocumentPayload = {
          document_type: documentType,
          title: title,
          object_key: p.data.object_key,
        };
        if (issueDate) payload.issue_date = issueDate;
        if (expiryDate) payload.expiry_date = expiryDate;

        const d = await apiFetch<DoctorDocument>(
          `/api/v1/doctors/${doctorId}/documents`,
          {
            method: "POST",
            body: JSON.stringify(payload),
          }
        );
        setDocument(d.data);
        setStatus("done");
        return d.data;
      } catch (e) {
        const msg =
          e instanceof UploadDocumentError
            ? e.message
            : e instanceof Error
            ? e.message
            : "Upload thất bại.";
        setError(msg);
        setStatus("error");
        throw e;
      }
    },
    [doctorId]
  );

  return { upload, status, error, document, reset };
}
```

### 8.2. `useDoctorDocument.ts` — tự lấy lại URL khi file hết hạn

`url` chỉ sống `R2_PRESIGN_GET_TTL` (mặc định 3600s). Hook này gọi lại
`GET /api/v1/doctors/{id}/documents/{doc_id}` khi user click "Tải lại" hoặc
khi `<img>` / `<iframe>` vỡ (404 từ R2 vì URL hết hạn).

```tsx
import { useEffect, useState } from "react";

type DoctorDocument = {
  id: number;
  doctor_id: number;
  object_key: string | null;
  url: string | null;
  is_verified: boolean;
  is_expiring_soon: boolean;
  expiry_date: string | null;
};

declare const apiFetch: <T = unknown>(
  path: string,
  init?: { method?: string; body?: BodyInit | null }
) => Promise<{ data: T }>;

export function useDoctorDocument(
  doctorId: number,
  documentId: number
) {
  const [data, setData] = useState<DoctorDocument | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await apiFetch<DoctorDocument>(
        `/api/v1/doctors/${doctorId}/documents/${documentId}`
      );
      setData(r.data);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Tải tài liệu thất bại."
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doctorId, documentId]);

  return { data, loading, error, refetch };
}
```

### 8.3. Component sử dụng cả hai hook

```tsx
import { useRef } from "react";
import {
  useDoctorDocumentUpload,
  UploadDocumentError,
} from "./useDoctorDocumentUpload";
import { useDoctorDocument } from "./useDoctorDocument";

const STATUS_LABEL: Record<string, string> = {
  idle: "Chọn tệp",
  presigning: "Đang xin URL...",
  uploading: "Đang tải lên R2...",
  confirming: "Đang xác nhận...",
  saving: "Đang lưu...",
  done: "Xong",
};

const STATUS_HINT: Record<string, string> = {
  presigning: "Xin URL upload từ server...",
  uploading: "Đang upload file lên Cloudflare R2...",
  confirming: "Đang xác nhận file đã lên R2...",
  saving: "Đang tạo tài liệu trong hệ thống...",
};

const DOCUMENT_TYPE_LABEL: Record<string, string> = {
  license: "Giấy phép hành nghề",
  degree: "Bằng cấp",
  certificate: "Chứng chỉ",
  contract: "Hợp đồng lao động",
  id_card: "CCCD/CMND",
  other: "Khác",
};

export function DoctorDocumentUploader({
  doctorId,
  documentType,
  onUploaded,
}: {
  doctorId: number;
  documentType: string;
  onUploaded?: (doc: { id: number; url: string | null }) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const upload = useDoctorDocumentUpload(doctorId);

  const busy =
    upload.status !== "idle" &&
    upload.status !== "done" &&
    upload.status !== "error";

  async function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const doc = await upload.upload({
        file,
        documentType,
        title: file.name,
      });
      onUploaded?.(doc);
    } catch (e) {
      if (e instanceof UploadDocumentError) {
        console.error("Upload lỗi tại bước:", e.step, e.http);
      }
    } finally {
      // Cho phép chọn lại cùng 1 file nếu muốn retry
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div>
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,application/pdf"
        disabled={busy}
        onChange={onPick}
      />

      <p aria-live="polite">
        {busy ? STATUS_HINT[upload.status] : `Sẵn sàng tải lên ${DOCUMENT_TYPE_LABEL[documentType] || documentType}`}
      </p>

      {upload.status === "done" && upload.document && (
        <p style={{ color: "green" }}>
          ✓ Đã tạo tài liệu #{upload.document.id}
        </p>
      )}

      {upload.error && (
        <p role="alert" style={{ color: "crimson" }}>
          {upload.error}
        </p>
      )}
    </div>
  );
}

export function DoctorDocumentViewer({
  doctorId,
  documentId,
  title,
}: {
  doctorId: number;
  documentId: number;
  title: string;
}) {
  const doc = useDoctorDocument(doctorId, documentId);

  return (
    <div>
      <h3>{title}</h3>

      {doc.loading && <p>Đang tải...</p>}
      {doc.error && <p style={{ color: "crimson" }}>{doc.error}</p>}

      {doc.data && (
        <>
          <a
            href={doc.data.url ?? "#"}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => {
              if (!doc.data?.url) e.preventDefault();
            }}
          >
            Mở tài liệu
          </a>

          {/* Tự refetch khi URL hết hạn hoặc R2 trả 404 */}
          {doc.data.url && (
            <iframe
              src={doc.data.url}
              title={title}
              style={{ width: "100%", height: 600, border: 0 }}
              onError={() => void doc.refetch()}
            />
          )}

          {doc.data.is_expiring_soon && (
            <p style={{ color: "orange" }}>
              ⚠️ Tài liệu sắp hết hạn (còn &lt; 30 ngày)
            </p>
          )}
        </>
      )}
    </div>
  );
}
```

### 8.4. Bảng map trạng thái → UI

| `status` | Nhãn tiếng Việt | Spinner | Disable nút | Hành động cho phép |
|----------|------------------|:-------:|:-----------:|---------------------|
| `idle` | (ẩn) | - | no | chọn file |
| `presigning` | Đang xin URL... | ✓ | yes | - |
| `uploading` | Đang tải lên R2... | ✓ | yes | - |
| `confirming` | Đang xác nhận... | ✓ | yes | - |
| `saving` | Đang lưu... | ✓ | yes | - |
| `done` | Xong | - | no | chọn file mới |
| `error` | (xem `upload.error`) | - | no | chọn file mới |

### 8.5. Bảng map lỗi từ BE → thông báo user

| Bước thất bại | HTTP / mã `data` | Thông báo gợi ý cho user |
|---------------|------------------|---------------------------|
| client | `size > 15 MB` hoặc `size = 0` | "Tệp vượt quá 15 MB." |
| client | `content_type` không nằm whitelist | "Chỉ chấp nhận JPG, PNG, WEBP, PDF." |
| presign | `400 upload_kind_unsupported` | "Loại upload không được hỗ trợ." |
| presign | `400 upload_content_type_unsupported` | "Định dạng tệp không được phép." |
| presign | `400 upload_too_large` | "Tệp vượt quá kích thước cho phép." |
| presign | `401 auth_unauthorized` | Điều hướng về trang đăng nhập. |
| presign | `503` | "Dịch vụ upload chưa sẵn sàng, thử lại sau." |
| uploading | `403 SignatureDoesNotMatch` | "Chữ ký không khớp — báo admin." |
| uploading | `403 RequestExpired` | Tự xin presign mới + PUT lại. |
| uploading | `0` / `NetworkError` | "Mất kết nối tới R2." (hook đã retry 1 lần) |
| confirming | `404 upload_object_not_found` | "Upload chưa tới R2 — thử lại." |
| saving | `400 document_type: duplicate_license` | "Bác sĩ đã có giấy phép — dùng PATCH thay vì POST." |
| saving | `403 permission_denied` | "Bạn không có quyền tạo tài liệu." |
| saving | `404 doctor_not_found` | "Bác sĩ không tồn tại hoặc đã bị xoá." |
| saving | `422` | Hiển thị message BE trả về. |

---

## 9. Luồng hiển thị & làm mới URL

- URL đọc (`url`) chỉ sống 1 giờ. FE **đừng cache vĩnh viễn** —
  cứ mỗi lần render, dùng `url` mà BE trả trong payload gần nhất.
- Khi URL hết hạn:
  - Cách 1 (khuyến nghị): reload lại trang chi tiết tài liệu
    → `GET /api/v1/doctors/{id}/documents/{doc_id}` → BE tự sinh presigned GET mới.
  - Cách 2: thêm icon "Tải lại" gọi lại `GET /api/v1/doctors/{id}/documents/{doc_id}`.
  - Cách 3: trong component, lắng nghe `onError` của `<iframe>` / `<img>` rồi gọi `refetch()`.

---

## 10. Checklist triển khai nhanh

- [ ] `apiFetch` có kèm `Authorization: Bearer <token>` (xem `FE_AUTH_TOKEN.md`).
- [ ] Validate content-type (`image/jpeg`, `image/png`, `image/webp`, `application/pdf`) & size (≤ 15 MB) phía client trước khi gọi `presign`.
- [ ] Lưu `object_key` sau bước 1; gắn vào bước 4.
- [ ] Với `document_type: "license"`, kiểm tra backend trả lỗi `duplicate_license` nếu đã có → dùng PATCH thay vì POST.
- [ ] Khi đổi file: chỉ cần PATCH `object_key` mới — **BE tự xóa object cũ trên R2** (sau khi commit DB). FE không cần gọi API delete.
- [ ] Khi muốn **xoá** tài liệu: gọi `DELETE /api/v1/doctors/{id}/documents/{doc_id}` — BE tự xóa cả object trên R2 lẫn row trong DB.
- [ ] PATCH idempotent: gửi lặp lại cùng `object_key` không gây xóa nhầm.
- [ ] Khi URL `url` hết hạn: dùng `onError` của `<iframe>`/`<img>` hoặc nút "Tải lại" để gọi `refetch()`.
- [ ] Nếu xóa R2 fail thì BE log warning, DB vẫn OK — orphan file có thể dọn bằng lifecycle policy của bucket.

---

## 11. Tài liệu liên quan

- [`FE_UPLOADS.md`](./FE_UPLOADS.md) — chi tiết API upload R2.
- [`FE_DOCTOR.md`](./FE_DOCTOR.md) — CRUD doctor + quản lý tài liệu.
- [`FE_DEPARTMENT_AVATAR_UPLOAD.md`](./FE_DEPARTMENT_AVATAR_UPLOAD.md) — flow tương tự cho avatar khoa.
- [`FE_AUTH_TOKEN.md`](./FE_AUTH_TOKEN.md) — header `Authorization`.

---

## 12. Lịch sử thay đổi

| Phiên bản | Thay đổi |
|-----------|----------|
| **1.0.0** | Bản đầu: tài liệu end-to-end cho FE upload tài liệu bác sĩ qua R2 với `kind = "doctor_document"`. Bao gồm 3 file React drop-in (`useDoctorDocumentUpload`, `useDoctorDocument`, components), bảng map trạng thái/lỗi, và cơ chế dọn dẹp tự động object cũ khi PATCH/DELETE. |
