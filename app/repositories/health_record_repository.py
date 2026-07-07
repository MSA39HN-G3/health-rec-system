from ..extensions import db
from ..models.health_record import HealthRecord


class HealthRecordRepository:
    def find_by_id(self, record_id):
        return db.session.get(HealthRecord, record_id)

    def find_by_patient_and_id(self, patient_id, record_id):
        return (
            HealthRecord.query.filter(
                HealthRecord.patient_id == patient_id,
                HealthRecord.id == record_id,
            )
            .order_by(HealthRecord.id)
            .first()
        )

    def paginate_by_patient(self, page, size, patient_id):
        query = HealthRecord.query.filter(HealthRecord.patient_id == patient_id)
        query = query.order_by(HealthRecord.id)
        total = query.count()
        items = query.offset((page - 1) * size).limit(size).all()
        return items, total

    def add(self, record):
        db.session.add(record)
        return record

    def commit(self):
        db.session.commit()
