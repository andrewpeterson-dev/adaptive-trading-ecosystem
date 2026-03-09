"""Add cerberus tables — 18 tables for the Cerberus AI subsystem.

Revision ID: 002_copilot
Revises: 001_initial
Create Date: 2026-03-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "002_copilot"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Enum types ────────────────────────────────────────────────────────
    account_mode = sa.Enum("paper", "live", name="accountmode")
    bot_status = sa.Enum("draft", "running", "paused", "stopped", "error", name="botstatus")
    conversation_mode = sa.Enum("chat", "analysis", "trade", "backtest", "build", name="conversationmode")
    message_role = sa.Enum("user", "assistant", "system", "tool", name="messagerole")
    proposal_status = sa.Enum(
        "pending", "confirmed", "rejected", "expired", "executed", "failed",
        name="proposalstatus",
    )
    document_status = sa.Enum("pending", "processing", "indexed", "failed", name="documentstatus")
    tool_side_effect = sa.Enum("none", "read", "write", "trade", "notify", name="toolsideeffect")

    # ── 1. cerberus_brokerage_accounts ─────────────────────────────────────
    op.create_table(
        "cerberus_brokerage_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("account_mode", account_mode, nullable=False, server_default="paper"),
        sa.Column("encrypted_access_token", sa.Text, nullable=True),
        sa.Column("encrypted_refresh_token", sa.Text, nullable=True),
        sa.Column("metadata_json", sa.JSON, nullable=True),
        sa.Column("last_synced_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_cerberus_brkacct_user", "cerberus_brokerage_accounts", ["user_id"])
    op.create_index("ix_cerberus_brkacct_provider", "cerberus_brokerage_accounts", ["provider"])

    # ── 2. cerberus_portfolio_snapshots ────────────────────────────────────
    op.create_table(
        "cerberus_portfolio_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "brokerage_account_id",
            sa.String(36),
            sa.ForeignKey("cerberus_brokerage_accounts.id"),
            nullable=False,
        ),
        sa.Column("snapshot_ts", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("cash", sa.Float, nullable=True),
        sa.Column("equity", sa.Float, nullable=True),
        sa.Column("buying_power", sa.Float, nullable=True),
        sa.Column("margin_used", sa.Float, nullable=True),
        sa.Column("day_pnl", sa.Float, nullable=True),
        sa.Column("total_pnl", sa.Float, nullable=True),
        sa.Column("payload_json", sa.JSON, nullable=True),
    )
    op.create_index("ix_cerberus_snap_user", "cerberus_portfolio_snapshots", ["user_id"])
    op.create_index(
        "ix_cerberus_snap_acct_ts",
        "cerberus_portfolio_snapshots",
        ["brokerage_account_id", "snapshot_ts"],
    )

    # ── 3. cerberus_positions ──────────────────────────────────────────────
    op.create_table(
        "cerberus_positions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "brokerage_account_id",
            sa.String(36),
            sa.ForeignKey("cerberus_brokerage_accounts.id"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("asset_type", sa.String(32), nullable=True),
        sa.Column("quantity", sa.Float, nullable=False),
        sa.Column("avg_price", sa.Float, nullable=True),
        sa.Column("mark_price", sa.Float, nullable=True),
        sa.Column("market_value", sa.Float, nullable=True),
        sa.Column("unrealized_pnl", sa.Float, nullable=True),
        sa.Column("realized_pnl", sa.Float, nullable=True),
        sa.Column("greeks_json", sa.JSON, nullable=True),
        sa.Column("metadata_json", sa.JSON, nullable=True),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_cerberus_pos_user", "cerberus_positions", ["user_id"])
    op.create_index(
        "ix_cerberus_pos_acct_symbol",
        "cerberus_positions",
        ["brokerage_account_id", "symbol"],
    )

    # ── 4. cerberus_orders ─────────────────────────────────────────────────
    op.create_table(
        "cerberus_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "brokerage_account_id",
            sa.String(36),
            sa.ForeignKey("cerberus_brokerage_accounts.id"),
            nullable=False,
        ),
        sa.Column("broker_order_id", sa.String(128), nullable=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("asset_type", sa.String(32), nullable=True),
        sa.Column("side", sa.String(16), nullable=False),
        sa.Column("order_type", sa.String(32), nullable=False),
        sa.Column("tif", sa.String(16), nullable=True),
        sa.Column("quantity", sa.Float, nullable=False),
        sa.Column("limit_price", sa.Float, nullable=True),
        sa.Column("stop_price", sa.Float, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("payload_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_cerberus_ord_user", "cerberus_orders", ["user_id"])
    op.create_index("ix_cerberus_ord_acct", "cerberus_orders", ["brokerage_account_id"])
    op.create_index("ix_cerberus_ord_symbol_status", "cerberus_orders", ["symbol", "status"])

    # ── 5. cerberus_trades ─────────────────────────────────────────────────
    op.create_table(
        "cerberus_trades",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "brokerage_account_id",
            sa.String(36),
            sa.ForeignKey("cerberus_brokerage_accounts.id"),
            nullable=True,
        ),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("asset_type", sa.String(32), nullable=True),
        sa.Column("side", sa.String(16), nullable=False),
        sa.Column("entry_ts", sa.DateTime, nullable=True),
        sa.Column("exit_ts", sa.DateTime, nullable=True),
        sa.Column("entry_price", sa.Float, nullable=True),
        sa.Column("exit_price", sa.Float, nullable=True),
        sa.Column("quantity", sa.Float, nullable=False),
        sa.Column("gross_pnl", sa.Float, nullable=True),
        sa.Column("net_pnl", sa.Float, nullable=True),
        sa.Column("return_pct", sa.Float, nullable=True),
        sa.Column("strategy_tag", sa.String(64), nullable=True),
        sa.Column("bot_id", sa.String(36), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("payload_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_cerberus_trd_user", "cerberus_trades", ["user_id"])
    op.create_index("ix_cerberus_trd_symbol", "cerberus_trades", ["symbol"])
    op.create_index("ix_cerberus_trd_strategy", "cerberus_trades", ["strategy_tag"])
    op.create_index("ix_cerberus_trd_bot", "cerberus_trades", ["bot_id"])

    # ── 6. cerberus_bots ──────────────────────────────────────────────────
    op.create_table(
        "cerberus_bots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("status", bot_status, nullable=False, server_default="draft"),
        sa.Column("current_version_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('draft','running','paused','stopped','error')",
            name="ck_cerberus_bot_status",
        ),
    )
    op.create_index("ix_cerberus_bot_user", "cerberus_bots", ["user_id"])

    # ── 7. cerberus_bot_versions ───────────────────────────────────────────
    op.create_table(
        "cerberus_bot_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("bot_id", sa.String(36), sa.ForeignKey("cerberus_bots.id"), nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("config_json", sa.JSON, nullable=True),
        sa.Column("diff_summary", sa.Text, nullable=True),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("backtest_required", sa.Boolean, server_default=sa.text("false")),
        sa.Column("backtest_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_cerberus_botver_bot", "cerberus_bot_versions", ["bot_id"])
    op.create_index(
        "ix_cerberus_botver_bot_num",
        "cerberus_bot_versions",
        ["bot_id", "version_number"],
        unique=True,
    )

    # ── 8. cerberus_backtests ──────────────────────────────────────────────
    op.create_table(
        "cerberus_backtests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("bot_id", sa.String(36), nullable=True),
        sa.Column("bot_version_id", sa.String(36), nullable=True),
        sa.Column("strategy_name", sa.String(128), nullable=True),
        sa.Column("params_json", sa.JSON, nullable=True),
        sa.Column("metrics_json", sa.JSON, nullable=True),
        sa.Column("equity_curve_json", sa.JSON, nullable=True),
        sa.Column("trades_json", sa.JSON, nullable=True),
        sa.Column("leakage_checks_json", sa.JSON, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_cerberus_bt_user", "cerberus_backtests", ["user_id"])
    op.create_index("ix_cerberus_bt_bot", "cerberus_backtests", ["bot_id"])

    # ── 9. cerberus_conversation_threads ───────────────────────────────────
    op.create_table(
        "cerberus_conversation_threads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(256), nullable=True),
        sa.Column("mode", conversation_mode, nullable=False, server_default="chat"),
        sa.Column("latest_page", sa.String(128), nullable=True),
        sa.Column("latest_symbol", sa.String(32), nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_cerberus_thread_user", "cerberus_conversation_threads", ["user_id"])
    op.create_index("ix_cerberus_thread_updated", "cerberus_conversation_threads", ["updated_at"])

    # ── 10. cerberus_conversation_messages ─────────────────────────────────
    op.create_table(
        "cerberus_conversation_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "thread_id",
            sa.String(36),
            sa.ForeignKey("cerberus_conversation_threads.id"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", message_role, nullable=False),
        sa.Column("content_md", sa.Text, nullable=True),
        sa.Column("structured_json", sa.JSON, nullable=True),
        sa.Column("model_name", sa.String(64), nullable=True),
        sa.Column("provider_name", sa.String(64), nullable=True),
        sa.Column("citations_json", sa.JSON, nullable=True),
        sa.Column("tool_calls_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_cerberus_msg_thread", "cerberus_conversation_messages", ["thread_id"])
    op.create_index("ix_cerberus_msg_user", "cerberus_conversation_messages", ["user_id"])
    op.create_index(
        "ix_cerberus_msg_thread_ts",
        "cerberus_conversation_messages",
        ["thread_id", "created_at"],
    )

    # ── 11. cerberus_memory_items ──────────────────────────────────────────
    op.create_table(
        "cerberus_memory_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("source_table", sa.String(128), nullable=True),
        sa.Column("source_id", sa.String(36), nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("metadata_json", sa.JSON, nullable=True),
        sa.Column("embedding_json", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_cerberus_mem_user", "cerberus_memory_items", ["user_id"])
    op.create_index("ix_cerberus_mem_kind", "cerberus_memory_items", ["kind"])
    op.create_index(
        "ix_cerberus_mem_source",
        "cerberus_memory_items",
        ["source_table", "source_id"],
    )

    # ── 12. cerberus_document_files ────────────────────────────────────────
    op.create_table(
        "cerberus_document_files",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=True),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("doc_type", sa.String(64), nullable=True),
        sa.Column("status", document_status, nullable=False, server_default="pending"),
        sa.Column("metadata_json", sa.JSON, nullable=True),
        sa.Column("indexed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('pending','processing','indexed','failed')",
            name="ck_cerberus_docfile_status",
        ),
    )
    op.create_index("ix_cerberus_docfile_user", "cerberus_document_files", ["user_id"])
    op.create_index("ix_cerberus_docfile_status", "cerberus_document_files", ["status"])

    # ── 13. cerberus_document_chunks ───────────────────────────────────────
    op.create_table(
        "cerberus_document_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(36),
            sa.ForeignKey("cerberus_document_files.id"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("page_number", sa.Integer, nullable=True),
        sa.Column("heading", sa.String(512), nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("metadata_json", sa.JSON, nullable=True),
        sa.Column("embedding_json", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_cerberus_chunk_doc", "cerberus_document_chunks", ["document_id"])
    op.create_index("ix_cerberus_chunk_user", "cerberus_document_chunks", ["user_id"])
    op.create_index(
        "ix_cerberus_chunk_doc_idx",
        "cerberus_document_chunks",
        ["document_id", "chunk_index"],
    )

    # ── 14. cerberus_ui_context_events ─────────────────────────────────────
    op.create_table(
        "cerberus_ui_context_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("thread_id", sa.String(36), nullable=True),
        sa.Column("current_page", sa.String(128), nullable=True),
        sa.Column("route", sa.String(256), nullable=True),
        sa.Column("visible_components", sa.JSON, nullable=True),
        sa.Column("focused_component", sa.String(128), nullable=True),
        sa.Column("selected_symbol", sa.String(32), nullable=True),
        sa.Column("selected_account_id", sa.String(36), nullable=True),
        sa.Column("selected_bot_id", sa.String(36), nullable=True),
        sa.Column("component_state", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_cerberus_uictx_user", "cerberus_ui_context_events", ["user_id"])
    op.create_index("ix_cerberus_uictx_thread", "cerberus_ui_context_events", ["thread_id"])

    # ── 15. cerberus_trade_proposals ───────────────────────────────────────
    op.create_table(
        "cerberus_trade_proposals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "thread_id",
            sa.String(36),
            sa.ForeignKey("cerberus_conversation_threads.id"),
            nullable=True,
        ),
        sa.Column("proposal_json", sa.JSON, nullable=True),
        sa.Column("risk_json", sa.JSON, nullable=True),
        sa.Column("explanation_md", sa.Text, nullable=True),
        sa.Column("status", proposal_status, nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('pending','confirmed','rejected','expired','executed','failed')",
            name="ck_cerberus_proposal_status",
        ),
    )
    op.create_index("ix_cerberus_proposal_user", "cerberus_trade_proposals", ["user_id"])
    op.create_index("ix_cerberus_proposal_thread", "cerberus_trade_proposals", ["thread_id"])
    op.create_index("ix_cerberus_proposal_status", "cerberus_trade_proposals", ["status"])

    # ── 16. cerberus_trade_confirmations ───────────────────────────────────
    op.create_table(
        "cerberus_trade_confirmations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "proposal_id",
            sa.String(36),
            sa.ForeignKey("cerberus_trade_proposals.id"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("confirmation_token_hash", sa.String(256), nullable=False),
        sa.Column("confirmed_at", sa.DateTime, nullable=True),
        sa.Column("executed_at", sa.DateTime, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_cerberus_confirm_proposal", "cerberus_trade_confirmations", ["proposal_id"]
    )
    op.create_index("ix_cerberus_confirm_user", "cerberus_trade_confirmations", ["user_id"])

    # ── 17. cerberus_ai_tool_calls ─────────────────────────────────────────
    op.create_table(
        "cerberus_ai_tool_calls",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("thread_id", sa.String(36), nullable=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tool_name", sa.String(128), nullable=False),
        sa.Column("tool_version", sa.String(32), nullable=True),
        sa.Column("input_json", sa.JSON, nullable=True),
        sa.Column("output_json", sa.JSON, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("error_text", sa.Text, nullable=True),
        sa.Column("provider_request_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_cerberus_toolcall_thread", "cerberus_ai_tool_calls", ["thread_id"])
    op.create_index("ix_cerberus_toolcall_user", "cerberus_ai_tool_calls", ["user_id"])
    op.create_index("ix_cerberus_toolcall_name", "cerberus_ai_tool_calls", ["tool_name"])

    # ── 18. cerberus_audit_log ─────────────────────────────────────────────
    op.create_table(
        "cerberus_audit_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("resource_id", sa.String(36), nullable=True),
        sa.Column("payload_json", sa.JSON, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_cerberus_audit_user", "cerberus_audit_log", ["user_id"])
    op.create_index("ix_cerberus_audit_action", "cerberus_audit_log", ["action_type"])
    op.create_index(
        "ix_cerberus_audit_resource",
        "cerberus_audit_log",
        ["resource_type", "resource_id"],
    )
    op.create_index("ix_cerberus_audit_trace", "cerberus_audit_log", ["trace_id"])


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("cerberus_audit_log")
    op.drop_table("cerberus_ai_tool_calls")
    op.drop_table("cerberus_trade_confirmations")
    op.drop_table("cerberus_trade_proposals")
    op.drop_table("cerberus_ui_context_events")
    op.drop_table("cerberus_document_chunks")
    op.drop_table("cerberus_document_files")
    op.drop_table("cerberus_memory_items")
    op.drop_table("cerberus_conversation_messages")
    op.drop_table("cerberus_conversation_threads")
    op.drop_table("cerberus_backtests")
    op.drop_table("cerberus_bot_versions")
    op.drop_table("cerberus_bots")
    op.drop_table("cerberus_trades")
    op.drop_table("cerberus_orders")
    op.drop_table("cerberus_positions")
    op.drop_table("cerberus_portfolio_snapshots")
    op.drop_table("cerberus_brokerage_accounts")

    # Drop enum types
    sa.Enum(name="toolsideeffect").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="documentstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="proposalstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="messagerole").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="conversationmode").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="botstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="accountmode").drop(op.get_bind(), checkfirst=True)
