"""Repository layer for DoctorDocument model."""
from ..extensions import db
from ..models.doctor_document import DoctorDocument


class DoctorDocumentRepository:
    def find_by_id(self, document_id):
        return db.session.get(DoctorDocument, document_id)

    def find_by_doctor_id(self, doctor_id, document_type=None):
        """Lấy tất cả tài liệu của một bác sĩ.

        Args:
            doctor_id: ID của bác sĩ
            document_type: Lọc theo loại tài liệu (tùy chọn)

        Returns:
            list: Danh sách DoctorDocument
        """
        query = DoctorDocument.query.filter_by(doctor_id=doctor_id)
        if document_type:
            query = query.filter_by(document_type=document_type)
        return query.order_by(DoctorDocument.created_at.desc()).all()

    def find_by_type(self, doctor_id, document_type):
        """Lấy tài liệu theo loại của bác sĩ (ví dụ: giấy phép hành nghề)."""
        return DoctorDocument.query.filter_by(
            doctor_id=doctor_id,
            document_type=document_type,
        ).first()

    def find_expiring_documents(self, days=30):
        """Tìm các tài liệu sắp hết hạn."""
        from datetime import date
        future_date = date.today() + __import__("datetime").timedelta(days=days)
        return DoctorDocument.query.filter(
            DoctorDocument.expiry_date.isnot(None),
            DoctorDocument.expiry_date <= future_date,
            DoctorDocument.expiry_date >= date.today(),
        ).all()

    def find_unverified_documents(self):
        """Tìm các tài liệu chưa được xác minh."""
        return DoctorDocument.query.filter_by(is_verified=False).all()

    def paginate_by_doctor(self, doctor_id, page, size):
        """Lấy tài liệu của bác sĩ có phân trang."""
        query = DoctorDocument.query.filter_by(doctor_id=doctor_id)
        total = query.count()
        items = query.order_by(DoctorDocument.created_at.desc()).offset((page - 1) * size).limit(size).all()
        return items, total

    def add(self, document):
        db.session.add(document)
        return document

    def update(self, document):
        db.session.add(document)
        db.session.commit()
        return document

    def delete(self, document):
        db.session.delete(document)
        db.session.commit()

    def commit(self):
        db.session.commit()

    def rollback(self):
        db.session.rollback()
