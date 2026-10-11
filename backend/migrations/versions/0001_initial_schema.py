"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-10 23:38:05.347247
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:

    op.create_table('users',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('display_name', sa.String(length=80), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email'))
    )
    op.create_table('documents',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('owner_id', sa.String(length=32), nullable=False),
    sa.Column('symbol', sa.String(length=16), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('document_type', sa.String(length=32), nullable=False),
    sa.Column('source', sa.String(length=500), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=True),
    sa.Column('content_sha256', sa.String(length=64), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('page_count', sa.Integer(), nullable=False),
    sa.Column('chunk_count', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('error', sa.String(length=500), nullable=True),
    sa.Column('published_on', sa.Date(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name=op.f('fk_documents_owner_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_documents')),
    sa.UniqueConstraint('owner_id', 'content_sha256', name=op.f('uq_documents_owner_id'))
    )
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_documents_owner_id'), ['owner_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_documents_symbol'), ['symbol'], unique=False)

    op.create_table('portfolios',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('owner_id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=True),
    sa.Column('benchmark', sa.String(length=16), nullable=False),
    sa.Column('rebalancing', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name=op.f('fk_portfolios_owner_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_portfolios')),
    sa.UniqueConstraint('owner_id', 'name', name=op.f('uq_portfolios_owner_id'))
    )
    with op.batch_alter_table('portfolios', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_portfolios_owner_id'), ['owner_id'], unique=False)

    op.create_table('research_reports',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('owner_id', sa.String(length=32), nullable=False),
    sa.Column('symbol', sa.String(length=16), nullable=False),
    sa.Column('question', sa.Text(), nullable=True),
    sa.Column('generation_mode', sa.String(length=20), nullable=False),
    sa.Column('model', sa.String(length=80), nullable=True),
    sa.Column('report', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name=op.f('fk_research_reports_owner_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_research_reports'))
    )
    with op.batch_alter_table('research_reports', schema=None) as batch_op:
        batch_op.create_index('ix_research_reports_owner_created', ['owner_id', 'created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_research_reports_owner_id'), ['owner_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_research_reports_symbol'), ['symbol'], unique=False)

    op.create_table('sessions',
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('user_agent', sa.String(length=255), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_sessions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('token_hash', name=op.f('pk_sessions'))
    )
    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sessions_expires_at'), ['expires_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_sessions_user_id'), ['user_id'], unique=False)

    op.create_table('watchlist_items',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('owner_id', sa.String(length=32), nullable=False),
    sa.Column('symbol', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name=op.f('fk_watchlist_items_owner_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_watchlist_items')),
    sa.UniqueConstraint('owner_id', 'symbol', name=op.f('uq_watchlist_items_owner_id'))
    )
    with op.batch_alter_table('watchlist_items', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_watchlist_items_owner_id'), ['owner_id'], unique=False)

    op.create_table('portfolio_holdings',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('portfolio_id', sa.String(length=32), nullable=False),
    sa.Column('symbol', sa.String(length=16), nullable=False),
    sa.Column('weight', sa.Float(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.CheckConstraint('weight > 0 AND weight <= 1', name=op.f('ck_portfolio_holdings_weight_range')),
    sa.ForeignKeyConstraint(['portfolio_id'], ['portfolios.id'], name=op.f('fk_portfolio_holdings_portfolio_id_portfolios'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_portfolio_holdings')),
    sa.UniqueConstraint('portfolio_id', 'symbol', name=op.f('uq_portfolio_holdings_portfolio_id'))
    )
    with op.batch_alter_table('portfolio_holdings', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_portfolio_holdings_portfolio_id'), ['portfolio_id'], unique=False)




def downgrade() -> None:

    with op.batch_alter_table('portfolio_holdings', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_portfolio_holdings_portfolio_id'))

    op.drop_table('portfolio_holdings')
    with op.batch_alter_table('watchlist_items', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_watchlist_items_owner_id'))

    op.drop_table('watchlist_items')
    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sessions_user_id'))
        batch_op.drop_index(batch_op.f('ix_sessions_expires_at'))

    op.drop_table('sessions')
    with op.batch_alter_table('research_reports', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_research_reports_symbol'))
        batch_op.drop_index(batch_op.f('ix_research_reports_owner_id'))
        batch_op.drop_index('ix_research_reports_owner_created')

    op.drop_table('research_reports')
    with op.batch_alter_table('portfolios', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_portfolios_owner_id'))

    op.drop_table('portfolios')
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_documents_symbol'))
        batch_op.drop_index(batch_op.f('ix_documents_owner_id'))

    op.drop_table('documents')
    op.drop_table('users')

