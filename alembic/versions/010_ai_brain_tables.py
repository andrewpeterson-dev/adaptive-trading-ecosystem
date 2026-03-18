"""AI Brain: ai_brain_config, bot_model_performance, ai_trade_reasoning

Revision ID: 010_ai_brain
Revises: 009
Create Date: 2026-03-18
"""

revision = "010_ai_brain"
down_revision = "009"

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column("cerberus_bots", sa.Column("ai_brain_config", sa.JSON, nullable=True))

    op.create_table(
        "bot_model_performance",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("bot_id", sa.String(36), sa.ForeignKey("cerberus_bots.id"), nullable=False),
        sa.Column("cerberus_trade_id", sa.String(36), sa.ForeignKey("cerberus_trades.id"), nullable=True),
        sa.Column("model_used", sa.String(64), nullable=False),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("action", sa.String(8), nullable=False),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("reasoning_summary", sa.Text, nullable=True),
        sa.Column("entry_price", sa.Float, nullable=True),
        sa.Column("exit_price", sa.Float, nullable=True),
        sa.Column("pnl", sa.Float, nullable=True),
        sa.Column("is_shadow", sa.Boolean, default=False),
        sa.Column("decided_at", sa.DateTime, nullable=False),
        sa.Column("resolved_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_bmp_bot_model", "bot_model_performance", ["bot_id", "model_used"])
    op.create_index("ix_bmp_bot_resolved", "bot_model_performance", ["bot_id", "resolved_at"])

    op.create_table(
        "ai_trade_reasoning",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("performance_id", sa.String(36), sa.ForeignKey("bot_model_performance.id"), nullable=False),
        sa.Column("node_name", sa.String(64), nullable=False),
        sa.Column("node_output", sa.JSON, nullable=True),
        sa.Column("model_used", sa.String(64), nullable=True),
        sa.Column("tokens_used", sa.Integer, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime),
    )


def downgrade():
    op.drop_table("ai_trade_reasoning")
    op.drop_index("ix_bmp_bot_resolved", "bot_model_performance")
    op.drop_index("ix_bmp_bot_model", "bot_model_performance")
    op.drop_table("bot_model_performance")
    op.drop_column("cerberus_bots", "ai_brain_config")
