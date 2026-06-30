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

    # --- Trường phục vụ AI/LLM routing ---
    # Mô tả giàu thông tin (free-text), phù hợp để sinh embedding / semantic match.
    description = db.Column(db.Text)
    # Danh sách từ khóa/triệu chứng (structured tags) -> hỗ trợ GIN index + toán tử @>, &&.
    keywords = db.Column(ARRAY(db.String(64)), nullable=False, server_default="{}")
    # Danh sách bệnh lý/điều kiện điển hình của khoa.
    conditions = db.Column(ARRAY(db.String(128)), nullable=False, server_default="{}")
    # Metadata mở rộng phi cấu trúc (vd {"icd10": [...], "age_group": "adult"}).
    ai_metadata = db.Column(JSONB, nullable=False, server_default="{}")

    # Trưởng khoa (tùy chọn) - FK tới users. SET NULL khi user bị xóa.
    head_doctor_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    head_doctor = db.relationship("User", foreign_keys=[head_doctor_id], lazy="joined")

    is_active = db.Column(
        db.Boolean, default=True, nullable=False, server_default="true"
    )
    created_at = db.Column(db.DateTime(timezone=True), default=_now, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "keywords": list(self.keywords or []),
            "conditions": list(self.conditions or []),
            "ai_metadata": self.ai_metadata or {},
            "head_doctor_id": self.head_doctor_id,
            "head_doctor": (
                {"id": self.head_doctor.id, "full_name": self.head_doctor.full_name}
                if self.head_doctor
                else None
            ),
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
