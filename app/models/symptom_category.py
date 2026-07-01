from ..extensions import db


class SymptomCategory(db.Model):
    __tablename__ = "symptom_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)

    symptoms = db.relationship("Symptom", back_populates="category", lazy="select")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
        }
