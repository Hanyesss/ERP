"""payment plans (expected payments) + installment link on payments

Revision ID: 0047
Revises: 0045
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ENUM

revision = '0047'
down_revision = '0045'
branch_labels = None
depends_on = None


def upgrade() -> None:
    planstatus = ENUM('pending', 'deposit', 'paid', name='planstatus', create_type=False)
    ENUM('pending', 'deposit', 'paid', name='planstatus').create(op.get_bind(), checkfirst=True)

    op.create_table(
        'payment_plans',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('direction', sa.String(3), nullable=False),
        sa.Column('order_id', UUID(as_uuid=True), sa.ForeignKey('orders.id'), nullable=True),
        sa.Column('purchase_id', UUID(as_uuid=True), sa.ForeignKey('purchases.id'), nullable=True),
        sa.Column('counterparty_id', UUID(as_uuid=True), sa.ForeignKey('counterparties.id'), nullable=False),
        sa.Column('currency', sa.String(10), server_default='CNY', nullable=False),
        sa.Column('expected_amount', sa.Numeric(18, 2), server_default='0', nullable=False),
        sa.Column('expected_cny', sa.Numeric(18, 2), server_default='0', nullable=False),
        sa.Column('status', planstatus, server_default='pending', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_payment_plans_order_id', 'payment_plans', ['order_id'])
    op.create_index('ix_payment_plans_purchase_id', 'payment_plans', ['purchase_id'])

    op.add_column('payments', sa.Column('plan_id', UUID(as_uuid=True),
                                        sa.ForeignKey('payment_plans.id'), nullable=True))
    op.add_column('payments', sa.Column('installment_kind', sa.String(20), nullable=True))
    op.create_index('ix_payments_plan_id', 'payments', ['plan_id'])


def downgrade() -> None:
    op.drop_index('ix_payments_plan_id', 'payments')
    op.drop_column('payments', 'installment_kind')
    op.drop_column('payments', 'plan_id')
    op.drop_index('ix_payment_plans_purchase_id', 'payment_plans')
    op.drop_index('ix_payment_plans_order_id', 'payment_plans')
    op.drop_table('payment_plans')
    sa.Enum(name='planstatus').drop(op.get_bind(), checkfirst=True)
