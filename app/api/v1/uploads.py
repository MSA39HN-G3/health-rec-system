"""Controller upload (presign + confirm) cho Cloudflare R2.

FE chọn file -> gọi `POST /uploads/presign` để lấy URL đã ký -> PUT thẳng lên
R2 -> gọi `POST /uploads/confirm` để BE HEAD object và trả về URL đọc (presigned
GET hoặc public). Endpoint không gắn permission riêng — chỉ yêu cầu đăng nhập.
Giới hạn content-type & size được áp dụng ở 2 lớp: validation (422) và service (400).
"""
from flask import Blueprint

from ...common.response import success_response
from ...errors import NotFoundException
from ...i18n import translate
from ...middleware import Field, require_auth, validate_body, validated
from ...services import storage

bp = Blueprint("uploads", __name__, url_prefix="/api/v1/uploads")


@bp.post("/presign")
@require_auth
@validate_body(
    {
        "kind": Field(str, required=True, min_length=1, max_length=64),
        "content_type": Field(str, required=True, min_length=1, max_length=128),
        "size": Field(int, required=True, minimum=1, maximum=104857600),  # 100MB trần bảo vệ; service sẽ siết lại theo config
        # Optional: tên file gốc để log, không bắt buộc.
        "filename": Field(str, required=False, max_length=255),
    }
)
def presign_upload():
    data = validated()

    # Service áp các ràng buộc: content type nằm trong whitelist, size nằm trong
    # R2_MAX_UPLOAD_BYTES, kind được hỗ trợ. Lỗi raise 400 (lỗi nghiệp vụ).
    storage.validate_content_type(data["content_type"])
    storage.validate_size(data["size"])

    object_key = storage.build_object_key(data["kind"], data["content_type"])
    presigned = storage.presign_put(object_key, data["content_type"])
    return success_response(
        {
            "kind": data["kind"],
            "object_key": object_key,
            "method": presigned["method"],
            "url": presigned["url"],
            "headers": presigned["headers"],
            "expires_in": presigned["expires_in"],
        },
        message=translate("messages.upload_presigned"),
    )


@bp.post("/confirm")
@require_auth
@validate_body(
    {
        "kind": Field(str, required=True, min_length=1, max_length=64),
        "object_key": Field(str, required=True, min_length=1, max_length=512),
        # Optional: client có thể gửi content_type đã dùng khi PUT để BE log/audit.
        "content_type": Field(str, required=False, max_length=128),
    }
)
def confirm_upload():
    data = validated()
    if not storage.is_valid_object_key(data["object_key"]):
        raise NotFoundException("errors.upload_object_not_found")

    # HEAD object để chắc chắn đã upload xong; raise 404 nếu chưa có.
    storage.head_exists(data["object_key"])

    url = storage.presign_get(data["object_key"])
    return success_response(
        {
            "kind": data["kind"],
            "object_key": data["object_key"],
            "url": url,
            "expires_in": storage.presign_get_ttl(),
        },
        message=translate("messages.upload_confirmed"),
    )
