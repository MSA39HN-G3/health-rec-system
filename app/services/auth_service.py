"""Service nghiệp vụ cho đăng nhập.

Điều phối luồng OAuth: gọi gateway Google (google_oauth) để lấy/verify thông tin,
rồi dùng repository để tạo/cập nhật user. Controller chỉ gọi vào đây, không biết
chi tiết Google hay DB.

State (chống CSRF):
    - build_google_login: lưu `state` (do FE gửi lên hoặc BE tự sinh) kèm hạn dùng,
      rồi nhúng vào URL redirect tới Google.
    - login_with_google: đối chiếu `state` nhận về với bản ghi đã lưu (còn hạn,
      chưa dùng) rồi đánh dấu đã dùng trước khi đổi token.
"""
import logging
from datetime import datetime, timedelta, timezone

from flask import current_app

from ..errors import ForbiddenException, UnauthorizedException
from ..models.user import User
from ..repositories.oauth_state_repository import OAuthStateRepository
from ..repositories.token_blacklist_repository import TokenBlacklistRepository
from ..repositories.user_repository import UserRepository
from . import google_oauth, token_service

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(
        self,
        user_repository=None,
        oauth_state_repository=None,
        token_blacklist_repository=None,
    ):
        # Cho phép truyền repository khác vào (hữu ích khi viết test).
        self.users = user_repository or UserRepository()
        self.oauth_states = oauth_state_repository or OAuthStateRepository()
        self.blacklist = token_blacklist_repository or TokenBlacklistRepository()

    def build_google_login(self, state=None):
        """Sinh URL đăng nhập Google kèm `state` để FE redirect.

        Nếu FE đã gửi `state` thì dùng lại, ngược lại BE tự sinh. State được lưu
        phía BE kèm thời điểm hết hạn để verify ở bước callback.
        """
        state = state or google_oauth.generate_state()

        ttl = current_app.config.get("GOOGLE_OAUTH_STATE_TTL", 600)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)
        self.oauth_states.save(state, expires_at)
        self.oauth_states.commit()

        auth_url = google_oauth.build_authorization_url(state)
        return {"auth_url": auth_url, "state": state}

    def login_with_google(self, authorization_code, state):
        """Verify state, đổi code lấy token, verify với Google, rồi đăng nhập/onboard user.

        Nếu user (theo Google `sub`) chưa có trong hệ thống thì tự tạo mới (onboard).
        Trả về (user, is_new) — is_new=True khi đây là lần đầu user đăng nhập.
        """
        record = self.oauth_states.find_by_state(state)
        if record is None or not record.is_usable():
            raise UnauthorizedException("errors.invalid_state")
        # State dùng một lần: đánh dấu đã dùng ngay sau khi xác thực.
        record.mark_used()
        self.oauth_states.commit()

        tokens = google_oauth.exchange_code_for_tokens(authorization_code)

        id_token_str = tokens.get("id_token")
        if not id_token_str:
            # Response đổi token không có id_token -> thường do thiếu scope "openid".
            raise UnauthorizedException(
                "errors.google_token_invalid", details={"reason": "missing_id_token"}
            )
        claims = google_oauth.verify_id_token(id_token_str)

        user = self.users.find_by_google_sub(claims["sub"])
        is_new = user is None
        if is_new:
            # Onboard: user lần đầu đăng nhập -> tạo bản ghi mới trong hệ thống.
            user = User(google_sub=claims["sub"])
            self.users.add(user)
        elif not user.is_active:
            # Tài khoản đã bị vô hiệu hóa -> không cho đăng nhập.
            raise ForbiddenException("errors.account_disabled")

        user.apply_google_claims(claims)
        self.users.commit()

        if is_new:
            logger.info(
                "Onboarded new user via Google: id=%s email=%s", user.id, user.email
            )
        return user, is_new

    def issue_token(self, user):
        """Cấp access token (JWT) cho user. Trả về (token, expires_at)."""
        token, _jti, expires_at = token_service.issue_access_token(user)
        return token, expires_at

    def logout(self, payload):
        """Thu hồi token hiện tại bằng cách đưa `jti` vào blacklist."""
        jti = payload.get("jti")
        if not jti:
            return
        exp = payload.get("exp")
        expires_at = (
            datetime.fromtimestamp(exp, tz=timezone.utc)
            if exp
            else datetime.now(timezone.utc)
        )
        if not self.blacklist.is_blacklisted(jti):
            self.blacklist.add(jti, expires_at)
            self.blacklist.commit()
            logger.info("Token revoked (logout): jti=%s user=%s", jti, payload.get("sub"))
