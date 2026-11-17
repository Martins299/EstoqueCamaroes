import pytest

from app import create_app
from app.extensions import db
from app.models import Establishment, User


@pytest.fixture
def app(tmp_path):
    database_file = tmp_path / "test.db"
    application = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test-secret-key",
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_file.as_posix()}",
    })
    with application.app_context():
        db.create_all()
        establishment = Establishment(name="Frigorífico de teste")
        db.session.add(establishment)
        db.session.flush()
        user = User(name="Administrador", email="admin@example.com", establishment_id=establishment.id)
        user.set_password("senha-de-teste-segura")
        db.session.add(user)
        db.session.commit()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def logged_in_client(client):
    client.post("/auth/login", data={"email": "admin@example.com", "password": "senha-de-teste-segura"})
    return client

