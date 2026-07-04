from ..extensions import db
from ..models.symptom import Symptom
from ..models.symptom_department_map import SymptomDepartmentMap


class SymptomRepository:
    def find_by_id(self, symptom_id):
        return db.session.get(Symptom, symptom_id)

    def find_by_code(self, code):
        return Symptom.query.filter_by(code=code).first()

    def paginate(self, page, size, category_id=None, is_active=None, department_id=None):
        query = Symptom.query
        if department_id is not None:
            query = query.join(
                SymptomDepartmentMap,
                SymptomDepartmentMap.symptom_id == Symptom.id,
            )
            query = query.filter(SymptomDepartmentMap.department_id == department_id)
        if category_id is not None:
            query = query.filter(Symptom.category_id == category_id)
        if is_active is not None:
            query = query.filter(Symptom.is_active == is_active)
        query = query.order_by(Symptom.code)
        total = query.count()
        items = query.offset((page - 1) * size).limit(size).all()
        return items, total

    def add(self, symptom):
        db.session.add(symptom)
        return symptom

    def commit(self):
        db.session.commit()
