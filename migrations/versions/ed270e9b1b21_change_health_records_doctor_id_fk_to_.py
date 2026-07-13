"""change_health_records_doctor_id_fk_to_doctors

Revision ID: ed270e9b1b21
Revises: 1c2d3e4f5a6b
Create Date: 2026-07-13 14:46:14.945284

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'ed270e9b1b21'
down_revision = '1c2d3e4f5a6b'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = inspect(connection)
    fkeys = inspector.get_foreign_keys('health_records')
    fkey_names = {fk['name'] for fk in fkeys if fk['name']}

    with op.batch_alter_table('health_records', schema=None) as batch_op:
        if 'health_records_doctor_id_fkey' in fkey_names:
            batch_op.drop_constraint('health_records_doctor_id_fkey', type_='foreignkey')
        batch_op.create_foreign_key('health_records_doctor_id_fkey', 'doctors', ['doctor_id'], ['id'], ondelete='SET NULL')


def downgrade():
    connection = op.get_bind()
    inspector = inspect(connection)
    fkeys = inspector.get_foreign_keys('health_records')
    fkey_names = {fk['name'] for fk in fkeys if fk['name']}

    with op.batch_alter_table('health_records', schema=None) as batch_op:
        if 'health_records_doctor_id_fkey' in fkey_names:
            batch_op.drop_constraint('health_records_doctor_id_fkey', type_='foreignkey')
        batch_op.create_foreign_key('health_records_doctor_id_fkey', 'users', ['doctor_id'], ['id'], ondelete='SET NULL')
