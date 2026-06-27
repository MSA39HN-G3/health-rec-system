from ..extensions import db
from ..models.user import User


class UserRepository:
    def find_by_id(self, user_id):
        return db.session.get(User, user_id)

    def find_by_google_sub(self, google_sub):
        return User.query.filter_by(google_sub=google_sub).first()

    def find_by_email(self, email):
        return User.query.filter_by(email=email).first()

    def paginate(self, page, size):
        """Lấy danh sách user theo trang. Trả về (items, total)."""
        query = User.query.order_by(User.id)
        total = query.count()
        items = query.offset((page - 1) * size).limit(size).all()
        return items, total

    def add(self, user):
        db.session.add(user)
        return user

    def commit(self):
        db.session.commit()
