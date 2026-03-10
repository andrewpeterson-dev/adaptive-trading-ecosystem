"""Options fallback + capability flags.

Adds:
  - api_providers.supports_stocks, supports_order_placement, supports_positions_streaming
  - user_api_settings.options_fallback_enabled, options_provider_connection_id
  - option_sim_trades table

Revision ID: 006
Revises: 005
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    def column_exists(table, column):
        result = bind.execute(sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name=:t AND column_name=:c"
        ), {"t": table, "c": column})
        return result.scalar() is not None

    def table_exists(table):
        result = bind.execute(sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name=:t"
        ), {"t": table})
        return result.scalar() is not None

    def index_exists(index):
        result = bind.execute(sa.text(
            "SELECT 1 FROM pg_indexes WHERE indexname=:i"
        ), {"i": index})
        return result.scalar() is not None

    # ── api_providers: new capability flags ──────────────────────────────
    if not column_exists('api_providers', 'supports_stocks'):
        op.add_column('api_providers', sa.Column('supports_stocks', sa.Boolean(), nullable=True, server_default=sa.text('false')))
    if not column_exists('api_providers', 'supports_order_placement'):
        op.add_column('api_providers', sa.Column('supports_order_placement', sa.Boolean(), nullable=True, server_default=sa.text('false')))
    if not column_exists('api_providers', 'supports_positions_streaming'):
        op.add_column('api_providers', sa.Column('supports_positions_streaming', sa.Boolean(), nullable=True, server_default=sa.text('false')))

    # ── user_api_settings: options fallback columns ───────────────────────
    if not column_exists('user_api_settings', 'options_fallback_enabled'):
        op.add_column('user_api_settings', sa.Column('options_fallback_enabled', sa.Boolean(), nullable=True, server_default=sa.text('false')))
    if not column_exists('user_api_settings', 'options_provider_connection_id'):
        op.add_column('user_api_settings', sa.Column('options_provider_connection_id', sa.Integer(), sa.ForeignKey('user_api_connections.id'), nullable=True))

    # ── option_sim_trades table ───────────────────────────────────────────
    if not table_exists('option_sim_trades'):
        op.create_table(
            'option_sim_trades',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('connection_id', sa.Integer(), sa.ForeignKey('user_api_connections.id'), nullable=False),
            sa.Column('tradier_order_id', sa.String(64), nullable=True),
            sa.Column('symbol', sa.String(32), nullable=False),
            sa.Column('option_symbol', sa.String(32), nullable=True),
            sa.Column('option_type', sa.String(4), nullable=False),
            sa.Column('strike', sa.Float(), nullable=False),
            sa.Column('expiry', sa.Date(), nullable=False),
            sa.Column('qty', sa.Integer(), nullable=False),
            sa.Column('fill_price', sa.Float(), nullable=True),
            sa.Column('realized_pnl', sa.Float(), nullable=True),
            sa.Column('status', sa.String(16), server_default='pending'),
            sa.Column('opened_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('closed_at', sa.DateTime(), nullable=True),
        )
        if not index_exists('ix_option_sim_user'):
            op.create_index('ix_option_sim_user', 'option_sim_trades', ['user_id'])
        if not index_exists('ix_option_sim_status'):
            op.create_index('ix_option_sim_status', 'option_sim_trades', ['status'])


def downgrade() -> None:
    op.drop_index('ix_option_sim_status', table_name='option_sim_trades')
    op.drop_index('ix_option_sim_user', table_name='option_sim_trades')
    op.drop_table('option_sim_trades')
    op.drop_column('user_api_settings', 'options_provider_connection_id')
    op.drop_column('user_api_settings', 'options_fallback_enabled')
    op.drop_column('api_providers', 'supports_positions_streaming')
    op.drop_column('api_providers', 'supports_order_placement')
    op.drop_column('api_providers', 'supports_stocks')
