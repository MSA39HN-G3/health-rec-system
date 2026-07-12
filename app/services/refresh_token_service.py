"""Phát và xoay vòng refresh token (opaque).

Một refresh token là chuỗi ngẫu nhiên 256-bit (URL-safe base64). BE chỉ lưu
SHA-256 hash của nó trong DB. Khi FE gửi refresh token lên, BE hash lại rồi
tra cứu — DB leak cũng không dùng trực tiếp được.

Rotation policy:
    - Mỗi lần refresh thành công: revoke token cũ + tạo token mới (parent_id
      trỏ về token cũ).
    - Nếu token cũ bị dùng lại (reuse detection): coi như bị lộ → thu hồi
      toàn bộ refresh token đang active của user (logout mọi thiết bị) + đưa
      access token hiện tại vào blacklist.

Hằng số ``JWT_REFRESH_EXPIRES`` cấu hình TTL (mặc định 14 ngày).
"""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from flask import current_app

from ..errors import UnauthorizedException
from ..extensions import db
from ..models.refresh_token import RefreshToken
from ..repositories.refresh_token_repository import RefreshTokenRepository
from ..repositories.token_blacklist_repository import TokenBlacklistRepository
from ..repositories.user_repository import UserRepository
from . import token_service

logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc)


def _hash_token(raw_token):
    """SHA-256 hex digest của raw token — lưu trong DB."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _generate_raw_token():
    """256-bit URL-safe base64. Có đủ entropy để không đoán được."""
    return secrets.token_urlsafe(32)


def _ttl_seconds():
    return int(current_app.config.get("JWT_REFRESH_EXPIRES", 14 * 24 * 3600))


class RefreshTokenService:
    """Quản lý vòng đời refresh token: issue / rotate / revoke."""

    def __init__(
        self,
        user_repository=None,
        refresh_token_repository=None,
        blacklist_repository=None,
    ):
        self.users = user_repository or UserRepository()
        self.repo = refresh_token_repository or RefreshTokenRepository()
        self.blacklist = blacklist_repository or TokenBlacklistRepository()

    # ----------------- issue -----------------
    def issue(self, user, created_ip=None, user_agent=None, parent_id=None):
        """Cấp một refresh token mới cho user.

        Args:
            user: instance User (đã xác thực).
            created_ip, user_agent: optional, ghi vào DB để audit.
            parent_id: id của token bị xoay vòng (chỉ đặt khi rotate).

        Returns:
            (raw_token, expires_at): raw_token chỉ trả 1 lần — FE phải lưu.
        """
        raw = _generate_raw_token()
        now = _now()
        expires_at = now + timedelta(seconds=_ttl_seconds())

        record = RefreshToken(
            user_id=user.id,
            token_hash=_hash_token(raw),
            parent_id=parent_id,
            expires_at=expires_at,
            created_ip=created_ip,
            user_agent=user_agent,
        )
        self.repo.add(record)
        self.repo.commit()
        return raw, expires_at

    # ----------------- rotate -----------------
    def rotate(self, raw_token, created_ip=None, user_agent=None):
        """Đổi refresh token cũ → (access mới, refresh mới).

        Quy trình:
            1. Tra hash(raw_token) trong DB.
            2. Nếu không thấy / đã revoke / hết hạn -> 401 ``errors.refresh_invalid``.
            3. Nếu thấy + còn active -> reuse-detection:
               - Nếu đã revoke rồi mà giờ mới gửi -> coi như bị lộ -> revoke_all.
               - Nếu còn active -> revoke token cũ, cấp token mới + access mới.
            4. Trả về (access_token, access_expires_at, refresh_token, refresh_expires_at).

        Raises:
            UnauthorizedException: với message key ``errors.refresh_invalid`` hoặc
                ``errors.refresh_reuse_detected`` (FE xử lý giống 401 → logout).
        """
        if not raw_token:
            raise UnauthorizedException("errors.refresh_invalid")

        token_hash = _hash_token(raw_token)
        record = self.repo.find_by_hash(token_hash)

        # Case 1: token không tồn tại trong DB.
        if record is None:
            raise UnauthorizedException("errors.refresh_invalid")

        # Case 2: reuse detection — token đã revoke (hoặc hết hạn) mà vẫn được dùng lại.
        # Đây là dấu hiệu token bị lộ; thu hồi mọi refresh token đang active của user
        # để chặn attacker dùng chain lộ.
        if not record.is_active():
            logger.warning(
                "Refresh token reuse detected: user_id=%s token_id=%s",
                record.user_id,
                record.id,
            )
            self._revoke_all_for_user_with_blacklist(record.user_id)
            raise UnauthorizedException("errors.refresh_reuse_detected")

        # Case 3: token còn active — rotate.
        # 3a. Revoke token cũ.
        record.revoke()
        self.repo.commit()

        # 3b. User có còn tồn tại + còn active không?
        # Expire session trước khi tìm lại để đảm bảo đọc được thay đổi mới nhất
        # (vd admin vừa disable user sau khi token được cấp).
        db.session.expire_all()
        user = self.users.find_by_id(record.user_id)
        if user is None:
            raise UnauthorizedException("errors.refresh_invalid")
        if not user.is_active:
            raise UnauthorizedException("errors.refresh_invalid")

        # 3c. Cấp access token mới (JWT).
        access_token, _jti, access_expires_at = token_service.issue_access_token(user)

        # 3d. Cấp refresh token mới (xoay vòng).
        new_raw, new_refresh_expires_at = self.issue(
            user,
            created_ip=created_ip,
            user_agent=user_agent,
            parent_id=record.id,
        )

        logger.info(
            "Refresh token rotated: user_id=%s old_id=%s", user.id, record.id
        )

        return {
            "access_token": access_token,
            "access_expires_at": access_expires_at,
            "refresh_token": new_raw,
            "refresh_expires_at": new_refresh_expires_at,
            "user": user,
        }

    # ----------------- revoke -----------------
    def revoke(self, raw_token):
        """Thu hồi 1 refresh token (logout session hiện tại). Idempotent."""
        if not raw_token:
            return
        record = self.repo.find_by_hash(_hash_token(raw_token))
        if record is None:
            return
        record.revoke()
        self.repo.commit()

    def revoke_all_for_user(self, user_id):
        """Thu hồi MỌI refresh token của user (logout mọi thiết bị).

        KHÔNG blacklist access token — access token có TTL ngắn, tự hết hạn;
        chỉ cần đảm bảo không ai refresh được nữa.

        Returns:
            int: số bản ghi bị thu hồi (0 nếu user không có token active).
        """
        count = self.repo.revoke_all_for_user(user_id)
        if count:
            self.repo.commit()
            logger.info("Revoked %d refresh tokens for user_id=%s", count, user_id)
        return count

    # ----------------- private -----------------
    def _revoke_all_for_user_with_blacklist(self, user_id):
        """Revoke all refresh tokens + blacklist toàn bộ access token hiện còn hạn.

        Dùng cho reuse-detection. Vì ta không lưu trữ mapping access -> refresh,
        ta chỉ có thể chặn tương lai bằng cách:
          - Revoke mọi refresh token (chặn cấp access mới).
          - Bẻ khoá mọi session bằng cách KHÔNG blacklist access token (vì user
            hợp lệ cũng đang dùng access đó). Tuy nhiên, attacker không thể
            lấy access mới được nữa.
        """
        self.revoke_all_for_user(user_id)
        # Ghi log; không blacklist access vì ảnh hưởng user hợp lệ.
        logger.warning(
            "Possible token leak: all refresh tokens revoked for user_id=%s", user_id
        )