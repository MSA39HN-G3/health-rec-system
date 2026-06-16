"""Service nghiệp vụ cho đăng nhập.

Điều phối luồng OAuth: gọi gateway Google (google_oauth) để lấy/verify thông tin,
rồi dùng repository để tạo/cập nhật user. Controller chỉ gọi vào đây, không biết
chi tiết Google hay DB.
"""
from ..errors import UnauthorizedException
from ..models.user import User
from ..repositories.user_repository import UserRepository
from . import google_oauth


class AuthService:
    def __init__(self, user_repository=None):
        # Cho phép truyền repository khác vào (hữu ích khi viết test).
        self.users = user_repository or UserRepository()

    def build_google_login(self):
        """Sinh URL đăng nhập Google kèm `state` để FE redirect."""
        state = google_oauth.generate_state()
        auth_url = google_oauth.build_authorization_url(state)
        return {"auth_url": auth_url, "state": state}

    def login_with_google(self, authorization_code):
        """Đổi code lấy token, verify với Google, rồi tạo/cập nhật user trong DB."""
        tokens = google_oauth.exchange_code_for_tokens(authorization_code)

        id_token_str = tokens.get("id_token")
        if not id_token_str:
            raise UnauthorizedException("errors.google_token_invalid")
        claims = google_oauth.verify_id_token(id_token_str)

        user = self.users.find_by_google_sub(claims["sub"])
        if user is None:
            user = User(google_sub=claims["sub"])
            self.users.add(user)

        user.apply_google_claims(claims)
        self.users.commit()
        return user
