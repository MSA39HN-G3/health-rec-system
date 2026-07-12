from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from ..extensions import db


def _now():
    return datetime.now(timezone.utc)


class Department(db.Model):
    """Khoa/Chuyên khoa.

    Thiết kế kèm các trường phục vụ AI/LLM gợi ý định tuyến bệnh nhân vào đúng
    khoa dựa trên triệu chứng:
      - keywords/conditions: dữ liệu CÓ CẤU TRÚC -> match nhanh theo triệu chứng/bệnh lý.
      - description: văn bản GIÀU NGỮ NGHĨA -> dùng cho semantic/embedding sau này.
    """

    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    # Mã khoa duy nhất (vd "CARDIO"). Dùng làm điểm tham chiếu ổn định.
    code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    # Vị trí của khoa (vd "Tầng 3, Tòa nhà A"). Tùy chọn.
    location = db.Column(db.String(255))
    # Ảnh đại diện của khoa.
    # Có 2 cách lưu:
    #  - `avatar_object_key`: key trong R2 sau khi upload (ưu tiên, dùng để sinh
    #    presigned GET mỗi lần trả response). Lưu DB thay vì URL để tránh URL hết hạn.
    #  - `avatar_url`: cache URL public (chỉ dùng khi bucket được public qua
    #    custom domain). Nếu không set thì BE tự derive từ `avatar_object_key`.
    avatar_object_key = db.Column(db.String(512))
    avatar_url = db.Column(db.String(512))
    # Danh mục các kĩ thuật chuyên môn của khoa (vd "Nội soi tiêu hóa", "Siêu âm tim").
    techniques = db.Column(ARRAY(db.String(255)), nullable=False, server_default="{}")

    # --- Trường phục vụ AI/LLM routing ---
    # Mô tả giàu thông tin (free-text), phù hợp để sinh embedding / semantic match.
    description = db.Column(db.Text)
    # Danh sách từ khóa/triệu chứng (structured tags) -> hỗ trợ GIN index + toán tử @>, &&.
    keywords = db.Column(ARRAY(db.String(64)), nullable=False, server_default="{}")
    # Danh sách bệnh lý/điều kiện điển hình của khoa.
    conditions = db.Column(ARRAY(db.String(128)), nullable=False, server_default="{}")
    # Metadata mở rộng phi cấu trúc (vd {"icd10": [...], "age_group": "adult"}).
    ai_metadata = db.Column(JSONB, nullable=False, server_default="{}")

    # Trưởng khoa cũ từng là user-id; sau refactor khái niệm này đã được bỏ
    # (staff quản lý tất cả bác sĩ thuộc khoa, không cần gắn một user/doctor
    # cụ thể làm "trưởng"). Xem migration 1a2b3c4d5e6f.

    is_active = db.Column(
        db.Boolean, default=True, nullable=False, server_default="true"
    )
    created_at = db.Column(db.DateTime(timezone=True), default=_now, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    def to_dict(self):
        from ..services.storage import presign_get

        avatar_object_key = self.avatar_object_key
        # Ưu tiên URL đã lưu (cache hoặc custom domain). Nếu không có thì
        # BE tự sinh presigned GET từ object_key để client hiển thị. Cache lại
        # để gọi API tiếp theo dùng ngay (vẫn có TTL 1 giờ ở URL).
        if not self.avatar_url and avatar_object_key:
            try:
                self.avatar_url = presign_get(avatar_object_key)
            except Exception:
                # Storage chưa cấu hình -> để None, FE xử lý fallback.
                self.avatar_url = None
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "location": self.location,
            "avatar_object_key": avatar_object_key,
            "avatar_url": self.avatar_url,
            "description": self.description,
            "keywords": list(self.keywords or []),
            "conditions": list(self.conditions or []),
            "techniques": list(self.techniques or []),
            "ai_metadata": self.ai_metadata or {},
            # `head_doctor` đã bỏ theo refactor 1a2b3c4d5e6f — staff giờ quản lý
            # tất cả bác sĩ trong khoa, không gắn một user/doctor cụ thể.
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
