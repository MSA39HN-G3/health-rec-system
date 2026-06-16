from ..extensions import db
from ..models.user import User


class UserRepository:
    def find_by_google_sub(self, google_sub):
        return User.query.filter_by(google_sub=google_sub).first()

    def find_by_email(self, email):
        return User.query.filter_by(email=email).first()

    def add(self, user):
        db.session.add(user)
        return user

    def commit(self):
        db.session.commit()
