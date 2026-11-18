"""adiciona tipo de movimentação DESCARTE

Revision ID: f4a91c2e7b60
Revises: e82b1c64fa30
"""

from alembic import op
import sqlalchemy as sa


revision = "f4a91c2e7b60"
down_revision = "e82b1c64fa30"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("movimentacoes") as batch:
        batch.drop_constraint("ck_movimentacoes_tipo", type_="check")
        batch.create_check_constraint(
            "ck_movimentacoes_tipo",
            "tipo IN ('ENTRADA', 'SAIDA', 'DESCARTE')",
        )


def downgrade():
    bind = op.get_bind()
    tem_descarte = bind.execute(
        sa.text(
            "SELECT 1 FROM movimentacoes "
            "WHERE tipo = 'DESCARTE' LIMIT 1"
        )
    ).first()

    if tem_descarte:
        raise RuntimeError(
            "Não é possível remover DESCARTE enquanto houver "
            "movimentações desse tipo no histórico."
        )

    with op.batch_alter_table("movimentacoes") as batch:
        batch.drop_constraint("ck_movimentacoes_tipo", type_="check")
        batch.create_check_constraint(
            "ck_movimentacoes_tipo",
            "tipo IN ('ENTRADA', 'SAIDA')",
        )