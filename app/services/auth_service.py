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

import jwt
from flask import current_app

from ..errors import ForbiddenException, UnauthorizedException
from ..models.user import User
from ..repositories.oauth_state_repository import OAuthStateRepository
from ..repositories.token_blacklist_repository import TokenBlacklistRepository
from ..repositories.user_repository import UserRepository
from . import google_oauth, token_service
from .refresh_token_service import RefreshTokenService

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(
        self,
        user_repository=None,
        oauth_state_repository=None,
        token_blacklist_repository=None,
        refresh_token_service=None,
    ):
        # Cho phép truyền repository khác vào (hữu ích khi viết test).
        self.users = user_repository or UserRepository()
        self.oauth_states = oauth_state_repository or OAuthStateRepository()
        self.blacklist = token_blacklist_repository or TokenBlacklistRepository()
        self.refresh_tokens = refresh_token_service or RefreshTokenService()

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

    def issue_token(self, user, created_ip=None, user_agent=None):
        """Cấp cặp (access token, refresh token) cho user.

        Returns:
            dict gồm:
                - access_token (JWT, ngắn hạn)
                - access_expires_at (datetime)
                - refresh_token (opaque, dài hạn — chỉ trả 1 lần)
                - refresh_expires_at (datetime)
        """
        access_token, _jti, access_expires_at = token_service.issue_access_token(user)
        refresh_raw, refresh_expires_at = self.refresh_tokens.issue(
            user, created_ip=created_ip, user_agent=user_agent
        )
        return {
            "access_token": access_token,
            "access_expires_at": access_expires_at,
            "refresh_token": refresh_raw,
            "refresh_expires_at": refresh_expires_at,
        }

    def logout(self, payload):
        """Thu hồi access token hiện tại bằng cách đưa `jti` vào blacklist."""
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

    def refresh(self, raw_refresh_token, created_ip=None, user_agent=None):
        """Đổi refresh token lấy cặp (access mới, refresh mới).

        Wrapper cho ``RefreshTokenService.rotate`` — raise UnauthorizedException
        với key message tương ứng. Service khác không cần biết chi tiết.
        """
        return self.refresh_tokens.rotate(
            raw_refresh_token, created_ip=created_ip, user_agent=user_agent
        )

    def revoke_refresh_token(self, raw_refresh_token):
        """Thu hồi 1 refresh token (FE gửi kèm lúc logout)."""
        self.refresh_tokens.revoke(raw_refresh_token)

    def revoke_all_refresh_tokens(self, user_id):
        """Thu hồi MỌI refresh token của user (logout mọi thiết bị)."""
        self.refresh_tokens.revoke_all_for_user(user_id)

    def introspect_token(self, token):
        """Kiểm tra trạng thái token theo chuẩn OAuth 2.0 RFC 7662.

        Trả về dict với:
          - active: bool (token còn hiệu lực hay không)
          - sub, jti, type, iat, exp: claim của JWT (chỉ trả khi active=True)
          - user: thông tin user (chỉ trả khi active=True và user còn tồn tại)
        Lưu ý: KHÔNG bao giờ trả về giá trị của `active=False` cùng với claim nhạy cảm
        — chỉ xác nhận trạng thái "không active" (token không hợp lệ/hết hạn/bị thu hồi).
        """
        result = {"active": False}

        # Bước 1: decode + verify chữ ký + hạn dùng.
        try:
            payload = token_service.decode_token(token)
        except jwt.ExpiredSignatureError:
            result["reason"] = "expired"
            return result
        except jwt.InvalidTokenError:
            result["reason"] = "invalid"
            return result

        # Bước 2: kiểm tra blacklist (logout/thu hồi).
        jti = payload.get("jti")
        if jti and self.blacklist.is_blacklisted(jti):
            result["reason"] = "revoked"
            return result

        # Bước 3: lookup user + kiểm tra trạng thái tài khoản.
        sub = payload.get("sub")
        try:
            user_id = int(sub) if sub is not None else None
        except (TypeError, ValueError):
            user_id = None
        user = self.users.find_by_id(user_id) if user_id else None
        if user is None:
            result["reason"] = "user_not_found"
            return result

        # Token hợp lệ + user tồn tại + chưa bị thu hồi -> active.
        now_ts = int(datetime.now(timezone.utc).timestamp())
        result.update(
            {
                "active": True,
                "jti": jti,
                "sub": sub,
                "type": payload.get("type"),
                "iat": payload.get("iat"),
                "exp": payload.get("exp"),
                "expires_in": max(payload.get("exp", now_ts) - now_ts, 0),
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "is_active": user.is_active,
                    "roles": sorted(user.role_names()),
                    "permissions": sorted(user.permission_names()),
                },
            }
        )
        return result
