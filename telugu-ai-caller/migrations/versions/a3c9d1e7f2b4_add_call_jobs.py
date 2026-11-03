"""add_call_jobs (outbound dialer queue)

Revision ID: a3c9d1e7f2b4
Revises: 7f5f125da574
Create Date: 2026-11-03 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3c9d1e7f2b4'
down_revision: Union[str, Sequence[str], None] = '7f5f125da574'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('call_jobs',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('account_id', sa.Integer(), nullable=False),
    sa.Column('lead_id', sa.Integer(), nullable=False),
    sa.Column('campaign_id', sa.Integer(), nullable=True),
    sa.Column('phone_e164', sa.String(length=32), nullable=False),
    sa.Column('language', sa.String(length=16), nullable=True),
    sa.Column('provider', sa.String(length=32), nullable=False),
    sa.Column('state', sa.String(length=32), nullable=False),
    sa.Column('priority', sa.Integer(), nullable=False),
    sa.Column('attempt', sa.Integer(), nullable=False),
    sa.Column('max_attempts', sa.Integer(), nullable=False),
    sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('provider_call_id', sa.String(length=128), nullable=True),
    sa.Column('call_id', sa.Integer(), nullable=True),
    sa.Column('last_disposition', sa.String(length=64), nullable=True),
    sa.Column('block_reason', sa.String(length=255), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('dialed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('answered_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['call_id'], ['calls.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_call_jobs_account_id'), 'call_jobs', ['account_id'], unique=False)
    op.create_index(op.f('ix_call_jobs_lead_id'), 'call_jobs', ['lead_id'], unique=False)
    op.create_index(op.f('ix_call_jobs_campaign_id'), 'call_jobs', ['campaign_id'], unique=False)
    op.create_index(op.f('ix_call_jobs_state'), 'call_jobs', ['state'], unique=False)
    op.create_index(op.f('ix_call_jobs_next_attempt_at'), 'call_jobs', ['next_attempt_at'], unique=False)
    op.create_index(op.f('ix_call_jobs_provider_call_id'), 'call_jobs', ['provider_call_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_call_jobs_provider_call_id'), table_name='call_jobs')
    op.drop_index(op.f('ix_call_jobs_next_attempt_at'), table_name='call_jobs')
    op.drop_index(op.f('ix_call_jobs_state'), table_name='call_jobs')
    op.drop_index(op.f('ix_call_jobs_campaign_id'), table_name='call_jobs')
    op.drop_index(op.f('ix_call_jobs_lead_id'), table_name='call_jobs')
    op.drop_index(op.f('ix_call_jobs_account_id'), table_name='call_jobs')
    op.drop_table('call_jobs')
