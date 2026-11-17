from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.extensions import db
from app.models import Chamber, Classification, Establishment, Lot, Movement, Presentation, User


def prepare_catalog(app):
    with app.app_context():
        tenant_id = db.session.scalar(select(User.establishment_id).where(User.email == "admin@example.com"))
        classification = Classification(establishment_id=tenant_id, name="Pistola")
        presentation = Presentation(establishment_id=tenant_id, name="Inteiro")
        chamber = Chamber(establishment_id=tenant_id, name="Câmara de teste")
        db.session.add_all([classification, presentation, chamber])
        db.session.commit()
        return classification.id, presentation.id, chamber.id


def lot_payload(classification_id, presentation_id, chamber_id, **overrides):
    data = {
        "code": "CAM-TEST-001",
        "classification_id": str(classification_id),
        "presentation_id": str(presentation_id),
        "origin": "MAR",
        "vessel_or_broker": "Barco de teste",
        "quantity": "25.500",
        "received_on": "2026-11-17",
        "expires_on": "2026-11-27",
        "chamber_id": str(chamber_id),
        "notes": "",
    }
    data.update(overrides)
    return data


def test_lot_form_shows_conditional_origin_fields(logged_in_client, app):
    prepare_catalog(app)
    response = logged_in_client.get("/lots/new")
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'id="mar-fields"' in page
    assert 'id="pond-fields"' in page
    assert "Embarcação ou atravessador" in page
    assert "Fazenda ou produtor" in page


def test_creating_lot_registers_initial_entry_and_detail(logged_in_client, app):
    classification_id, presentation_id, chamber_id = prepare_catalog(app)
    response = logged_in_client.post(
        "/lots/new",
        data=lot_payload(classification_id, presentation_id, chamber_id),
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Lote cadastrado. A entrada inicial foi registrada." in page
    assert "25.500 kg" in page
    assert "Barco de teste" in page
    lot = db.session.scalar(select(Lot).where(Lot.code == "CAM-TEST-001"))
    movements = db.session.scalars(select(Movement).where(Movement.lot_id == lot.id)).all()
    assert len(movements) == 1
    assert movements[0].kind == "ENTRADA"
    assert movements[0].is_initial is True
    assert movements[0].quantity_kg == Decimal("25.500")


def test_lot_requires_origin_details(logged_in_client, app):
    classification_id, presentation_id, chamber_id = prepare_catalog(app)
    data = lot_payload(classification_id, presentation_id, chamber_id, vessel_or_broker="")
    response = logged_in_client.post("/lots/new", data=data, follow_redirects=True)
    assert response.status_code == 200
    assert "Informe a embarcação ou o atravessador." in response.get_data(as_text=True)
    assert db.session.scalar(select(Lot.id)) is None


def test_pond_origin_stores_farm_and_location(logged_in_client, app):
    classification_id, presentation_id, chamber_id = prepare_catalog(app)
    data = lot_payload(
        classification_id, presentation_id, chamber_id,
        code="CAM-VIVEIRO-001", origin="VIVEIRO", vessel_or_broker="",
        farm_or_producer="Fazenda Boa Água", origin_location="Aracaju",
        pond_provenance_note="Tanque 4",
    )
    response = logged_in_client.post("/lots/new", data=data, follow_redirects=True)
    assert response.status_code == 200
    assert "Fazenda Boa Água" in response.get_data(as_text=True)
    lot = db.session.scalar(select(Lot).where(Lot.code == "CAM-VIVEIRO-001"))
    assert lot.origin == "VIVEIRO"
    assert lot.provenance_note == "Tanque 4"


def create_test_lot(client, app):
    classification_id, presentation_id, chamber_id = prepare_catalog(app)
    client.post("/lots/new", data=lot_payload(classification_id, presentation_id, chamber_id))
    return db.session.scalar(select(Lot).where(Lot.code == "CAM-TEST-001"))


def test_exit_above_available_stock_is_blocked(logged_in_client, app):
    lot = create_test_lot(logged_in_client, app)
    response = logged_in_client.post("/movements/new", data={
        "kind": "SAIDA", "lot_id": str(lot.id), "quantity": "25.501",
        "occurred_at": "2026-11-17T12:00", "notes": "",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert "A quantidade solicitada supera o saldo disponível de 25.500 kg." in response.get_data(as_text=True)
    movements = db.session.scalars(select(Movement).where(Movement.lot_id == lot.id)).all()
    assert len(movements) == 1


def test_valid_entry_and_exit_update_derived_balance(logged_in_client, app):
    lot = create_test_lot(logged_in_client, app)
    entry = logged_in_client.post("/movements/new", data={
        "kind": "ENTRADA", "lot_id": str(lot.id), "quantity": "4.500",
        "occurred_at": "2026-11-17T12:00", "notes": "Reposição",
    }, follow_redirects=True)
    assert entry.status_code == 200
    assert "Saldo disponível" in entry.get_data(as_text=True)
    assert "30.000 kg" in entry.get_data(as_text=True)

    exit_response = logged_in_client.post("/movements/new", data={
        "kind": "SAIDA", "lot_id": str(lot.id), "quantity": "5.000",
        "occurred_at": "2026-11-17T13:00", "notes": "Venda",
    }, follow_redirects=True)
    assert exit_response.status_code == 200
    assert "25.000 kg" in exit_response.get_data(as_text=True)
    assert db.session.scalar(select(db.func.count(Movement.id)).where(Movement.lot_id == lot.id)) == 3


def test_stock_search_and_lot_detail_show_history(logged_in_client, app):
    lot = create_test_lot(logged_in_client, app)
    stock_response = logged_in_client.get("/stock?q=Barco+de+teste")
    assert stock_response.status_code == 200
    assert "CAM-TEST-001" in stock_response.get_data(as_text=True)
    assert "Por classificação" in stock_response.get_data(as_text=True)
    assert "25.500 kg" in stock_response.get_data(as_text=True)
    detail_response = logged_in_client.get(f"/lots/{lot.id}")
    assert detail_response.status_code == 200
    assert "Histórico de movimentações" in detail_response.get_data(as_text=True)


def test_dashboard_flags_lot_expiring_soon(logged_in_client, app):
    classification_id, presentation_id, chamber_id = prepare_catalog(app)
    today = datetime.now(ZoneInfo("America/Fortaleza")).date()
    data = lot_payload(
        classification_id, presentation_id, chamber_id,
        code="CAM-EXPIRA-001",
        received_on=today.isoformat(),
        expires_on=(today + timedelta(days=3)).isoformat(),
    )
    logged_in_client.post("/lots/new", data=data)
    response = logged_in_client.get("/dashboard")
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "CAM-EXPIRA-001" in page
    assert "Próximo" in page
