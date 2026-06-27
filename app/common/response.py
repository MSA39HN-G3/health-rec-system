"""Chuẩn hóa response trả về cho toàn bộ API.

Mọi response đều có cùng cấu trúc:
{
    "status":  "success" | "error",
    "code":    "string",          # mã trạng thái/nghiệp vụ dạng chuỗi
    "message": "string",
    "data":    object | list | null,
    "meta": {                     # chỉ có giá trị khi phân trang, ngược lại null
        "page":      int,
        "size":      int,
        "totalPage": int
    }
}
"""
from flask import jsonify


def _build_meta(page, size, total):
    """Tạo khối meta phân trang từ tổng số bản ghi."""
    total_page = (total + size - 1) // size if size else 0
    return {"page": page, "size": size, "totalPage": total_page}


def success_response(data=None, message=None, status_code=200, code=None, meta=None):
    body = {
        "status": "success",
        "code": str(code) if code is not None else str(status_code),
        "message": message,
        "data": data,
        "meta": meta,
    }
    return jsonify(body), status_code


def paginated_response(
    data, page, size, total, message=None, status_code=200, code=None
):
    """Response cho danh sách có phân trang, tự tính totalPage."""
    return success_response(
        data=data,
        message=message,
        status_code=status_code,
        code=code,
        meta=_build_meta(page, size, total),
    )


def error_response(message, status_code=400, code=None, data=None):
    body = {
        "status": "error",
        "code": str(code) if code is not None else str(status_code),
        "message": message,
        "data": data,
        "meta": None,
    }
    return jsonify(body), status_code
