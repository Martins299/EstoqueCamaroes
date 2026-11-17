from urllib.parse import urlsplit

from sqlalchemy import select

from app.extensions import db
from app.models import Chamber, Classification, User


def register(client, email, establishment="Meu Frigorífico"):
    return client.post("/auth/register", data={
        "establishment_name": establishment,
        "name": "Responsável",
        "email": email,
        "password": "senha-nova-segura-123",
        "password_confirmation": "senha-nova-segura-123",
    }, follow_redirects=True)


def test_registration_creates_independent_establishment_and_defaults(client, app):
    response = register(client, "novo@example.com")
    assert response.status_code == 200
    assert "Estoque armazenado" in response.get_data(as_text=True)
    with app.app_context():
        user = db.session.scalar(select(User).where(User.email == "novo@example.com"))
        assert user is not None
        assert user.establishment.name == "Meu Frigorífico"
        classes = db.session.scalars(select(Classification).where(
            Classification.establishment_id == user.establishment_id
        )).all()
        assert {item.name for item in classes} == {"Pistola", "Escolha", "Espigão", "Misturado"}


def test_duplicate_email_and_short_password_are_rejected(client, app):
    register(client, "repetido@example.com")
    client.post("/auth/logout")
    response = client.post("/auth/register", data={
        "establishment_name": "Outro negócio", "name": "Outro", "email": "repetido@example.com",
        "password": "curta", "password_confirmation": "curta",
    }, follow_redirects=True)
    page = response.get_data(as_text=True)
    assert "Este e-mail já possui uma conta." in page
    assert "A senha deve ter pelo menos 12 caracteres." in page


def test_establishment_data_is_hidden_from_another_account(client, app):
    client.post("/auth/login", data={"email": "admin@example.com", "password": "senha-de-teste-segura"})
    client.post("/chambers", data={"name": "Câmara privada"})
    with app.app_context():
        private_chamber = db.session.scalar(select(Chamber).where(Chamber.name == "Câmara privada"))
        private_id = private_chamber.id

    second_client = app.test_client()
    response = register(second_client, "outro@example.com", "Outro Estabelecimento")
    assert response.status_code == 200
    page = second_client.get("/chambers").get_data(as_text=True)
    assert "Câmara privada" not in page
    assert second_client.get(f"/chambers/{private_id}/edit").status_code == 404


def test_password_reset_token_changes_password_and_cannot_be_reused(client, app, monkeypatch):
    sent = {}

    def capture_email(user, reset_url):
        sent["email"] = user.email
        sent["url"] = reset_url

    monkeypatch.setattr("app.auth.routes.send_password_reset_email", capture_email)
    response = client.post("/auth/forgot-password", data={"email": "admin@example.com"}, follow_redirects=True)
    assert "Se o e-mail estiver cadastrado" in response.get_data(as_text=True)
    assert sent["email"] == "admin@example.com"

    reset_path = urlsplit(sent["url"]).path
    response = client.post(reset_path, data={
        "password": "senha-redefinida-123", "password_confirmation": "senha-redefinida-123"
    }, follow_redirects=True)
    assert "Senha redefinida" in response.get_data(as_text=True)
    old_token_response = client.get(reset_path, follow_redirects=True)
    assert "inválido ou expirou" in old_token_response.get_data(as_text=True)

    with app.app_context():
        user = db.session.scalar(select(User).where(User.email == "admin@example.com"))
        assert user.check_password("senha-redefinida-123")
        assert not user.check_password("senha-de-teste-segura")


def test_google_sign_in_links_only_a_verified_existing_email(client, app, monkeypatch):
    app.config["GOOGLE_CLIENT_ID"] = "test-client-id.apps.googleusercontent.com"
    monkeypatch.setattr("app.auth.routes._verify_google_credential", lambda _token, _client: {
        "email": "admin@example.com", "email_verified": True, "sub": "google-user-123", "iss": "https://accounts.google.com"
    })
    response = client.post("/auth/google", data={"credential": "test-id-token"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")
    with app.app_context():
        user = db.session.scalar(select(User).where(User.email == "admin@example.com"))
        assert user.google_sub == "google-user-123"


def test_google_sign_in_requires_verified_email(client, app, monkeypatch):
    app.config["GOOGLE_CLIENT_ID"] = "test-client-id.apps.googleusercontent.com"
    monkeypatch.setattr("app.auth.routes._verify_google_credential", lambda _token, _client: {
        "email": "admin@example.com", "email_verified": False, "sub": "google-user-123"
    })
    response = client.post("/auth/google", data={"credential": "test-id-token"}, follow_redirects=True)
    assert "precisa ter um e-mail verificado" in response.get_data(as_text=True)
