"""Add auto_route_enabled to cerberus_bots

Revision ID: 011_auto_routing
Revises: 010_ai_brain
Create Date: 2026-03-23
"""

revision = "011_auto_routing"
down_revision = "010_ai_brain"

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column(
        "cerberus_bots",
        sa.Column("auto_route_enabled", sa.Boolean, server_default=sa.text("false"), nullable=False),
    )


def downgrade():
    op.drop_column("cerberus_bots", "auto_route_enabled")
