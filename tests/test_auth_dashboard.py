def test_login_page_is_available(client):
    response = client.get("/auth/login")
    assert response.status_code == 200
    assert "Acesse sua conta" in response.get_data(as_text=True)


def test_dashboard_requires_login(client):
    response = client.get("/dashboard")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_valid_login_opens_dashboard(client):
    response = client.post(
        "/auth/login",
        data={"email": "admin@example.com", "password": "senha-de-teste-segura"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Estoque armazenado" in response.get_data(as_text=True)
    assert "Seu histórico começa com o primeiro lote" in response.get_data(as_text=True)


def test_invalid_login_shows_generic_error(client):
    response = client.post(
        "/auth/login",
        data={"email": "admin@example.com", "password": "incorreta"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "E-mail ou senha inválidos." in response.get_data(as_text=True)


def test_logout_ends_session(logged_in_client):
    response = logged_in_client.post("/auth/logout", follow_redirects=True)
    assert response.status_code == 200
    dashboard_response = logged_in_client.get("/dashboard")
    assert dashboard_response.status_code == 302


def test_stock_page_requires_login(client):
    response = client.get("/stock")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_chamber_page_requires_login(client):
    response = client.get("/chambers")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_chamber_can_be_created_and_deactivated(logged_in_client, app):
    from app.extensions import db
    from app.models import Chamber

    response = logged_in_client.post("/chambers", data={"name": "Câmara 01", "description": "Principal"}, follow_redirects=True)
    assert response.status_code == 200
    assert "Câmara cadastrada." in response.get_data(as_text=True)
    chamber = db.session.scalar(db.select(Chamber).where(Chamber.name == "Câmara 01"))
    assert chamber is not None and chamber.active is True

    response = logged_in_client.post(f"/chambers/{chamber.id}/toggle", follow_redirects=True)
    assert response.status_code == 200
    assert "desativada" in response.get_data(as_text=True)
    db.session.refresh(chamber)
    assert chamber.active is False


def test_chamber_duplicate_name_is_rejected(logged_in_client, app):
    from app.extensions import db
    from app.models import Chamber, User

    tenant_id = db.session.scalar(db.select(User.establishment_id).where(User.email == "admin@example.com"))
    db.session.add(Chamber(establishment_id=tenant_id, name="Câmara 01"))
    db.session.commit()
    response = logged_in_client.post("/chambers", data={"name": "Câmara 01"}, follow_redirects=True)
    assert response.status_code == 200
    assert "Já existe uma câmara" in response.get_data(as_text=True)


def test_stock_page_shows_empty_state(logged_in_client):
    response = logged_in_client.get("/stock")
    assert response.status_code == 200
    assert "Nenhum lote cadastrado" in response.get_data(as_text=True)


def test_chamber_can_be_edited(logged_in_client, app):
    from app.extensions import db
    from app.models import Chamber, User

    tenant_id = db.session.scalar(db.select(User.establishment_id).where(User.email == "admin@example.com"))
    chamber = Chamber(establishment_id=tenant_id, name="Câmara antiga", description="Antiga")
    db.session.add(chamber)
    db.session.commit()
    response = logged_in_client.post(
        f"/chambers/{chamber.id}/edit",
        data={"name": "Câmara principal", "description": "Armazenamento principal"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Câmara atualizada." in response.get_data(as_text=True)
    db.session.refresh(chamber)
    assert chamber.name == "Câmara principal"
    assert chamber.description == "Armazenamento principal"


def test_preferences_are_saved_and_applied(logged_in_client, app):
    from app.extensions import db
    from app.models import UserPreference

    response = logged_in_client.post(
        "/preferences",
        data={"theme": "ESCURO", "accent_color": "VERDE"},
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Preferências salvas." in page
    assert 'data-theme="ESCURO"' in page
    assert 'data-accent="VERDE"' in page
    preference = db.session.scalar(db.select(UserPreference))
    assert preference.theme == "ESCURO"
    assert preference.accent_color == "VERDE"

