"""strategy groups and settings

Revision ID: 004
Revises: 003_mode_sep
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003_mode_sep'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('strategies', sa.Column('condition_groups', sa.JSON(), nullable=True))
    op.add_column('strategies', sa.Column('symbols', sa.JSON(), nullable=True))
    op.add_column('strategies', sa.Column('commission_pct', sa.Float(), nullable=True, server_default='0.001'))
    op.add_column('strategies', sa.Column('slippage_pct', sa.Float(), nullable=True, server_default='0.0005'))
    op.add_column('strategies', sa.Column('trailing_stop_pct', sa.Float(), nullable=True))
    op.add_column('strategies', sa.Column('exit_after_bars', sa.Integer(), nullable=True))
    op.add_column('strategies', sa.Column('cooldown_bars', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('strategies', sa.Column('max_trades_per_day', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('strategies', sa.Column('max_exposure_pct', sa.Float(), nullable=True, server_default='1.0'))
    op.add_column('strategies', sa.Column('max_loss_pct', sa.Float(), nullable=True, server_default='0.0'))


def downgrade() -> None:
    for col in [
        'condition_groups', 'symbols', 'commission_pct', 'slippage_pct',
        'trailing_stop_pct', 'exit_after_bars', 'cooldown_bars',
        'max_trades_per_day', 'max_exposure_pct', 'max_loss_pct',
    ]:
        op.drop_column('strategies', col)
