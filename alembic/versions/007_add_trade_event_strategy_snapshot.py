"""Add trade_events and strategy_snapshots tables for Quant Intelligence Layer.

Revision ID: 007
Revises: 006
Create Date: 2026-03-10
"""

from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "trade_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("strategy_id", sa.Integer, nullable=False, index=True),
        sa.Column("timestamp", sa.DateTime, nullable=False),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("entry_price", sa.Float, nullable=True),
        sa.Column("exit_price", sa.Float, nullable=True),
        sa.Column("entry_time", sa.DateTime, nullable=True),
        sa.Column("exit_time", sa.DateTime, nullable=True),
        sa.Column("pnl", sa.Float, nullable=True),
        sa.Column("pnl_pct", sa.Float, nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("regime", sa.String(32), nullable=True),
        sa.Column("signals_json", sa.JSON, nullable=True),
        sa.Column("approved", sa.Boolean, default=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("reasoning_text", sa.Text, nullable=True),
        sa.Column("model_name", sa.String(64), nullable=True),
    )
    op.create_index("ix_trade_events_strategy_time", "trade_events", ["strategy_id", "timestamp"])

    op.create_table(
        "strategy_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("strategy_id", sa.Integer, nullable=False, index=True),
        sa.Column("timestamp", sa.DateTime, nullable=False),
        sa.Column("equity", sa.Float, nullable=False),
        sa.Column("realized_pnl", sa.Float, nullable=True),
        sa.Column("num_trades", sa.Integer, default=0),
        sa.Column("win_rate", sa.Float, nullable=True),
        sa.Column("sharpe", sa.Float, nullable=True),
        sa.Column("max_drawdown", sa.Float, nullable=True),
        sa.Column("regime", sa.String(32), nullable=True),
        sa.Column("metrics_json", sa.JSON, nullable=True),
    )
    op.create_index(
        "ix_strategy_snapshot_strategy_time",
        "strategy_snapshots",
        ["strategy_id", "timestamp"],
    )


def downgrade():
    op.drop_index("ix_strategy_snapshot_strategy_time", "strategy_snapshots")
    op.drop_table("strategy_snapshots")
    op.drop_index("ix_trade_events_strategy_time", "trade_events")
    op.drop_table("trade_events")
