"""Create 12 missing tables, fix paper_portfolios default, add missing columns and indexes.

Revision ID: 012_missing_tables_and_fixes
Revises: 011_auto_routing
Create Date: 2026-03-26
"""

revision = "012_missing_tables_and_fixes"
down_revision = "011_auto_routing"

from alembic import op
import sqlalchemy as sa


def upgrade():
    # ── Fix paper_portfolios server_default: 1000000 → 100000 ──────────
    with op.batch_alter_table("paper_portfolios") as batch_op:
        batch_op.alter_column("cash", server_default="100000.0")
        batch_op.alter_column("initial_capital", server_default="100000.0")

    # ── Add missing columns to cerberus_bot_versions ───────────────────
    op.add_column(
        "cerberus_bot_versions",
        sa.Column("universe_config", sa.JSON, default=dict),
    )
    op.add_column(
        "cerberus_bot_versions",
        sa.Column("override_level", sa.String(16), server_default="soft"),
    )

    # ── Add missing indexes on portfolio_snapshots ─────────────────────
    op.create_index("ix_portfolio_mode_time", "portfolio_snapshots", ["mode", "timestamp"])
    op.create_index("ix_portfolio_user_mode", "portfolio_snapshots", ["user_id", "mode"])

    # ── Create api_providers ───────────────────────────────────────────
    op.create_table(
        "api_providers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(32), unique=True, nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("api_type", sa.String(32), nullable=False),
        sa.Column("supports_trading", sa.Boolean, server_default=sa.text("false")),
        sa.Column("supports_paper", sa.Boolean, server_default=sa.text("false")),
        sa.Column("supports_market_data", sa.Boolean, server_default=sa.text("false")),
        sa.Column("supports_options", sa.Boolean, server_default=sa.text("false")),
        sa.Column("supports_crypto", sa.Boolean, server_default=sa.text("false")),
        sa.Column("supports_stocks", sa.Boolean, server_default=sa.text("true")),
        sa.Column("supports_order_placement", sa.Boolean, server_default=sa.text("false")),
        sa.Column("supports_positions_streaming", sa.Boolean, server_default=sa.text("false")),
        sa.Column("requires_secret", sa.Boolean, server_default=sa.text("true")),
        sa.Column("unified_mode", sa.Boolean, server_default=sa.text("false")),
        sa.Column("credential_note", sa.Text, nullable=True),
        sa.Column("credential_fields", sa.JSON, default=list),
        sa.Column("docs_url", sa.String(256), nullable=True),
        sa.Column("is_available", sa.Boolean, server_default=sa.text("true")),
    )

    # ── Create user_api_connections ────────────────────────────────────
    op.create_table(
        "user_api_connections",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider_id", sa.Integer, sa.ForeignKey("api_providers.id"), nullable=False),
        sa.Column("encrypted_credentials", sa.Text, nullable=False),
        sa.Column("status", sa.String(16), server_default="pending"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("is_paper", sa.Boolean, server_default=sa.text("true")),
        sa.Column("nickname", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("last_tested_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_user_api_conn_user", "user_api_connections", ["user_id"])

    # ── Create user_api_settings ───────────────────────────────────────
    op.create_table(
        "user_api_settings",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("active_equity_broker_id", sa.Integer, sa.ForeignKey("user_api_connections.id"), nullable=True),
        sa.Column("active_crypto_broker_id", sa.Integer, nullable=True),
        sa.Column("primary_market_data_id", sa.Integer, nullable=True),
        sa.Column("fallback_market_data_ids", sa.JSON, default=list),
        sa.Column("primary_options_data_id", sa.Integer, nullable=True),
        sa.Column("options_fallback_enabled", sa.Boolean, server_default=sa.text("false")),
        sa.Column("options_provider_connection_id", sa.Integer, nullable=True),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── Create password_reset_tokens ───────────────────────────────────
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(128), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("used", sa.Boolean, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_pw_reset_user", "password_reset_tokens", ["user_id"])

    # ── Create market_events ───────────────────────────────────────────
    op.create_table(
        "market_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("impact", sa.String(16), nullable=True),
        sa.Column("symbols", sa.JSON, default=list),
        sa.Column("sectors", sa.JSON, default=list),
        sa.Column("headline", sa.Text, nullable=True),
        sa.Column("raw_data", sa.JSON, default=dict),
        sa.Column("source", sa.String(32), nullable=True),
        sa.Column("source_id", sa.String(128), nullable=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("detected_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_market_event_detected", "market_events", ["detected_at"])

    # ── Create trade_decisions ─────────────────────────────────────────
    op.create_table(
        "trade_decisions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("bot_id", sa.String(64), sa.ForeignKey("cerberus_bots.id"), nullable=False),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("strategy_signal", sa.String(16), nullable=True),
        sa.Column("context_risk_level", sa.String(16), nullable=True),
        sa.Column("ai_confidence", sa.Float, nullable=True),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("reasoning", sa.Text, nullable=True),
        sa.Column("size_adjustment", sa.Float, server_default="1.0"),
        sa.Column("delay_seconds", sa.Integer, server_default="0"),
        sa.Column("events_considered", sa.JSON, default=list),
        sa.Column("model_used", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_trade_decision_bot", "trade_decisions", ["bot_id", "created_at"])

    # ── Create universe_candidates ─────────────────────────────────────
    op.create_table(
        "universe_candidates",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("bot_id", sa.String(64), sa.ForeignKey("cerberus_bots.id"), nullable=False),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("scanned_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_universe_bot_score", "universe_candidates", ["bot_id", "score"])

    # ── Create bot_trade_journal ───────────────────────────────────────
    op.create_table(
        "bot_trade_journal",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("bot_id", sa.String(64), sa.ForeignKey("cerberus_bots.id"), nullable=False),
        sa.Column("trade_id", sa.String(64), nullable=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("side", sa.String(8), nullable=True),
        sa.Column("entry_price", sa.Float, nullable=True),
        sa.Column("exit_price", sa.Float, nullable=True),
        sa.Column("entry_at", sa.DateTime, nullable=True),
        sa.Column("exit_at", sa.DateTime, nullable=True),
        sa.Column("hold_duration_seconds", sa.Float, nullable=True),
        sa.Column("pnl", sa.Float, nullable=True),
        sa.Column("pnl_pct", sa.Float, nullable=True),
        sa.Column("market_events", sa.JSON, default=list),
        sa.Column("vix_at_entry", sa.Float, nullable=True),
        sa.Column("sector_momentum_at_entry", sa.Float, nullable=True),
        sa.Column("ai_confidence_at_entry", sa.Float, nullable=True),
        sa.Column("ai_decision", sa.String(32), nullable=True),
        sa.Column("ai_reasoning", sa.Text, nullable=True),
        sa.Column("regime_at_entry", sa.String(32), nullable=True),
        sa.Column("outcome_tag", sa.String(32), nullable=True),
        sa.Column("lesson_learned", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_journal_bot", "bot_trade_journal", ["bot_id", "created_at"])

    # ── Create bot_regime_stats ────────────────────────────────────────
    op.create_table(
        "bot_regime_stats",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("bot_id", sa.String(64), sa.ForeignKey("cerberus_bots.id"), nullable=False),
        sa.Column("regime", sa.String(32), nullable=False),
        sa.Column("total_trades", sa.Integer, server_default="0"),
        sa.Column("win_rate", sa.Float, nullable=True),
        sa.Column("avg_pnl", sa.Float, nullable=True),
        sa.Column("avg_confidence", sa.Float, nullable=True),
        sa.Column("sharpe", sa.Float, nullable=True),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── Create bot_adaptations ─────────────────────────────────────────
    op.create_table(
        "bot_adaptations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("bot_id", sa.String(64), sa.ForeignKey("cerberus_bots.id"), nullable=False),
        sa.Column("adaptation_type", sa.String(32), nullable=False),
        sa.Column("old_value", sa.JSON, nullable=True),
        sa.Column("new_value", sa.JSON, nullable=True),
        sa.Column("reasoning", sa.Text, nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("auto_applied", sa.Boolean, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── Create strategy_type_scores ────────────────────────────────────
    op.create_table(
        "strategy_type_scores",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("strategy_type", sa.String(32), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("roi_component", sa.Float, nullable=True),
        sa.Column("trend_component", sa.Float, nullable=True),
        sa.Column("sample_size_component", sa.Float, nullable=True),
        sa.Column("win_rate_component", sa.Float, nullable=True),
        sa.Column("total_trades", sa.Integer, server_default="0"),
        sa.Column("is_blocked", sa.Boolean, server_default=sa.text("false")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_strat_type_score_user", "strategy_type_scores", ["user_id", "strategy_type"], unique=True)


def downgrade():
    op.drop_table("strategy_type_scores")
    op.drop_table("bot_adaptations")
    op.drop_table("bot_regime_stats")
    op.drop_table("bot_trade_journal")
    op.drop_table("universe_candidates")
    op.drop_table("trade_decisions")
    op.drop_table("market_events")
    op.drop_table("password_reset_tokens")
    op.drop_table("user_api_settings")
    op.drop_table("user_api_connections")
    op.drop_table("api_providers")
    op.drop_index("ix_portfolio_user_mode", "portfolio_snapshots")
    op.drop_index("ix_portfolio_mode_time", "portfolio_snapshots")
    op.drop_column("cerberus_bot_versions", "override_level")
    op.drop_column("cerberus_bot_versions", "universe_config")
    with op.batch_alter_table("paper_portfolios") as batch_op:
        batch_op.alter_column("cash", server_default="1000000.0")
        batch_op.alter_column("initial_capital", server_default="1000000.0")
