"""Paper / live mode separation — new tables and column additions.

Adds user_trading_sessions, strategy_templates, strategy_instances,
user_broker_accounts, user_risk_limits, system_events tables.
Adds 'mode' column to capital_allocations, risk_events, trading_models.
Migrates existing strategies data into templates + instances.

Revision ID: 003_mode_sep
Revises: 002_copilot
Create Date: 2026-03-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "003_mode_sep"
down_revision = "002_copilot"
branch_labels = None
depends_on = None

# Re-use the existing tradingmodeenum — do NOT create it again.
trading_mode = sa.Enum(
    "backtest", "paper", "live",
    name="tradingmodeenum",
    create_type=False,
)

# New enum for system_events.event_type
system_event_type = sa.Enum(
    "mode_switch",
    "strategy_promoted",
    "trade_executed",
    "trade_failed",
    "account_sync",
    "risk_limit_triggered",
    "kill_switch_toggled",
    "bot_enabled",
    "bot_disabled",
    name="systemeventtype",
)


def upgrade() -> None:
    # ── Create new enum type ─────────────────────────────────────────────
    system_event_type.create(op.get_bind(), checkfirst=True)

    # ── 1. user_trading_sessions ─────────────────────────────────────────
    op.create_table(
        "user_trading_sessions",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("active_mode", trading_mode, nullable=False, server_default="paper"),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── 2. strategy_templates ────────────────────────────────────────────
    op.create_table(
        "strategy_templates",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("conditions", sa.JSON, nullable=False),
        sa.Column("action", sa.String(16), nullable=False, server_default="BUY"),
        sa.Column("stop_loss_pct", sa.Float, server_default="0.02"),
        sa.Column("take_profit_pct", sa.Float, server_default="0.05"),
        sa.Column("timeframe", sa.String(16), server_default="1D"),
        sa.Column("diagnostics", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_strategy_template_user", "strategy_templates", ["user_id"])

    # ── 3. strategy_instances ────────────────────────────────────────────
    op.create_table(
        "strategy_instances",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "template_id",
            sa.Integer,
            sa.ForeignKey("strategy_templates.id"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("mode", trading_mode, nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("position_size_pct", sa.Float, server_default="0.1"),
        sa.Column("max_position_value", sa.Float, nullable=True),
        sa.Column("nickname", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column(
            "promoted_from_id",
            sa.Integer,
            sa.ForeignKey("strategy_instances.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_strategy_instance_user_mode",
        "strategy_instances",
        ["user_id", "mode"],
    )

    # ── 4. user_broker_accounts ──────────────────────────────────────────
    op.create_table(
        "user_broker_accounts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "connection_id",
            sa.Integer,
            sa.ForeignKey("user_api_connections.id"),
            nullable=False,
        ),
        sa.Column("broker_account_id", sa.String(128), nullable=False),
        sa.Column("account_type", sa.String(64), nullable=False),
        sa.Column("nickname", sa.String(128), nullable=True),
        sa.Column("discovered_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_user_broker_acct_user_type",
        "user_broker_accounts",
        ["user_id", "account_type"],
    )

    # ── 5. user_risk_limits (composite PK: user_id + mode) ──────────────
    op.create_table(
        "user_risk_limits",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("mode", trading_mode, primary_key=True),
        sa.Column("daily_loss_limit", sa.Float, nullable=True),
        sa.Column("max_position_size_pct", sa.Float, server_default="0.25"),
        sa.Column("max_open_positions", sa.Integer, server_default="10"),
        sa.Column("kill_switch_active", sa.Boolean, server_default=sa.text("false")),
        sa.Column(
            "live_bot_trading_confirmed",
            sa.Boolean,
            server_default=sa.text("false"),
        ),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── 6. system_events ─────────────────────────────────────────────────
    op.create_table(
        "system_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_type", system_event_type, nullable=False),
        sa.Column("mode", trading_mode, nullable=True),
        sa.Column("severity", sa.String(32), server_default="info"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("metadata_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_system_events_user_time", "system_events", ["user_id", "created_at"]
    )
    op.create_index("ix_system_events_type", "system_events", ["event_type"])

    # ── Add mode column to existing tables ───────────────────────────────
    # Pattern: add nullable → backfill → set NOT NULL

    # capital_allocations
    op.add_column(
        "capital_allocations",
        sa.Column("mode", trading_mode, nullable=True),
    )
    op.execute("UPDATE capital_allocations SET mode = 'paper' WHERE mode IS NULL")
    op.alter_column("capital_allocations", "mode", nullable=False)

    # risk_events
    op.add_column(
        "risk_events",
        sa.Column("mode", trading_mode, nullable=True),
    )
    op.execute("UPDATE risk_events SET mode = 'paper' WHERE mode IS NULL")
    op.alter_column("risk_events", "mode", nullable=False)

    # trading_models
    op.add_column(
        "trading_models",
        sa.Column("mode", trading_mode, nullable=True),
    )
    op.execute("UPDATE trading_models SET mode = 'paper' WHERE mode IS NULL")
    op.alter_column("trading_models", "mode", nullable=False)

    # ── Data migration: strategies → strategy_templates + strategy_instances
    # The strategies table may be empty — these INSERTs are safe either way.
    op.execute(
        """
        INSERT INTO strategy_templates
            (id, user_id, name, description, conditions, action,
             stop_loss_pct, take_profit_pct, timeframe, diagnostics,
             created_at, updated_at)
        SELECT
            id, user_id, name, description, conditions, action,
            stop_loss_pct, take_profit_pct, timeframe, diagnostics,
            created_at, updated_at
        FROM strategies
        WHERE user_id IS NOT NULL
        """
    )

    op.execute(
        """
        INSERT INTO strategy_instances
            (template_id, user_id, mode, is_active, position_size_pct, nickname, created_at)
        SELECT
            id, user_id, 'paper', true, position_size_pct, name, created_at
        FROM strategies
        WHERE user_id IS NOT NULL
        """
    )

    # ── Default user_trading_sessions for existing users ─────────────────
    op.execute(
        """
        INSERT INTO user_trading_sessions (user_id, active_mode)
        SELECT id, 'paper'
        FROM users
        """
    )


def downgrade() -> None:
    # ── Remove added columns ─────────────────────────────────────────────
    op.drop_column("trading_models", "mode")
    op.drop_column("risk_events", "mode")
    op.drop_column("capital_allocations", "mode")

    # ── Drop new tables (reverse dependency order) ───────────────────────
    op.drop_table("system_events")
    op.drop_table("user_risk_limits")
    op.drop_table("user_broker_accounts")
    op.drop_table("strategy_instances")
    op.drop_table("strategy_templates")
    op.drop_table("user_trading_sessions")

    # ── Drop new enum type ───────────────────────────────────────────────
    sa.Enum(name="systemeventtype").drop(op.get_bind(), checkfirst=True)
