"""Add AI strategy metadata and bot learning history.

Revision ID: 009
Revises: 008
Create Date: 2026-03-11
"""

from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = {col["name"] for col in inspector.get_columns(table_name)}
    if column.name not in columns:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(column)


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "strategies" in existing_tables:
        _add_column_if_missing("strategies", sa.Column("strategy_type", sa.String(length=32), nullable=True))
        _add_column_if_missing("strategies", sa.Column("source_prompt", sa.Text(), nullable=True))
        _add_column_if_missing("strategies", sa.Column("ai_context", sa.JSON(), nullable=True))

    if "strategy_templates" in existing_tables:
        _add_column_if_missing("strategy_templates", sa.Column("strategy_type", sa.String(length=32), nullable=True))
        _add_column_if_missing("strategy_templates", sa.Column("source_prompt", sa.Text(), nullable=True))
        _add_column_if_missing("strategy_templates", sa.Column("ai_context", sa.JSON(), nullable=True))

    if "cerberus_bots" in existing_tables:
        _add_column_if_missing("cerberus_bots", sa.Column("learning_enabled", sa.Boolean(), nullable=True))
        _add_column_if_missing("cerberus_bots", sa.Column("learning_status_json", sa.JSON(), nullable=True))
        _add_column_if_missing("cerberus_bots", sa.Column("last_optimization_at", sa.DateTime(), nullable=True))

    if "cerberus_bot_optimization_runs" not in existing_tables:
        op.create_table(
            "cerberus_bot_optimization_runs",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("bot_id", sa.String(length=36), sa.ForeignKey("cerberus_bots.id"), nullable=False),
            sa.Column("source_version_id", sa.String(length=36), sa.ForeignKey("cerberus_bot_versions.id"), nullable=True),
            sa.Column("result_version_id", sa.String(length=36), sa.ForeignKey("cerberus_bot_versions.id"), nullable=True),
            sa.Column("method", sa.String(length=64), nullable=False, server_default="parameter_optimization"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="completed"),
            sa.Column("metrics_json", sa.JSON(), nullable=True),
            sa.Column("adjustments_json", sa.JSON(), nullable=True),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_cerberus_botopt_bot", "cerberus_bot_optimization_runs", ["bot_id"])
        op.create_index("ix_cerberus_botopt_created", "cerberus_bot_optimization_runs", ["created_at"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "cerberus_bot_optimization_runs" in existing_tables:
        indexes = {index["name"] for index in inspector.get_indexes("cerberus_bot_optimization_runs")}
        if "ix_cerberus_botopt_created" in indexes:
            op.drop_index("ix_cerberus_botopt_created", table_name="cerberus_bot_optimization_runs")
        if "ix_cerberus_botopt_bot" in indexes:
            op.drop_index("ix_cerberus_botopt_bot", table_name="cerberus_bot_optimization_runs")
        op.drop_table("cerberus_bot_optimization_runs")

    if "cerberus_bots" in existing_tables:
        columns = {col["name"] for col in inspector.get_columns("cerberus_bots")}
        with op.batch_alter_table("cerberus_bots") as batch_op:
            if "last_optimization_at" in columns:
                batch_op.drop_column("last_optimization_at")
            if "learning_status_json" in columns:
                batch_op.drop_column("learning_status_json")
            if "learning_enabled" in columns:
                batch_op.drop_column("learning_enabled")

    if "strategy_templates" in existing_tables:
        columns = {col["name"] for col in inspector.get_columns("strategy_templates")}
        with op.batch_alter_table("strategy_templates") as batch_op:
            if "ai_context" in columns:
                batch_op.drop_column("ai_context")
            if "source_prompt" in columns:
                batch_op.drop_column("source_prompt")
            if "strategy_type" in columns:
                batch_op.drop_column("strategy_type")

    if "strategies" in existing_tables:
        columns = {col["name"] for col in inspector.get_columns("strategies")}
        with op.batch_alter_table("strategies") as batch_op:
            if "ai_context" in columns:
                batch_op.drop_column("ai_context")
            if "source_prompt" in columns:
                batch_op.drop_column("source_prompt")
            if "strategy_type" in columns:
                batch_op.drop_column("strategy_type")
