from ..extensions import db
from ..models.symptom_category import SymptomCategory


class SymptomCategoryRepository:
    def find_by_id(self, category_id):
        return db.session.get(SymptomCategory, category_id)

    def find_all(self):
        return SymptomCategory.query.order_by(SymptomCategory.name).all()

    def add(self, category):
        db.session.add(category)
        return category

    def delete(self, category):
        db.session.delete(category)

    def commit(self):
        db.session.commit()
