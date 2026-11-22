from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, select

from ..extensions import db
from ..models import Chamber, Lot, Movement, UserPreference
from ..stock import stock_by_lot

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    return render_template("main/home.html")


def redirect_to_dashboard():
    from flask import redirect, url_for
    return redirect(url_for("main.dashboard"))


@bp.get("/dashboard")
@login_required
def dashboard():
    today = datetime.now(ZoneInfo("America/Fortaleza")).date()
    stock = stock_by_lot(current_user.establishment_id)
    total_kg = db.session.scalar(
        select(func.coalesce(func.sum(stock.c.balance), 0)).where(stock.c.balance > 0)
    ) or 0
    active_lots = db.session.scalar(
        select(func.count()).select_from(stock).where(stock.c.balance > 0)
    ) or 0
    active_chambers = db.session.scalar(
        select(func.count(Chamber.id)).where(
            Chamber.active.is_(True), Chamber.establishment_id == current_user.establishment_id
        )
    ) or 0
    expiring_lots = db.session.execute(
        select(Lot, stock.c.balance)
        .join(stock, stock.c.lot_id == Lot.id)
        .where(
            stock.c.balance > 0,
            Lot.expires_on.is_not(None),
            Lot.expires_on <= today + timedelta(days=7),
        )
        .order_by(Lot.expires_on.asc())
        .limit(5)
    ).all()
    recent_movements = db.session.execute(
        select(Movement)
        .order_by(Movement.occurred_at.desc())
        .limit(6)
    ).scalars().all()

    return render_template(
        "main/dashboard.html",
        total_kg=total_kg,
        active_lots=active_lots,
        active_chambers=active_chambers,
        expiring_lots=expiring_lots,
        recent_movements=recent_movements,
        today=today,
    )


@bp.route("/preferences", methods=["GET", "POST"])
@login_required
def preferences():
    preference = current_user.preferences

    if request.method == "POST":
        theme = request.form.get("theme", "").strip().upper()
        establishment_name = request.form.get("establishment_name", "").strip()

        errors = []

        if theme not in {"CLARO", "ESCURO"}:
            errors.append("Selecione o tema claro ou escuro.")

        if not establishment_name:
            errors.append("Informe o nome do estabelecimento.")
        elif len(establishment_name) > 140:
            errors.append("O nome do estabelecimento deve ter até 140 caracteres.")

        if errors:
            for message in errors:
                flash(message, "danger")
        else:
            if preference is None:
                preference = UserPreference(user_id=current_user.id)
                db.session.add(preference)

            preference.theme = theme
            current_user.establishment.name = establishment_name

            db.session.commit()
            flash("Preferências atualizadas.", "success")
            return redirect(url_for("main.preferences"))

    return render_template(
        "main/preferences.html",
        theme=preference.theme if preference else "CLARO",
        establishment_name=current_user.establishment.name,
    )