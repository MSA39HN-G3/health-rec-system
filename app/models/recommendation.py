from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from ..extensions import db


def _now():
    return datetime.now(timezone.utc)


class Recommendation(db.Model):
    """Lưu trữ lịch sử lượt phân tích triệu chứng và gợi ý chuyên khoa (Thống kê gợi ý AI)."""

    __tablename__ = "recommendations"

    id = db.Column(db.Integer, primary_key=True)
    symptoms = db.Column(ARRAY(db.String(255)), nullable=False)
    results = db.Column(JSONB, nullable=False)  # Lưu chi tiết mảng các gợi ý (specialty_id, specialty_name, score, explanation)
    created_at = db.Column(db.DateTime(timezone=True), default=_now, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "symptoms": list(self.symptoms or []),
            "results": self.results,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
