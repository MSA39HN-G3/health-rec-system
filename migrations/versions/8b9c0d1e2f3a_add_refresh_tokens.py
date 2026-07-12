"""add refresh_tokens table

Bổ sung refresh token (opaque) cho phép FE tự làm mới access token mà không
phải đăng nhập lại qua Google OAuth.

Bảng ``refresh_tokens`` lưu **hash SHA-256** của token (chứ không phải raw
token) — nếu DB leak, attacker không dùng trực tiếp được. Mỗi token có
``expires_at`` (TTL cấu hình qua ``JWT_REFRESH_EXPIRES``), ``revoked_at``
(nullable, đánh dấu đã logout/thu hồi), và ``parent_id`` (chuỗi huyết thống
khi xoay vòng — phát hiện tái sử dụng).

Rotation (xoay vòng) là chiến lược bảo mật chính: mỗi lần refresh thành công
sẽ tạo refresh token mới và thu hồi token cũ. Nếu token cũ bị dùng lại
(reuse detection), toàn bộ chain của user bị thu hồi (logout mọi thiết bị).

Revision ID: 8b9c0d1e2f3a
Revises: 7a8b9c0d1e2f
Create Date: 2026-07-12 09:50:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8b9c0d1e2f3a"
down_revision = "7a8b9c0d1e2f"
branch_labels = None
depends_on = None


def upgrade():
    # SQLite cần INTEGER PRIMARY KEY cho autoincrement; Postgres thì BIGINT.
    bigint_pk = sa.BigInteger().with_variant(sa.Integer, "sqlite")

    op.create_table(
        "refresh_tokens",
        sa.Column("id", bigint_pk, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        # SHA-256 hex digest của raw token (64 ký tự). Index unique để tra cứu O(1).
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        # Chuỗi huyết thống: parent_id = id của token bị xoay vòng. Cho phép trace
        # lại toàn bộ chain khi reuse detection hoặc revoke toàn bộ.
        sa.Column("parent_id", bigint_pk, sa.ForeignKey("refresh_tokens.id", ondelete="SET NULL"), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        # IP/UA của session tạo token — audit/log/debug.
        sa.Column("created_ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"])
    op.create_index("ix_refresh_tokens_user_active", "refresh_tokens", ["user_id", "revoked_at"])


def downgrade():
    op.drop_index("ix_refresh_tokens_user_active", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_expires_at", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")