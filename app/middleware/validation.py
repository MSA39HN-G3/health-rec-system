"""Middleware validate dữ liệu đầu vào theo schema khai báo.

Cách dùng (đặt decorator trên controller):

    from ..middleware.validation import Field, validate_body, validated

    @bp.post("/records")
    @validate_body({
        "title": Field(str, required=True, min_length=1, max_length=255),
        "age":   Field(int, required=False, minimum=0, maximum=150),
        "email": Field(str, type="email"),
    })
    def create_record():
        data = validated()          # dict đã được làm sạch & ép kiểu
        ...

Khi không hợp lệ, tự động raise ValidationException -> handler tập trung trả về
response chuẩn hóa (status 422). `data` chứa chi tiết theo từng field, ví dụ:
    { "title": "required", "age": "too_large" }
Các mã lỗi (reason code) ở dạng máy đọc được để FE map sang thông báo phù hợp.
"""
import re
from functools import wraps

from flask import g, request

from ..errors import ValidationException

_MISSING = object()
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_TRUE = {"true", "1", "yes", "on"}
_FALSE = {"false", "0", "no", "off"}


class Field:
    """Khai báo ràng buộc cho một trường.

    type: kiểu dữ liệu mong muốn — "string"|str, "integer"|int, "number"|float,
          "boolean"|bool, hoặc "email".
    """

    def __init__(
        self,
        type="string",
        required=True,
        default=_MISSING,
        min_length=None,
        max_length=None,
        minimum=None,
        maximum=None,
        choices=None,
        nullable=False,
        strip=True,
    ):
        self.type = _normalize_type(type)
        self.required = required
        self.default = default
        self.min_length = min_length
        self.max_length = max_length
        self.minimum = minimum
        self.maximum = maximum
        self.choices = set(choices) if choices is not None else None
        self.nullable = nullable
        self.strip = strip

    def process(self, present, value):
        """Trả về (ok, cleaned_value_hoặc_reason_code)."""
        if not present:
            if self.required:
                return False, "required"
            if self.default is not _MISSING:
                return True, self.default
            return True, _MISSING  # không có trong output

        if value is None:
            if self.nullable:
                return True, None
            return False, "null_not_allowed"

        ok, cleaned = _coerce(self.type, value, self.strip)
        if not ok:
            return False, cleaned  # cleaned là reason code

        reason = self._check_constraints(cleaned)
        if reason:
            return False, reason
        return True, cleaned

    def _check_constraints(self, value):
        if self.choices is not None and value not in self.choices:
            return "invalid_choice"
        if self.type in ("string", "email"):
            if self.min_length is not None and len(value) < self.min_length:
                return "too_short"
            if self.max_length is not None and len(value) > self.max_length:
                return "too_long"
        if self.type in ("integer", "number"):
            if self.minimum is not None and value < self.minimum:
                return "too_small"
            if self.maximum is not None and value > self.maximum:
                return "too_large"
        return None


def _normalize_type(type):
    mapping = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        "str": "string",
        "int": "integer",
        "float": "number",
        "bool": "boolean",
    }
    return mapping.get(type, type)


def _coerce(type, value, strip):
    """Ép kiểu giá trị về type; trả (True, value) hoặc (False, reason_code)."""
    if type in ("string", "email"):
        if not isinstance(value, str):
            return False, "invalid_type"
        if strip:
            value = value.strip()
        if type == "email" and not _EMAIL_RE.match(value):
            return False, "invalid_email"
        return True, value

    if type == "boolean":
        if isinstance(value, bool):
            return True, value
        if isinstance(value, str):
            low = value.strip().lower()
            if low in _TRUE:
                return True, True
            if low in _FALSE:
                return True, False
        return False, "invalid_type"

    if type == "integer":
        # Tránh bool (bool là sub-class của int) bị nhận nhầm.
        if isinstance(value, bool):
            return False, "invalid_type"
        if isinstance(value, int):
            return True, value
        if isinstance(value, str) and re.fullmatch(r"[+-]?\d+", value.strip()):
            return True, int(value.strip())
        return False, "invalid_type"

    if type == "number":
        if isinstance(value, bool):
            return False, "invalid_type"
        if isinstance(value, (int, float)):
            return True, float(value)
        if isinstance(value, str):
            try:
                return True, float(value.strip())
            except ValueError:
                return False, "invalid_type"
        return False, "invalid_type"

    return False, "unknown_type"


def _run(schema, source):
    cleaned, errors = {}, {}
    for name, field in schema.items():
        present = name in source
        ok, result = field.process(present, source.get(name))
        if not ok:
            errors[name] = result
        elif result is not _MISSING:
            cleaned[name] = result
    return cleaned, errors


def validate_body(schema):
    """Validate JSON body của request theo schema; lưu kết quả vào g.validated_body."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            data = request.get_json(silent=True)
            if data is None:
                data = {}
            if not isinstance(data, dict):
                raise ValidationException(details={"_body": "must_be_object"})
            cleaned, errors = _run(schema, data)
            if errors:
                raise ValidationException(details=errors)
            g.validated_body = cleaned
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def validate_query(schema):
    """Validate query string theo schema; lưu kết quả vào g.validated_query."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            cleaned, errors = _run(schema, request.args.to_dict())
            if errors:
                raise ValidationException(details=errors)
            g.validated_query = cleaned
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def validated():
    """Lấy dữ liệu body đã được validate trong request hiện tại."""
    return getattr(g, "validated_body", {})


def validated_query():
    """Lấy dữ liệu query đã được validate trong request hiện tại."""
    return getattr(g, "validated_query", {})
