from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from sqlalchemy import func, select
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from ..extensions import db
from ..mail import send_password_reset_email
from ..models import Classification, Establishment, Presentation, User

bp = Blueprint("auth", __name__, url_prefix="/auth")


def _reset_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="senha-estoque-camarao")


def _valid_email(value):
    return len(value) <= 255 and value.count("@") == 1 and "." in value.rsplit("@", 1)[1]


def _verify_google_credential(credential, client_id):
    from google.auth.transport.requests import Request as GoogleRequest
    from google.oauth2 import id_token

    return id_token.verify_oauth2_token(credential, GoogleRequest(), client_id)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        establishment_name = request.form.get("establishment_name", "").strip()
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirmation = request.form.get("password_confirmation", "")
        errors = []
        if not establishment_name or len(establishment_name) > 140:
            errors.append("Informe o nome do estabelecimento (até 140 caracteres).")
        if not name or len(name) > 120:
            errors.append("Informe o nome do responsável (até 120 caracteres).")
        if not _valid_email(email):
            errors.append("Informe um e-mail válido.")
        elif db.session.scalar(select(User.id).where(func.lower(User.email) == email)):
            errors.append("Este e-mail já possui uma conta.")
        if len(password) < 12:
            errors.append("A senha deve ter pelo menos 12 caracteres.")
        if password != confirmation:
            errors.append("A confirmação da senha não confere.")
        if errors:
            for error in errors:
                flash(error, "danger")
        else:
            establishment = Establishment(name=establishment_name)
            db.session.add(establishment)
            db.session.flush()
            user = User(name=name, email=email, establishment_id=establishment.id)
            user.set_password(password)
            db.session.add(user)
            db.session.add_all([
                Classification(establishment_id=establishment.id, name=value)
                for value in ("Pistola", "Escolha", "Espigão", "Misturado")
            ])
            db.session.add_all([
                Presentation(establishment_id=establishment.id, name=value)
                for value in ("Inteiro", "Descabeçado", "Filé")
            ])
            db.session.commit()
            login_user(user, remember=False, fresh=True)
            flash("Estabelecimento cadastrado. Seus dados ficarão separados dos demais.", "success")
            return redirect(url_for("main.dashboard"))
    return render_template("auth/register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = db.session.scalar(select(User).where(func.lower(User.email) == email))
        if user and user.active and user.check_password(password):
            login_user(user, remember=False, fresh=True)
            return redirect(url_for("main.dashboard"))
        flash("E-mail ou senha inválidos.", "danger")

    return render_template("auth/login.html", google_client_id=current_app.config["GOOGLE_CLIENT_ID"])


@bp.post("/google")
def google_login():
    credential = request.form.get("credential", "")
    client_id = current_app.config["GOOGLE_CLIENT_ID"]
    if not client_id or not credential:
        flash("O acesso pelo Google não está configurado.", "danger")
        return redirect(url_for("auth.login"))
    try:
        claims = _verify_google_credential(credential, client_id)
    except Exception:
        current_app.logger.exception("Falha ao validar credencial do Google")
        flash("Não foi possível validar o acesso pelo Google. Tente novamente.", "danger")
        return redirect(url_for("auth.login"))

    email = (claims.get("email") or "").strip().lower()
    google_sub = claims.get("sub")
    if claims.get("email_verified") is not True or not _valid_email(email) or not google_sub:
        flash("A conta Google precisa ter um e-mail verificado.", "danger")
        return redirect(url_for("auth.login"))

    user = db.session.scalar(select(User).where(User.google_sub == google_sub))
    if user is None:
        user = db.session.scalar(select(User).where(func.lower(User.email) == email))
        if user is None:
            flash("Crie sua conta com este mesmo e-mail antes de entrar pelo Google.", "warning")
            return redirect(url_for("auth.register"))
        if user.google_sub and user.google_sub != google_sub:
            flash("Este e-mail já está vinculado a outra conta Google.", "danger")
            return redirect(url_for("auth.login"))
        user.google_sub = google_sub
        db.session.commit()

    if not user.active:
        flash("Esta conta está inativa. Entre em contato com o responsável.", "danger")
        return redirect(url_for("auth.login"))
    login_user(user, remember=False, fresh=True)
    return redirect(url_for("main.dashboard"))


@bp.post("/logout")
def logout():
    logout_user()
    flash("Você saiu do sistema.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = db.session.scalar(select(User).where(func.lower(User.email) == email)) if _valid_email(email) else None
        if user and user.active:
            token = _reset_serializer().dumps({"id": user.id, "password_hash": user.password_hash})
            reset_url = f"{current_app.config['PUBLIC_BASE_URL']}{url_for('auth.reset_password', token=token)}"
            try:
                send_password_reset_email(user, reset_url)
            except Exception:
                current_app.logger.exception("Falha ao enviar e-mail de redefinição de senha")
                if current_app.testing:
                    raise
        flash("Se o e-mail estiver cadastrado, você receberá um link para redefinir a senha.", "info")
        return redirect(url_for("auth.forgot_password"))
    return render_template("auth/forgot_password.html")


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        payload = _reset_serializer().loads(token, max_age=current_app.config["PASSWORD_RESET_TOKEN_MAX_AGE"])
        user = db.session.get(User, payload.get("id"))
        if not user or not user.active or user.password_hash != payload.get("password_hash"):
            raise BadSignature("Token inválido")
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        flash("O link de redefinição é inválido ou expirou. Solicite outro.", "danger")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirmation = request.form.get("password_confirmation", "")
        if len(password) < 12:
            flash("A senha deve ter pelo menos 12 caracteres.", "danger")
        elif password != confirmation:
            flash("A confirmação da senha não confere.", "danger")
        else:
            user.set_password(password)
            db.session.commit()
            flash("Senha redefinida. Entre com sua nova senha.", "success")
            return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html")

