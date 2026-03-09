"""Add copilot tables — 18 tables for the AI Copilot subsystem.

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

    # ── 1. copilot_brokerage_accounts ─────────────────────────────────────
    op.create_table(
        "copilot_brokerage_accounts",
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
    op.create_index("ix_copilot_brkacct_user", "copilot_brokerage_accounts", ["user_id"])
    op.create_index("ix_copilot_brkacct_provider", "copilot_brokerage_accounts", ["provider"])

    # ── 2. copilot_portfolio_snapshots ────────────────────────────────────
    op.create_table(
        "copilot_portfolio_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "brokerage_account_id",
            sa.String(36),
            sa.ForeignKey("copilot_brokerage_accounts.id"),
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
    op.create_index("ix_copilot_snap_user", "copilot_portfolio_snapshots", ["user_id"])
    op.create_index(
        "ix_copilot_snap_acct_ts",
        "copilot_portfolio_snapshots",
        ["brokerage_account_id", "snapshot_ts"],
    )

    # ── 3. copilot_positions ──────────────────────────────────────────────
    op.create_table(
        "copilot_positions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "brokerage_account_id",
            sa.String(36),
            sa.ForeignKey("copilot_brokerage_accounts.id"),
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
    op.create_index("ix_copilot_pos_user", "copilot_positions", ["user_id"])
    op.create_index(
        "ix_copilot_pos_acct_symbol",
        "copilot_positions",
        ["brokerage_account_id", "symbol"],
    )

    # ── 4. copilot_orders ─────────────────────────────────────────────────
    op.create_table(
        "copilot_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "brokerage_account_id",
            sa.String(36),
            sa.ForeignKey("copilot_brokerage_accounts.id"),
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
    op.create_index("ix_copilot_ord_user", "copilot_orders", ["user_id"])
    op.create_index("ix_copilot_ord_acct", "copilot_orders", ["brokerage_account_id"])
    op.create_index("ix_copilot_ord_symbol_status", "copilot_orders", ["symbol", "status"])

    # ── 5. copilot_trades ─────────────────────────────────────────────────
    op.create_table(
        "copilot_trades",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "brokerage_account_id",
            sa.String(36),
            sa.ForeignKey("copilot_brokerage_accounts.id"),
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
    op.create_index("ix_copilot_trd_user", "copilot_trades", ["user_id"])
    op.create_index("ix_copilot_trd_symbol", "copilot_trades", ["symbol"])
    op.create_index("ix_copilot_trd_strategy", "copilot_trades", ["strategy_tag"])
    op.create_index("ix_copilot_trd_bot", "copilot_trades", ["bot_id"])

    # ── 6. copilot_bots ──────────────────────────────────────────────────
    op.create_table(
        "copilot_bots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("status", bot_status, nullable=False, server_default="draft"),
        sa.Column("current_version_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('draft','running','paused','stopped','error')",
            name="ck_copilot_bot_status",
        ),
    )
    op.create_index("ix_copilot_bot_user", "copilot_bots", ["user_id"])

    # ── 7. copilot_bot_versions ───────────────────────────────────────────
    op.create_table(
        "copilot_bot_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("bot_id", sa.String(36), sa.ForeignKey("copilot_bots.id"), nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("config_json", sa.JSON, nullable=True),
        sa.Column("diff_summary", sa.Text, nullable=True),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("backtest_required", sa.Boolean, server_default=sa.text("false")),
        sa.Column("backtest_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_copilot_botver_bot", "copilot_bot_versions", ["bot_id"])
    op.create_index(
        "ix_copilot_botver_bot_num",
        "copilot_bot_versions",
        ["bot_id", "version_number"],
        unique=True,
    )

    # ── 8. copilot_backtests ──────────────────────────────────────────────
    op.create_table(
        "copilot_backtests",
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
    op.create_index("ix_copilot_bt_user", "copilot_backtests", ["user_id"])
    op.create_index("ix_copilot_bt_bot", "copilot_backtests", ["bot_id"])

    # ── 9. copilot_conversation_threads ───────────────────────────────────
    op.create_table(
        "copilot_conversation_threads",
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
    op.create_index("ix_copilot_thread_user", "copilot_conversation_threads", ["user_id"])
    op.create_index("ix_copilot_thread_updated", "copilot_conversation_threads", ["updated_at"])

    # ── 10. copilot_conversation_messages ─────────────────────────────────
    op.create_table(
        "copilot_conversation_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "thread_id",
            sa.String(36),
            sa.ForeignKey("copilot_conversation_threads.id"),
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
    op.create_index("ix_copilot_msg_thread", "copilot_conversation_messages", ["thread_id"])
    op.create_index("ix_copilot_msg_user", "copilot_conversation_messages", ["user_id"])
    op.create_index(
        "ix_copilot_msg_thread_ts",
        "copilot_conversation_messages",
        ["thread_id", "created_at"],
    )

    # ── 11. copilot_memory_items ──────────────────────────────────────────
    op.create_table(
        "copilot_memory_items",
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
    op.create_index("ix_copilot_mem_user", "copilot_memory_items", ["user_id"])
    op.create_index("ix_copilot_mem_kind", "copilot_memory_items", ["kind"])
    op.create_index(
        "ix_copilot_mem_source",
        "copilot_memory_items",
        ["source_table", "source_id"],
    )

    # ── 12. copilot_document_files ────────────────────────────────────────
    op.create_table(
        "copilot_document_files",
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
            name="ck_copilot_docfile_status",
        ),
    )
    op.create_index("ix_copilot_docfile_user", "copilot_document_files", ["user_id"])
    op.create_index("ix_copilot_docfile_status", "copilot_document_files", ["status"])

    # ── 13. copilot_document_chunks ───────────────────────────────────────
    op.create_table(
        "copilot_document_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(36),
            sa.ForeignKey("copilot_document_files.id"),
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
    op.create_index("ix_copilot_chunk_doc", "copilot_document_chunks", ["document_id"])
    op.create_index("ix_copilot_chunk_user", "copilot_document_chunks", ["user_id"])
    op.create_index(
        "ix_copilot_chunk_doc_idx",
        "copilot_document_chunks",
        ["document_id", "chunk_index"],
    )

    # ── 14. copilot_ui_context_events ─────────────────────────────────────
    op.create_table(
        "copilot_ui_context_events",
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
    op.create_index("ix_copilot_uictx_user", "copilot_ui_context_events", ["user_id"])
    op.create_index("ix_copilot_uictx_thread", "copilot_ui_context_events", ["thread_id"])

    # ── 15. copilot_trade_proposals ───────────────────────────────────────
    op.create_table(
        "copilot_trade_proposals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "thread_id",
            sa.String(36),
            sa.ForeignKey("copilot_conversation_threads.id"),
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
            name="ck_copilot_proposal_status",
        ),
    )
    op.create_index("ix_copilot_proposal_user", "copilot_trade_proposals", ["user_id"])
    op.create_index("ix_copilot_proposal_thread", "copilot_trade_proposals", ["thread_id"])
    op.create_index("ix_copilot_proposal_status", "copilot_trade_proposals", ["status"])

    # ── 16. copilot_trade_confirmations ───────────────────────────────────
    op.create_table(
        "copilot_trade_confirmations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "proposal_id",
            sa.String(36),
            sa.ForeignKey("copilot_trade_proposals.id"),
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
        "ix_copilot_confirm_proposal", "copilot_trade_confirmations", ["proposal_id"]
    )
    op.create_index("ix_copilot_confirm_user", "copilot_trade_confirmations", ["user_id"])

    # ── 17. copilot_ai_tool_calls ─────────────────────────────────────────
    op.create_table(
        "copilot_ai_tool_calls",
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
    op.create_index("ix_copilot_toolcall_thread", "copilot_ai_tool_calls", ["thread_id"])
    op.create_index("ix_copilot_toolcall_user", "copilot_ai_tool_calls", ["user_id"])
    op.create_index("ix_copilot_toolcall_name", "copilot_ai_tool_calls", ["tool_name"])

    # ── 18. copilot_audit_log ─────────────────────────────────────────────
    op.create_table(
        "copilot_audit_log",
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
    op.create_index("ix_copilot_audit_user", "copilot_audit_log", ["user_id"])
    op.create_index("ix_copilot_audit_action", "copilot_audit_log", ["action_type"])
    op.create_index(
        "ix_copilot_audit_resource",
        "copilot_audit_log",
        ["resource_type", "resource_id"],
    )
    op.create_index("ix_copilot_audit_trace", "copilot_audit_log", ["trace_id"])


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("copilot_audit_log")
    op.drop_table("copilot_ai_tool_calls")
    op.drop_table("copilot_trade_confirmations")
    op.drop_table("copilot_trade_proposals")
    op.drop_table("copilot_ui_context_events")
    op.drop_table("copilot_document_chunks")
    op.drop_table("copilot_document_files")
    op.drop_table("copilot_memory_items")
    op.drop_table("copilot_conversation_messages")
    op.drop_table("copilot_conversation_threads")
    op.drop_table("copilot_backtests")
    op.drop_table("copilot_bot_versions")
    op.drop_table("copilot_bots")
    op.drop_table("copilot_trades")
    op.drop_table("copilot_orders")
    op.drop_table("copilot_positions")
    op.drop_table("copilot_portfolio_snapshots")
    op.drop_table("copilot_brokerage_accounts")

    # Drop enum types
    sa.Enum(name="toolsideeffect").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="documentstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="proposalstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="messagerole").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="conversationmode").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="botstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="accountmode").drop(op.get_bind(), checkfirst=True)
