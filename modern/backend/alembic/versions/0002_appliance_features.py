from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_appliance_features"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "custom_buttons",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("owner_username", sa.String(length=128), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("command_value", sa.Text(), nullable=False),
        sa.Column("dangerous", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_custom_buttons_owner_username", "custom_buttons", ["owner_username"])
    op.create_table(
        "api_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False, unique=True),
        sa.Column("token_prefix", sa.String(length=16), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="viewer"),
        sa.Column("disabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_api_tokens_user_id", "api_tokens", ["user_id"])
    op.create_index("ix_api_tokens_token_hash", "api_tokens", ["token_hash"], unique=True)
    op.create_index("ix_api_tokens_token_prefix", "api_tokens", ["token_prefix"])


def downgrade() -> None:
    op.drop_table("api_tokens")
    op.drop_table("custom_buttons")
