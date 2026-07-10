"""Lớp truy cập Cloudflare R2 (S3-compatible) cho FE direct-upload.

Flow FE <-> BE <-> R2:
    1. FE gọi `POST /api/v1/uploads/presign` với `{ kind, content_type, size }`
       -> BE gọi `build_object_key(kind, ext)` + `presign_put(object_key, ...)`
       -> trả về `{ object_key, method, url, headers, expires_in }`.
    2. FE thực hiện `PUT url` với headers đã cấp để upload thẳng lên R2.
    3. FE gọi `POST /api/v1/uploads/confirm` với `{ kind, object_key }`
       -> BE gọi `head_exists(object_key)` để chắc chắn object đã có
       -> trả về `{ object_key, url, expires_in }` với `url` là presigned GET.
    4. FE lưu `object_key` vào entity liên quan (vd `departments.avatar_object_key`).

Module này không lưu state ngoài — singleton client được cache qua
`get_r2_client()` và đọc config từ Flask `app.config` thông qua hàm
`current_app` (tránh import vòng).
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Optional

import boto3
from botocore.client import Config
from flask import current_app
from werkzeug.exceptions import ServiceUnavailable

from ..errors import BadRequestException, NotFoundException

logger = logging.getLogger(__name__)

# S3-compatible client; R2 dùng `auto` cho region (chữ ký vẫn đúng).
_SIG_VERSION = "s3v4"
_REGION = "auto"

# Map extension/loại object => prefix trong bucket.
#  - department_avatar: ảnh đại diện khoa
#  - doctor_avatar:     ảnh đại diện bác sĩ
#  - doctor_document:   tài liệu bác sĩ (giấy phép, bằng cấp, hợp đồng, ...)
_KIND_PREFIXES = {
    "department_avatar": "department",
    "doctor_avatar": "doctor",
    "doctor_document": "doctor",
}

# Map content_type -> đuôi file mặc định.
_CONTENT_TYPE_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}


def get_r2_client():
    """Trả về boto3 S3 client trỏ vào R2 (cấu hình theo env). Lazy-init."""
    cfg = current_app.config
    if not cfg.get("R2_BUCKET") or not cfg.get("R2_ACCESS_KEY_ID"):
        raise ServiceUnavailable("Object storage is not configured.")

    return boto3.client(
        "s3",
        endpoint_url=_endpoint_url(cfg),
        aws_access_key_id=cfg["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=cfg["R2_SECRET_ACCESS_KEY"],
        region_name=_REGION,
        config=Config(signature_version=_SIG_VERSION),
    )


def _endpoint_url(cfg) -> str:
    """Endpoint R2: `https://<account>.r2.cloudflarestorage.com`."""
    account_id = cfg.get("R2_ACCOUNT_ID")
    if not account_id:
        raise ServiceUnavailable("R2_ACCOUNT_ID is not configured.")
    return f"https://{account_id}.r2.cloudflarestorage.com"


def _bucket() -> str:
    return current_app.config["R2_BUCKET"]


def _public_host(cfg) -> Optional[str]:
    """Trả về host tuỳ chỉnh nếu đã cấu hình (vd assets.example.com)."""
    host = cfg.get("R2_PUBLIC_HOST")
    return host.rstrip("/") if host else None


def build_object_key(kind: str, content_type: str) -> str:
    """Sinh key ngẫu nhiên theo `kind` + content_type.

    Ví dụ:
      ("department_avatar", "image/png")     -> "department/<uuid>.png"
      ("doctor_avatar",     "image/jpeg")    -> "doctor/avatar/<uuid>.jpg"
      ("doctor_document",   "application/pdf") -> "doctor/document/<uuid>.pdf"
    """
    if kind not in _KIND_PREFIXES:
        raise BadRequestException(
            "errors.upload_kind_unsupported",
            details={"kind": "invalid_kind"},
        )
    ext = _CONTENT_TYPE_EXT.get(content_type.lower())
    if not ext:
        raise BadRequestException(
            "errors.upload_content_type_unsupported",
            details={"content_type": "invalid_type"},
        )
    base = _KIND_PREFIXES[kind]
    # Các kind liên quan tới doctor phân thành sub-prefix để dễ quản lý trong bucket.
    if kind == "doctor_avatar":
        return f"{base}/avatar/{uuid.uuid4().hex}{ext}"
    if kind == "doctor_document":
        return f"{base}/document/{uuid.uuid4().hex}{ext}"
    return f"{base}/{uuid.uuid4().hex}{ext}"


def validate_content_type(content_type: str) -> None:
    """Đảm bảo content_type nằm trong whitelist của cấu hình (`R2_ALLOWED_CONTENT_TYPES`)."""
    allowed = current_app.config["R2_ALLOWED_CONTENT_TYPES"]
    if content_type.lower() not in allowed:
        raise BadRequestException(
            "errors.upload_content_type_unsupported",
            details={"content_type": "invalid_type"},
        )


def validate_size(size: int) -> None:
    max_bytes = int(current_app.config["R2_MAX_UPLOAD_BYTES"])
    if size <= 0 or size > max_bytes:
        raise BadRequestException(
            "errors.upload_too_large",
            details={"size": "out_of_range"},
        )


def is_valid_object_key(key: str) -> bool:
    """Ràng buộc shape của object_key: prefix hợp lệ + phần đuôi an toàn.

    Dùng khi client gửi ngược `object_key` về (vd trong `confirm` hoặc khi lưu
    vào entity) để chống injection / path traversal.

    Các prefix được chấp nhận:
      - department/...
      - doctor/avatar/...
      - doctor/document/...
    """
    if not key or "\x00" in key or key.startswith("/") or "//" in key:
        return False
    valid_prefixes = {
        "department",
        "doctor/avatar",
        "doctor/document",
    }
    head, _, _name = key.rpartition("/")
    return head in valid_prefixes and bool(_name)


def presign_put(object_key: str, content_type: str) -> dict:
    """Sinh presigned URL để FE upload (PUT) object lên R2.

    Trả về dict có `url`, `headers` (client phải gắn), `expires_in` (giây).
    R2 KHÔNG chấp nhận `x-amz-acl` hay metadata tuỳ ý trong PUT — chỉ gắn
    `Content-Type` để server ghi đúng mimetype.
    """
    cfg = current_app.config
    ttl = int(cfg["R2_PRESIGN_PUT_TTL"])
    client = get_r2_client()
    url = client.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": _bucket(),
            "Key": object_key,
            "ContentType": content_type,
        },
        ExpiresIn=ttl,
        HttpMethod="PUT",
    )
    return {
        "method": "PUT",
        "url": url,
        "headers": {"Content-Type": content_type},
        "expires_in": ttl,
    }


def head_exists(object_key: str) -> bool:
    """HEAD object; trả True nếu tồn tại, raise NotFound nếu không."""
    client = get_r2_client()
    try:
        client.head_object(Bucket=_bucket(), Key=object_key)
        return True
    except client.exceptions.NoSuchKey:  # type: ignore[attr-defined]
        raise NotFoundException(
            "errors.upload_object_not_found",
            details={"object_key": "not_found"},
        )
    except client.exceptions.NotFound:  # 404 tổng quát (vd bucket không tồn tại)
        raise NotFoundException(
            "errors.upload_object_not_found",
            details={"object_key": "not_found"},
        )


def delete_object(object_key: str) -> bool:
    """Xóa object khỏi R2. Trả True nếu xóa được, False nếu không tồn tại.

    Dùng trong các luồng cleanup (vd PATCH department đổi avatar → xóa avatar
    cũ). Bọc ngoài service: **luôn gọi SAU commit DB**, lỗi xóa chỉ log warning,
    không rollback nghiệp vụ — file orphan vẫn có thể dọn sau bằng lifecycle
    policy của R2.

    Raises:
        ServiceUnavailable: storage chưa cấu hình.
    """
    if not is_valid_object_key(object_key):
        # Từ chối key rác để không phát sinh request xóa lung tung.
        # Trả False thay vì raise: cleanup là best-effort, không nên
        # làm fail cả luồng nghiệp vụ vì dữ liệu cũ (vd key legacy trước fix).
        logger.warning(
            "Refusing to delete R2 object with invalid shape: %r", object_key
        )
        return False

    client = get_r2_client()
    try:
        client.delete_object(Bucket=_bucket(), Key=object_key)
        return True
    except client.exceptions.NoSuchKey:  # type: ignore[attr-defined]
        return False


def presign_get(object_key: str) -> str:
    """Trả về URL truy cập object để FE dùng trong thẻ `<img>` / link.

    - Nếu bucket được bật **public** thông qua `R2_PUBLIC_HOST` (custom domain
      hoặc r2.dev) → trả URL public, FE dùng trực tiếp.
    - Nếu **không** có `R2_PUBLIC_HOST` → bucket mặc định là private, BE ký
      GET có thời hạn (`R2_PRESIGN_GET_TTL`).
    """
    cfg = current_app.config
    public_url = build_public_url(object_key)
    if public_url:
        return public_url

    ttl = int(cfg["R2_PRESIGN_GET_TTL"])
    client = get_r2_client()
    return client.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": _bucket(), "Key": object_key},
        ExpiresIn=ttl,
        HttpMethod="GET",
    )


def presign_get_ttl() -> int:
    """Trả về TTL (giây) mà presigned GET vừa dựng, để FE biết URL sống bao lâu."""
    return int(current_app.config["R2_PRESIGN_GET_TTL"])


def build_public_url(object_key: str) -> Optional[str]:
    """URL public (chỉ dùng khi bucket được bật public). Trả None nếu không có host."""
    host = _public_host(current_app.config)
    if not host:
        return None
    return f"https://{host}/{_bucket()}/{object_key}"
