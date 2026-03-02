"""Initial schema — all trading ecosystem tables.

Revision ID: 001_initial
Revises:
Create Date: 2026-03-02
"""

from alembic import op
import sqlalchemy as sa

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- trading_models (referenced by trades, model_performance, capital_allocations, risk_events) --
    op.create_table(
        "trading_models",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), unique=True, nullable=False),
        sa.Column("model_type", sa.String(64), nullable=False),
        sa.Column("version", sa.String(32), server_default="1.0.0"),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("parameters", sa.JSON, server_default=sa.text("'{}'")),
        sa.Column("artifact_path", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # -- users (referenced by email_verifications, broker_credentials, paper_portfolios, etc.) --
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("is_admin", sa.Boolean, server_default=sa.text("false")),
        sa.Column("email_verified", sa.Boolean, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # -- trades --
    trade_direction = sa.Enum("long", "short", name="tradedirection")
    trade_status = sa.Enum(
        "pending", "filled", "partially_filled", "cancelled", "rejected",
        name="tradestatus",
    )
    trading_mode = sa.Enum("backtest", "paper", "live", name="tradingmodeenum")

    op.create_table(
        "trades",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("model_id", sa.Integer, sa.ForeignKey("trading_models.id"), nullable=False),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("direction", trade_direction, nullable=False),
        sa.Column("quantity", sa.Float, nullable=False),
        sa.Column("entry_price", sa.Float, nullable=True),
        sa.Column("exit_price", sa.Float, nullable=True),
        sa.Column("pnl", sa.Float, nullable=True),
        sa.Column("pnl_pct", sa.Float, nullable=True),
        sa.Column("status", trade_status, server_default="pending"),
        sa.Column("mode", trading_mode, nullable=False),
        sa.Column("order_id", sa.String(128), nullable=True),
        sa.Column("slippage", sa.Float, server_default="0.0"),
        sa.Column("commission", sa.Float, server_default="0.0"),
        sa.Column("entry_time", sa.DateTime, server_default=sa.func.now()),
        sa.Column("exit_time", sa.DateTime, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
    )
    op.create_index("ix_trades_symbol_time", "trades", ["symbol", "entry_time"])
    op.create_index("ix_trades_model_status", "trades", ["model_id", "status"])

    # -- model_performance --
    op.create_table(
        "model_performance",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("model_id", sa.Integer, sa.ForeignKey("trading_models.id"), nullable=False),
        sa.Column("timestamp", sa.DateTime, server_default=sa.func.now()),
        sa.Column("sharpe_ratio", sa.Float, nullable=True),
        sa.Column("sortino_ratio", sa.Float, nullable=True),
        sa.Column("win_rate", sa.Float, nullable=True),
        sa.Column("profit_factor", sa.Float, nullable=True),
        sa.Column("max_drawdown", sa.Float, nullable=True),
        sa.Column("total_return", sa.Float, nullable=True),
        sa.Column("num_trades", sa.Integer, server_default="0"),
        sa.Column("avg_trade_pnl", sa.Float, nullable=True),
        sa.Column("rolling_window_days", sa.Integer, server_default="30"),
        sa.Column("mode", trading_mode, nullable=False),
    )
    op.create_index("ix_perf_model_time", "model_performance", ["model_id", "timestamp"])

    # -- capital_allocations --
    op.create_table(
        "capital_allocations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("model_id", sa.Integer, sa.ForeignKey("trading_models.id"), nullable=False),
        sa.Column("timestamp", sa.DateTime, server_default=sa.func.now()),
        sa.Column("weight", sa.Float, nullable=False),
        sa.Column("allocated_capital", sa.Float, nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
    )
    op.create_index("ix_alloc_model_time", "capital_allocations", ["model_id", "timestamp"])

    # -- portfolio_snapshots --
    op.create_table(
        "portfolio_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime, server_default=sa.func.now()),
        sa.Column("total_equity", sa.Float, nullable=False),
        sa.Column("cash", sa.Float, nullable=False),
        sa.Column("positions_value", sa.Float, nullable=False),
        sa.Column("unrealized_pnl", sa.Float, nullable=False),
        sa.Column("realized_pnl", sa.Float, nullable=False),
        sa.Column("num_open_positions", sa.Integer, server_default="0"),
        sa.Column("exposure_pct", sa.Float, nullable=False),
        sa.Column("drawdown_pct", sa.Float, nullable=False),
        sa.Column("mode", trading_mode, nullable=False),
        sa.Column("positions_detail", sa.JSON, server_default=sa.text("'{}'")),
    )
    op.create_index("ix_portfolio_time", "portfolio_snapshots", ["timestamp"])

    # -- market_regimes --
    market_regime = sa.Enum(
        "low_vol_bull", "high_vol_bull", "low_vol_bear", "high_vol_bear", "sideways",
        name="marketregime",
    )
    op.create_table(
        "market_regimes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime, server_default=sa.func.now()),
        sa.Column("regime", market_regime, nullable=False),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("volatility_20d", sa.Float, nullable=True),
        sa.Column("trend_strength", sa.Float, nullable=True),
        sa.Column("metadata_json", sa.JSON, server_default=sa.text("'{}'")),
    )
    op.create_index("ix_regime_time", "market_regimes", ["timestamp"])

    # -- risk_events --
    risk_event_type = sa.Enum(
        "max_drawdown_breach", "position_limit_hit", "exposure_limit_hit",
        "stop_loss_triggered", "trade_frequency_limit", "manual_halt",
        name="riskeventtype",
    )
    op.create_table(
        "risk_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime, server_default=sa.func.now()),
        sa.Column("event_type", risk_event_type, nullable=False),
        sa.Column("severity", sa.String(16), server_default="warning"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("model_id", sa.Integer, sa.ForeignKey("trading_models.id"), nullable=True),
        sa.Column("action_taken", sa.Text, nullable=True),
        sa.Column("metadata_json", sa.JSON, server_default=sa.text("'{}'")),
    )
    op.create_index("ix_risk_event_time", "risk_events", ["timestamp"])

    # -- email_verifications --
    op.create_table(
        "email_verifications",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token", sa.String(255), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("used", sa.Boolean, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_email_verifications_token", "email_verifications", ["token"])

    # -- broker_credentials --
    broker_type = sa.Enum("alpaca", "webull", name="brokertype")
    op.create_table(
        "broker_credentials",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("broker_type", broker_type, nullable=False),
        sa.Column("encrypted_api_key", sa.Text, nullable=False),
        sa.Column("encrypted_api_secret", sa.Text, nullable=False),
        sa.Column("is_paper", sa.Boolean, server_default=sa.text("true")),
        sa.Column("nickname", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_broker_cred_user", "broker_credentials", ["user_id"])

    # -- paper_portfolios --
    op.create_table(
        "paper_portfolios",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), unique=True, nullable=False),
        sa.Column("cash", sa.Float, nullable=False, server_default="1000000.0"),
        sa.Column("initial_capital", sa.Float, nullable=False, server_default="1000000.0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # -- paper_positions --
    op.create_table(
        "paper_positions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("portfolio_id", sa.Integer, sa.ForeignKey("paper_portfolios.id"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("quantity", sa.Float, nullable=False),
        sa.Column("avg_entry_price", sa.Float, nullable=False),
        sa.Column("current_price", sa.Float, nullable=True),
        sa.Column("unrealized_pnl", sa.Float, nullable=True),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_paper_pos_user_symbol", "paper_positions", ["user_id", "symbol"], unique=True,
    )

    # -- paper_trades --
    paper_trade_status = sa.Enum("open", "closed", name="papertradestatus")
    op.create_table(
        "paper_trades",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("portfolio_id", sa.Integer, sa.ForeignKey("paper_portfolios.id"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("direction", trade_direction, nullable=False),
        sa.Column("quantity", sa.Float, nullable=False),
        sa.Column("entry_price", sa.Float, nullable=False),
        sa.Column("exit_price", sa.Float, nullable=True),
        sa.Column("pnl", sa.Float, nullable=True),
        sa.Column("status", paper_trade_status, server_default="open"),
        sa.Column("entry_time", sa.DateTime, server_default=sa.func.now()),
        sa.Column("exit_time", sa.DateTime, nullable=True),
    )
    op.create_index("ix_paper_trade_user", "paper_trades", ["user_id"])

    # -- strategies --
    op.create_table(
        "strategies",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("conditions", sa.JSON, nullable=False),
        sa.Column("action", sa.String(16), nullable=False, server_default="BUY"),
        sa.Column("stop_loss_pct", sa.Float, server_default="0.02"),
        sa.Column("take_profit_pct", sa.Float, server_default="0.05"),
        sa.Column("position_size_pct", sa.Float, server_default="0.1"),
        sa.Column("timeframe", sa.String(16), server_default="1D"),
        sa.Column("diagnostics", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_strategy_user", "strategies", ["user_id"])
    op.create_index("ix_strategy_name", "strategies", ["name"])


def downgrade() -> None:
    op.drop_table("strategies")
    op.drop_table("paper_trades")
    op.drop_table("paper_positions")
    op.drop_table("paper_portfolios")
    op.drop_table("broker_credentials")
    op.drop_table("email_verifications")
    op.drop_table("risk_events")
    op.drop_table("market_regimes")
    op.drop_table("portfolio_snapshots")
    op.drop_table("capital_allocations")
    op.drop_table("model_performance")
    op.drop_table("trades")
    op.drop_table("users")
    op.drop_table("trading_models")

    # Drop enum types
    sa.Enum(name="papertradestatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="brokertype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="riskeventtype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="marketregime").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="tradingmodeenum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="tradestatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="tradedirection").drop(op.get_bind(), checkfirst=True)
