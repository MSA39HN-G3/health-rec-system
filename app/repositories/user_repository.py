from ..extensions import db
from ..models.rbac import Role, user_roles
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

    def search(self, keyword, page, size):
        """Tìm kiếm user theo từ khóa (tìm trong email, full_name).

        Trả về (items, total).
        """
        q = User.query.filter(
            db.or_(
                User.email.ilike(f"%{keyword}%"),
                User.full_name.ilike(f"%{keyword}%"),
            )
        ).order_by(User.id)

        total = q.count()
        items = q.offset((page - 1) * size).limit(size).all()
        return items, total

    def filter(
        self,
        page,
        size,
        role=None,
        is_active=None,
    ):
        """Lọc user theo role và/hoặc is_active.

        Args:
            role: Lọc user có role này (tên role, ví dụ "admin").
            is_active: Lọc theo trạng thái tài khoản.

        Trả về (items, total).
        """
        q = User.query.order_by(User.id)

        if role is not None:
            q = q.filter(User.roles.any(Role.name.ilike(role)))

        if is_active is not None:
            q = q.filter(User.is_active == is_active)

        total = q.count()
        items = q.offset((page - 1) * size).limit(size).all()
        return items, total

    def add(self, user):
        db.session.add(user)
        return user

    def commit(self):
        db.session.commit()
