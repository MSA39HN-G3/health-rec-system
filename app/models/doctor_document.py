"""Model DoctorDocument - Quản lý tài liệu của bác sĩ.

Lưu trữ các tài liệu như giấy phép hành nghề, bằng cấp, chứng chỉ, hợp đồng.
"""
from datetime import datetime, timezone

from ..extensions import db


def _now():
    return datetime.now(timezone.utc)


# Các loại tài liệu được hỗ trợ
DOCUMENT_TYPES = (
    "license",      # Giấy phép hành nghề
    "degree",       # Bằng cấp
    "certificate",   # Chứng chỉ
    "contract",     # Hợp đồng lao động
    "id_card",      # CCCD/CMND
    "other",        # Khác
)


class DoctorDocument(db.Model):
    __tablename__ = "doctor_documents"

    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(
        db.Integer,
        db.ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_type = db.Column(db.String(64), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    object_key = db.Column(db.String(512))  # Key trong R2/S3
    url = db.Column(db.String(512))  # Cache URL
    issue_date = db.Column(db.Date)  # Ngày cấp
    expiry_date = db.Column(db.Date)  # Ngày hết hạn
    is_verified = db.Column(
        db.Boolean, default=False, nullable=False, server_default="false"
    )
    created_at = db.Column(db.DateTime(timezone=True), default=_now, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=_now, onupdate=_now, nullable=True
    )

    def _get_url(self):
        """Lấy URL, ưu tiên cache hoặc generate presigned."""
        from ..services.storage import presign_get

        key = self.object_key
        if not self.url and key:
            try:
                self.url = presign_get(key)
            except Exception:
                self.url = None
        return self.url

    def is_expiring_soon(self, days=30):
        """Kiểm tra tài liệu có sắp hết hạn không."""
        if not self.expiry_date:
            return False
        from datetime import date
        return (self.expiry_date - date.today()).days <= days

    def to_dict(self):
        return {
            "id": self.id,
            "doctor_id": self.doctor_id,
            "document_type": self.document_type,
            "title": self.title,
            "object_key": self.object_key,
            "url": self._get_url(),
            "issue_date": self.issue_date.isoformat() if self.issue_date else None,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "is_verified": self.is_verified,
            "is_expiring_soon": self.is_expiring_soon(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
