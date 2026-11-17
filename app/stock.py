from sqlalchemy import case, func, select

from .models import Movement


def stock_by_lot(establishment_id):
    signed_quantity = case(
        (Movement.kind == "ENTRADA", Movement.quantity_kg),
        else_=-Movement.quantity_kg,
    )
    return (
        select(Movement.lot_id.label("lot_id"), func.sum(signed_quantity).label("balance"))
        .where(Movement.establishment_id == establishment_id)
        .group_by(Movement.lot_id)
        .subquery()
    )

