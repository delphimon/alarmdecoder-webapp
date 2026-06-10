from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("data_json", sa.Text(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_events_timestamp", "events", ["timestamp"])
    op.create_index("ix_events_type", "events", ["type"])
    op.create_table(
        "raw_messages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw", sa.Text(), nullable=False),
    )
    op.create_index("ix_raw_messages_timestamp", "raw_messages", ["timestamp"])
    op.create_table(
        "zones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=120), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False, server_default=""),
    )
    op.create_table(
        "notification_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("config_json", sa.Text(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_notification_settings_provider", "notification_settings", ["provider"])
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(length=128), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="viewer"),
        sa.Column("disabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False, server_default="system"),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_audit_log_timestamp", "audit_log", ["timestamp"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("users")
    op.drop_table("notification_settings")
    op.drop_table("app_settings")
    op.drop_table("zones")
    op.drop_table("raw_messages")
    op.drop_table("events")
