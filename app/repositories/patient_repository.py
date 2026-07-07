from ..extensions import db
from ..models.patient import Patient


class PatientRepository:
    def find_by_id(self, patient_id):
        return db.session.get(Patient, patient_id)

    def paginate(self, page, size):
        query = Patient.query.order_by(Patient.id)
        total = query.count()
        items = query.offset((page - 1) * size).limit(size).all()
        return items, total

    def add(self, patient):
        db.session.add(patient)
        return patient

    def count(self):
        return Patient.query.count()

    def commit(self):
        db.session.commit()
