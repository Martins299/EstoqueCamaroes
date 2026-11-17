"""vincula contas ao Google Sign-In

Revision ID: e82b1c64fa30
Revises: d13a4f5c9e21
Create Date: 2026-11-17
"""
from alembic import op
import sqlalchemy as sa


revision = "e82b1c64fa30"
down_revision = "d13a4f5c9e21"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("usuarios") as batch:
        batch.add_column(sa.Column("google_sub", sa.String(length=255), nullable=True))
        batch.create_index("ix_usuarios_google_sub", ["google_sub"], unique=True)


def downgrade():
    with op.batch_alter_table("usuarios") as batch:
        batch.drop_index("ix_usuarios_google_sub")
        batch.drop_column("google_sub")
