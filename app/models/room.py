from datetime import datetime, timezone
from sqlalchemy import Index
from ..extensions import db


def _now():
    return datetime.now(timezone.utc)


class Room(db.Model):
    """Phòng khám vật lý thuộc khoa.

    Phục vụ luồng chọn phòng khám thuộc khoa sau khi AI gợi ý và bệnh nhân chọn khoa.
    """

    __tablename__ = "rooms"

    id = db.Column(db.Integer, primary_key=True)
    # Mã phòng, duy nhất (vd 'P201').
    code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    # Tên phòng (vd 'Phòng khám Tim mạch 1').
    name = db.Column(db.String(255), nullable=False)
    # Chuyên khoa mà phòng trực thuộc.
    department_id = db.Column(
        db.Integer,
        db.ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Loại phòng: EXAMINATION | PROCEDURE | CONSULTATION | IMAGING | LAB.
    room_type = db.Column(
        db.String(64), nullable=False, default="EXAMINATION", server_default="'EXAMINATION'"
    )
    # Vị trí tòa nhà (vd 'Tòa A').
    building = db.Column(db.String(255))
    # Tầng (vd 'Tầng 2').
    floor = db.Column(db.String(255))
    # Sức chứa số bệnh nhân khám đồng thời.
    capacity = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    # Mô tả thêm.
    description = db.Column(db.Text)
    # Trạng thái vận hành: OPEN | FULL | CLOSED | MAINTENANCE.
    status = db.Column(
        db.String(32), nullable=False, default="OPEN", server_default="'OPEN'"
    )
    created_at = db.Column(db.DateTime(timezone=True), default=_now, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    department = db.relationship("Department", backref=db.backref("rooms", lazy="dynamic"))

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "department_id": self.department_id,
            "department": (
                {"id": self.department.id, "name": self.department.name, "code": self.department.code}
                if self.department
                else None
            ),
            "room_type": self.room_type,
            "building": self.building,
            "floor": self.floor,
            "capacity": self.capacity,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# Chỉ số tìm kiếm nhanh phòng khám đang mở thuộc khoa
Index("idx_rooms_dept_open", Room.department_id, postgresql_where=(Room.status == "OPEN"))

