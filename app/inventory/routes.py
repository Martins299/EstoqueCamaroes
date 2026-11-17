from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from collections import defaultdict
from zoneinfo import ZoneInfo

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Chamber, Classification, Lot, Movement, Presentation
from ..stock import stock_by_lot

bp = Blueprint("inventory", __name__)


def _parse_quantity(value):
    try:
        amount = Decimal(value.replace(",", ".").strip())
    except (InvalidOperation, AttributeError):
        return None
    if not amount.is_finite() or amount <= 0:
        return None
    if amount >= Decimal("1000000000"):
        return None
    try:
        quantized = amount.quantize(Decimal("0.001"))
    except InvalidOperation:
        return None
    return quantized if quantized == amount else None


def _balance_for_lot(lot_id):
    signed_quantity = case(
        (Movement.kind == "ENTRADA", Movement.quantity_kg),
        else_=-Movement.quantity_kg,
    )
    return db.session.scalar(
        select(func.coalesce(func.sum(signed_quantity), 0)).where(
            Movement.lot_id == lot_id,
            Movement.establishment_id == current_user.establishment_id,
        )
    ) or Decimal("0")


def _parse_date(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


@bp.get("/stock")
@login_required
def stock_list():
    stock = stock_by_lot(current_user.establishment_id)
    statement = (
        select(Lot, func.coalesce(stock.c.balance, 0).label("balance"))
        .outerjoin(stock, stock.c.lot_id == Lot.id)
        .join(Classification, Lot.classification_id == Classification.id)
        .join(Presentation, Lot.presentation_id == Presentation.id)
        .join(Chamber, Lot.current_chamber_id == Chamber.id)
    )
    search = request.args.get("q", "").strip()
    classification_id = request.args.get("classification", type=int)
    presentation_id = request.args.get("presentation", type=int)
    origin = request.args.get("origin", "").strip().upper()
    chamber_id = request.args.get("chamber", type=int)
    status = request.args.get("status", "active")

    if search:
        pattern = f"%{search}%"
        statement = statement.where(or_(
            Lot.code.ilike(pattern),
            Lot.vessel_or_broker.ilike(pattern),
            Lot.farm_or_producer.ilike(pattern),
            Lot.provenance_note.ilike(pattern),
        ))
    if classification_id:
        statement = statement.where(Lot.classification_id == classification_id)
    if presentation_id:
        statement = statement.where(Lot.presentation_id == presentation_id)
    if origin in {"MAR", "VIVEIRO"}:
        statement = statement.where(Lot.origin == origin)
    if chamber_id:
        statement = statement.where(Lot.current_chamber_id == chamber_id)
    if status == "active":
        statement = statement.where(func.coalesce(stock.c.balance, 0) > 0)
    elif status == "closed":
        statement = statement.where(func.coalesce(stock.c.balance, 0) <= 0)

    rows = db.session.execute(statement.order_by(Lot.created_at.desc(), Lot.code)).all()
    grouped = {
        "classification": defaultdict(lambda: Decimal("0")),
        "presentation": defaultdict(lambda: Decimal("0")),
        "origin": defaultdict(lambda: Decimal("0")),
        "chamber": defaultdict(lambda: Decimal("0")),
    }
    for lot, balance in rows:
        if balance > 0:
            grouped["classification"][lot.classification.name] += balance
            grouped["presentation"][lot.presentation.name] += balance
            grouped["origin"]["Mar" if lot.origin == "MAR" else "Viveiro"] += balance
            grouped["chamber"][lot.current_chamber.name] += balance
    summaries = {key: dict(sorted(values.items())) for key, values in grouped.items()}
    classifications = db.session.scalars(
        select(Classification).where(Classification.active.is_(True)).order_by(Classification.name)
    ).all()
    presentations = db.session.scalars(
        select(Presentation).where(Presentation.active.is_(True)).order_by(Presentation.name)
    ).all()
    chambers = db.session.scalars(
        select(Chamber).where(Chamber.active.is_(True)).order_by(Chamber.name)
    ).all()

    return render_template(
        "inventory/stock_list.html",
        rows=rows,
        summaries=summaries,
        classifications=classifications,
        presentations=presentations,
        chambers=chambers,
        filters={"q": search, "classification": classification_id, "presentation": presentation_id,
                 "origin": origin, "chamber": chamber_id, "status": status},
    )


@bp.route("/chambers", methods=["GET", "POST"])
@login_required
def chambers():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip() or None
        if not name:
            flash("Informe a identificação da câmara.", "danger")
        else:
            db.session.add(Chamber(name=name, description=description))
            try:
                db.session.commit()
                flash("Câmara cadastrada.", "success")
                return redirect(url_for("inventory.chambers"))
            except IntegrityError:
                db.session.rollback()
                flash("Já existe uma câmara com essa identificação.", "danger")

    chamber_rows = db.session.scalars(select(Chamber).order_by(Chamber.name)).all()
    return render_template("inventory/chambers.html", chambers=chamber_rows)


@bp.post("/chambers/<int:chamber_id>/toggle")
@login_required
def toggle_chamber(chamber_id):
    chamber = db.get_or_404(Chamber, chamber_id)
    chamber.active = not chamber.active
    db.session.commit()
    state = "ativada" if chamber.active else "desativada"
    flash(f'Câmara "{chamber.name}" {state}.', "success")
    return redirect(url_for("inventory.chambers"))


@bp.route("/chambers/<int:chamber_id>/edit", methods=["GET", "POST"])
@login_required
def edit_chamber(chamber_id):
    chamber = db.get_or_404(Chamber, chamber_id)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip() or None
        if not name:
            flash("Informe a identificação da câmara.", "danger")
        else:
            chamber.name = name
            chamber.description = description
            try:
                db.session.commit()
                flash("Câmara atualizada.", "success")
                return redirect(url_for("inventory.chambers"))
            except IntegrityError:
                db.session.rollback()
                flash("Já existe outra câmara com essa identificação.", "danger")
    return render_template("inventory/chamber_form.html", chamber=chamber)


@bp.route("/lots/new", methods=["GET", "POST"])
@login_required
def new_lot():
    active_chambers = db.session.scalars(
        select(Chamber).where(Chamber.active.is_(True)).order_by(Chamber.name)
    ).all()
    classifications = db.session.scalars(
        select(Classification).where(Classification.active.is_(True)).order_by(Classification.name)
    ).all()
    presentations = db.session.scalars(
        select(Presentation).where(Presentation.active.is_(True)).order_by(Presentation.name)
    ).all()

    if request.method == "POST":
        code = request.form.get("code", "").strip()
        classification_id = request.form.get("classification_id", type=int)
        presentation_id = request.form.get("presentation_id", type=int)
        origin = request.form.get("origin", "").strip().upper()
        vessel_or_broker = request.form.get("vessel_or_broker", "").strip()
        farm_or_producer = request.form.get("farm_or_producer", "").strip()
        origin_location = request.form.get("origin_location", "").strip()
        provenance_note = (
            request.form.get("mar_provenance_note", "") if origin == "MAR"
            else request.form.get("pond_provenance_note", "")
        ).strip() or None
        quantity = _parse_quantity(request.form.get("quantity", ""))
        received_on = _parse_date(request.form.get("received_on", ""))
        expires_on_raw = request.form.get("expires_on", "").strip()
        expires_on = _parse_date(expires_on_raw)
        chamber_id = request.form.get("chamber_id", type=int)
        notes = request.form.get("notes", "").strip() or None

        errors = []
        if not code or len(code) > 60:
            errors.append("Informe um código de lote com até 60 caracteres.")
        elif db.session.scalar(select(Lot.id).where(
            func.lower(Lot.code) == code.lower(),
            Lot.establishment_id == current_user.establishment_id,
        )):
            errors.append("Esse código de lote já está cadastrado.")
        classification = db.session.get(Classification, classification_id) if classification_id else None
        presentation = db.session.get(Presentation, presentation_id) if presentation_id else None
        if not classification or not classification.active:
            errors.append("Selecione uma classificação ativa.")
        if not presentation or not presentation.active:
            errors.append("Selecione uma apresentação ativa.")
        if origin not in {"MAR", "VIVEIRO"}:
            errors.append("Selecione a origem do camarão.")
        elif origin == "MAR" and not vessel_or_broker:
            errors.append("Informe a embarcação ou o atravessador.")
        elif origin == "VIVEIRO" and (not farm_or_producer or not origin_location):
            errors.append("Informe a fazenda ou produtor e o local de origem.")
        if not quantity:
            errors.append("Informe uma quantidade maior que zero, com até três casas decimais.")
        if not received_on:
            errors.append("Informe uma data de entrada válida.")
        if expires_on_raw and not expires_on:
            errors.append("Informe uma data de validade válida.")
        if received_on and expires_on and expires_on < received_on:
            errors.append("A validade não pode ser anterior à data de entrada.")
        chamber = db.session.get(Chamber, chamber_id) if chamber_id else None
        if not chamber or not chamber.active:
            errors.append("Selecione uma câmara ativa.")

        if errors:
            for message in errors:
                flash(message, "danger")
        else:
            lot = Lot(
                code=code.upper(),
                classification_id=classification.id,
                presentation_id=presentation.id,
                origin=origin,
                vessel_or_broker=vessel_or_broker or None,
                farm_or_producer=farm_or_producer or None,
                origin_location=origin_location or None,
                provenance_note=provenance_note,
                received_on=received_on,
                expires_on=expires_on,
                current_chamber_id=chamber.id,
                notes=notes,
            )
            db.session.add(lot)
            try:
                db.session.flush()
                db.session.add(Movement(
                    lot_id=lot.id,
                    user_id=current_user.id,
                    chamber_id=chamber.id,
                    kind="ENTRADA",
                    quantity_kg=quantity,
                    occurred_at=datetime.now(timezone.utc),
                    notes="Entrada inicial do lote",
                    is_initial=True,
                ))
                db.session.commit()
                flash("Lote cadastrado. A entrada inicial foi registrada.", "success")
                return redirect(url_for("inventory.lot_detail", lot_id=lot.id))
            except IntegrityError:
                db.session.rollback()
                flash("Não foi possível salvar o lote. Confira se o código já está em uso.", "danger")

    return render_template(
        "inventory/lot_form.html", chambers=active_chambers,
        classifications=classifications, presentations=presentations,
        today=datetime.now(ZoneInfo("America/Fortaleza")).date().isoformat(),
    )


@bp.get("/lots/<int:lot_id>")
@login_required
def lot_detail(lot_id):
    lot = db.get_or_404(Lot, lot_id)
    balance = _balance_for_lot(lot.id)
    movements = db.session.scalars(
        select(Movement).where(Movement.lot_id == lot.id)
        .order_by(Movement.occurred_at.asc(), Movement.id.asc())
    ).all()
    initial_entry = next((movement for movement in movements if movement.is_initial), None)
    total_entries = sum((movement.quantity_kg for movement in movements if movement.kind == "ENTRADA"), Decimal("0"))
    total_exits = sum((movement.quantity_kg for movement in movements if movement.kind == "SAIDA"), Decimal("0"))
    running_balance = Decimal("0")
    movement_rows = []
    for movement in movements:
        if movement.kind == "ENTRADA":
            running_balance += movement.quantity_kg
        else:
            running_balance -= movement.quantity_kg
        movement_rows.append((movement, running_balance))
    return render_template(
        "inventory/lot_detail.html", lot=lot, balance=balance,
        movements=movements, movement_rows=movement_rows, initial_entry=initial_entry,
        total_entries=total_entries, total_exits=total_exits,
    )


@bp.route("/movements/new", methods=["GET", "POST"])
@login_required
def new_movement():
    stock = stock_by_lot(current_user.establishment_id)
    lot_rows = db.session.execute(
        select(Lot, func.coalesce(stock.c.balance, 0).label("balance"))
        .outerjoin(stock, stock.c.lot_id == Lot.id)
        .order_by(Lot.code)
    ).all()
    selected_type = request.args.get("type", request.form.get("kind", "ENTRADA")).upper()
    if selected_type not in {"ENTRADA", "SAIDA"}:
        selected_type = "ENTRADA"
    selected_lot_id = request.args.get("lot_id", type=int) or request.form.get("lot_id", type=int)

    if request.method == "POST":
        selected_type = request.form.get("kind", "").strip().upper()
        selected_lot_id = request.form.get("lot_id", type=int)
        quantity = _parse_quantity(request.form.get("quantity", ""))
        occurred_raw = request.form.get("occurred_at", "").strip()
        notes = request.form.get("notes", "").strip() or None
        errors = []
        if selected_type not in {"ENTRADA", "SAIDA"}:
            errors.append("Selecione entrada ou saída.")
        if not selected_lot_id:
            errors.append("Selecione um lote.")
        if not quantity:
            errors.append("Informe uma quantidade maior que zero, com até três casas decimais.")
        lot = db.session.execute(
            select(Lot).where(Lot.id == selected_lot_id).with_for_update()
        ).scalar_one_or_none() if selected_lot_id else None
        if selected_lot_id and not lot:
            errors.append("O lote selecionado não foi encontrado.")
        if not occurred_raw:
            occurred_at = datetime.now(timezone.utc)
        else:
            try:
                occurred_local = datetime.fromisoformat(occurred_raw)
                if occurred_local.tzinfo is None:
                    occurred_local = occurred_local.replace(tzinfo=ZoneInfo("America/Fortaleza"))
                occurred_at = occurred_local.astimezone(timezone.utc)
            except ValueError:
                occurred_at = None
                errors.append("Informe uma data e horário válidos.")

        balance = _balance_for_lot(lot.id) if lot else Decimal("0")
        if lot and selected_type == "SAIDA" and quantity and quantity > balance:
            errors.append(f"A quantidade solicitada supera o saldo disponível de {balance:.3f} kg.")
        if lot and selected_type == "ENTRADA" and not lot.current_chamber.active:
            errors.append("A câmara atual está inativa. Reative-a antes de registrar uma entrada.")

        if errors:
            for message in errors:
                flash(message, "danger")
        else:
            db.session.add(Movement(
                lot_id=lot.id,
                user_id=current_user.id,
                chamber_id=lot.current_chamber_id if selected_type == "ENTRADA" else None,
                kind=selected_type,
                quantity_kg=quantity,
                occurred_at=occurred_at,
                notes=notes,
            ))
            try:
                db.session.commit()
                flash("Entrada registrada." if selected_type == "ENTRADA" else "Saída registrada.", "success")
                return redirect(url_for("inventory.lot_detail", lot_id=lot.id))
            except Exception:
                db.session.rollback()
                raise

    return render_template(
        "inventory/movement_form.html", lots=lot_rows,
        selected_type=selected_type, selected_lot_id=selected_lot_id,
        now_local=datetime.now(ZoneInfo("America/Fortaleza")).strftime("%Y-%m-%dT%H:%M"),
    )
