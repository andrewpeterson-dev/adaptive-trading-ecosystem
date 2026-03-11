"""Add user ownership to legacy trades.

Revision ID: 008
Revises: 007
Create Date: 2026-03-11
"""

from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "trades" not in existing_tables or "users" not in existing_tables:
        return

    columns = {column["name"] for column in inspector.get_columns("trades")}
    indexes = {index["name"] for index in inspector.get_indexes("trades")}
    foreign_keys = {
        fk.get("name") for fk in inspector.get_foreign_keys("trades") if fk.get("name")
    }

    if "user_id" not in columns:
        with op.batch_alter_table("trades") as batch_op:
            batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_trades_user_id_users",
                "users",
                ["user_id"],
                ["id"],
            )
    elif "fk_trades_user_id_users" not in foreign_keys:
        with op.batch_alter_table("trades") as batch_op:
            batch_op.create_foreign_key(
                "fk_trades_user_id_users",
                "users",
                ["user_id"],
                ["id"],
            )

    if "ix_trades_user_id" not in indexes:
        op.create_index("ix_trades_user_id", "trades", ["user_id"])
    if "ix_trades_user_mode_time" not in indexes:
        op.create_index("ix_trades_user_mode_time", "trades", ["user_id", "mode", "entry_time"])

    user_count = conn.execute(sa.text("SELECT COUNT(*) FROM users")).scalar() or 0
    if user_count == 1:
        user_id = conn.execute(sa.text("SELECT id FROM users LIMIT 1")).scalar()
        if user_id is not None:
            conn.execute(
                sa.text("UPDATE trades SET user_id = :user_id WHERE user_id IS NULL"),
                {"user_id": user_id},
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "trades" not in existing_tables:
        return

    indexes = {index["name"] for index in inspector.get_indexes("trades")}
    columns = {column["name"] for column in inspector.get_columns("trades")}
    foreign_keys = {
        fk.get("name") for fk in inspector.get_foreign_keys("trades") if fk.get("name")
    }

    if "ix_trades_user_mode_time" in indexes:
        op.drop_index("ix_trades_user_mode_time", table_name="trades")
    if "ix_trades_user_id" in indexes:
        op.drop_index("ix_trades_user_id", table_name="trades")

    if "user_id" in columns:
        with op.batch_alter_table("trades") as batch_op:
            if "fk_trades_user_id_users" in foreign_keys:
                batch_op.drop_constraint("fk_trades_user_id_users", type_="foreignkey")
            batch_op.drop_column("user_id")
