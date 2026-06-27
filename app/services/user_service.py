"""Service quản lý user (dùng cho khu vực admin)."""
from ..errors import BadRequestException, NotFoundException
from ..repositories.role_repository import RoleRepository
from ..repositories.user_repository import UserRepository


class UserService:
    def __init__(self, user_repository=None, role_repository=None):
        self.users = user_repository or UserRepository()
        self.roles = role_repository or RoleRepository()

    def list_users(self, page, size):
        """Danh sách user phân trang. Trả về (items, total)."""
        return self.users.paginate(page, size)

    def get_user(self, user_id):
        user = self.users.find_by_id(user_id)
        if user is None:
            raise NotFoundException("errors.not_found")
        return user

    def add_role(self, user_id, role_name):
        """Gán thêm một role (theo tên) cho user."""
        user = self.get_user(user_id)
        role = self.roles.find_by_name(role_name)
        if role is None:
            raise NotFoundException("errors.role_not_found")
        if role not in user.roles:
            user.roles.append(role)
            self.users.commit()
        return user

    def set_active(self, user_id, is_active, acting_user_id=None):
        """Bật/tắt (disable) tài khoản user. Không cho tự vô hiệu hóa chính mình."""
        user = self.get_user(user_id)
        if not is_active and acting_user_id is not None and user.id == acting_user_id:
            raise BadRequestException("errors.cannot_disable_self")
        user.is_active = is_active
        self.users.commit()
        return user

    def remove_role(self, user_id, role_name):
        """Gỡ một role khỏi user."""
        user = self.get_user(user_id)
        role = self.roles.find_by_name(role_name)
        if role is not None and role in user.roles:
            user.roles.remove(role)
            self.users.commit()
        return user
