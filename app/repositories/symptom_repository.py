from ..extensions import db
from ..models.symptom import Symptom


class SymptomRepository:
    def find_by_id(self, symptom_id):
        return db.session.get(Symptom, symptom_id)

    def find_by_code(self, code):
        return Symptom.query.filter_by(code=code).first()

    def paginate(self, page, size, category_id=None, is_active=None):
        query = Symptom.query
        if category_id is not None:
            query = query.filter_by(category_id=category_id)
        if is_active is not None:
            query = query.filter_by(is_active=is_active)
        query = query.order_by(Symptom.code)
        total = query.count()
        items = query.offset((page - 1) * size).limit(size).all()
        return items, total

    def add(self, symptom):
        db.session.add(symptom)
        return symptom

    def commit(self):
        db.session.commit()
