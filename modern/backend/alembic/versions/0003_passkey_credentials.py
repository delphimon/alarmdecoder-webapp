from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_passkey_credentials"
down_revision = "0002_appliance_features"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "passkey_credentials",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("username", sa.String(length=128), sa.ForeignKey("users.username", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False, server_default="Passkey"),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("sign_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("aaguid", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_passkey_credentials_username", "passkey_credentials", ["username"])


def downgrade() -> None:
    op.drop_table("passkey_credentials")
