from datetime import datetime, timezone

from flask_login import UserMixin
from sqlalchemy import CheckConstraint, Index, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.orm import relationship
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


class Establishment(db.Model):
    __tablename__ = "estabelecimentos"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    users = relationship("User", back_populates="establishment")


class User(UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    establishment_id = db.Column(db.Integer, db.ForeignKey("estabelecimentos.id", ondelete="RESTRICT"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    google_sub = db.Column(db.String(255), unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    movements = relationship("Movement", back_populates="user", passive_deletes=True)
    preferences = relationship("UserPreference", back_populates="user", uselist=False, cascade="all, delete-orphan")
    establishment = relationship("Establishment", back_populates="users")

    @property
    def is_active(self):
        return self.active

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Chamber(db.Model):
    __tablename__ = "camaras"
    __table_args__ = (UniqueConstraint("establishment_id", "name", name="uq_camaras_estabelecimento_nome"),)

    id = db.Column(db.Integer, primary_key=True)
    establishment_id = db.Column(db.Integer, db.ForeignKey("estabelecimentos.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(250))
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class Classification(db.Model):
    __tablename__ = "classificacoes"
    __table_args__ = (UniqueConstraint("establishment_id", "name", name="uq_classificacoes_estabelecimento_nome"),)

    id = db.Column(db.Integer, primary_key=True)
    establishment_id = db.Column(db.Integer, db.ForeignKey("estabelecimentos.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)


class Presentation(db.Model):
    __tablename__ = "apresentacoes"
    __table_args__ = (UniqueConstraint("establishment_id", "name", name="uq_apresentacoes_estabelecimento_nome"),)

    id = db.Column(db.Integer, primary_key=True)
    establishment_id = db.Column(db.Integer, db.ForeignKey("estabelecimentos.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)


class Lot(db.Model):
    __tablename__ = "lotes"
    __table_args__ = (
        UniqueConstraint("establishment_id", "code", name="uq_lotes_estabelecimento_codigo"),
        CheckConstraint("origem IN ('MAR', 'VIVEIRO')", name="ck_lotes_origem"),
        CheckConstraint(
            "(origem = 'MAR' AND embarcacao_ou_atravessador IS NOT NULL AND fazenda_ou_produtor IS NULL AND local_origem IS NULL) "
            "OR (origem = 'VIVEIRO' AND fazenda_ou_produtor IS NOT NULL AND local_origem IS NOT NULL AND embarcacao_ou_atravessador IS NULL)",
            name="ck_lotes_procedencia_por_origem",
        ),
        Index("ix_lotes_validade", "validade"),
    )

    id = db.Column(db.Integer, primary_key=True)
    establishment_id = db.Column(db.Integer, db.ForeignKey("estabelecimentos.id", ondelete="CASCADE"), nullable=False, index=True)
    code = db.Column(db.String(60), nullable=False, index=True)
    classification_id = db.Column(db.Integer, db.ForeignKey("classificacoes.id", ondelete="RESTRICT"), nullable=False)
    presentation_id = db.Column(db.Integer, db.ForeignKey("apresentacoes.id", ondelete="RESTRICT"), nullable=False)
    origin = db.Column("origem", db.String(12), nullable=False)
    vessel_or_broker = db.Column("embarcacao_ou_atravessador", db.String(160))
    farm_or_producer = db.Column("fazenda_ou_produtor", db.String(160))
    origin_location = db.Column("local_origem", db.String(160))
    provenance_note = db.Column("observacao_procedencia", db.String(300))
    received_on = db.Column("data_entrada", db.Date, nullable=False)
    expires_on = db.Column("validade", db.Date)
    current_chamber_id = db.Column(db.Integer, db.ForeignKey("camaras.id", ondelete="RESTRICT"), nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    classification = relationship("Classification")
    presentation = relationship("Presentation")
    current_chamber = relationship("Chamber")
    movements = relationship("Movement", back_populates="lot", passive_deletes=True)


class Movement(db.Model):
    __tablename__ = "movimentacoes"
    __table_args__ = (
        CheckConstraint("tipo IN ('ENTRADA', 'SAIDA')", name="ck_movimentacoes_tipo"),
        CheckConstraint("quantidade_kg > 0", name="ck_movimentacoes_quantidade_positiva"),
        CheckConstraint("tipo != 'ENTRADA' OR camara_id IS NOT NULL", name="ck_movimentacoes_entrada_camara"),
        CheckConstraint("entrada_inicial IS FALSE OR tipo = 'ENTRADA'", name="ck_movimentacoes_inicial_e_entrada"),
        Index("ix_movimentacoes_lote_data", "lote_id", "data_hora"),
        Index(
            "uq_movimentacoes_entrada_inicial",
            "lote_id",
            unique=True,
            postgresql_where=text("entrada_inicial IS TRUE"),
            sqlite_where=text("entrada_inicial = 1"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    establishment_id = db.Column(db.Integer, db.ForeignKey("estabelecimentos.id", ondelete="CASCADE"), nullable=False, index=True)
    lot_id = db.Column("lote_id", db.Integer, db.ForeignKey("lotes.id", ondelete="RESTRICT"), nullable=False, index=True)
    user_id = db.Column("usuario_id", db.Integer, db.ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False)
    chamber_id = db.Column("camara_id", db.Integer, db.ForeignKey("camaras.id", ondelete="RESTRICT"))
    kind = db.Column("tipo", db.String(8), nullable=False)
    quantity_kg = db.Column("quantidade_kg", Numeric(12, 3), nullable=False)
    occurred_at = db.Column("data_hora", db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    notes = db.Column("observacoes", db.Text)
    is_initial = db.Column("entrada_inicial", db.Boolean, nullable=False, default=False)

    lot = relationship("Lot", back_populates="movements")
    user = relationship("User", back_populates="movements")
    chamber = relationship("Chamber")


class UserPreference(db.Model):
    __tablename__ = "preferencias_usuario"
    __table_args__ = (
        CheckConstraint("tema IN ('CLARO', 'ESCURO')", name="ck_preferencias_tema"),
        CheckConstraint("cor_destaque IN ('AZUL', 'VERDE', 'TERRACOTA')", name="ck_preferencias_cor"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column("usuario_id", db.Integer, db.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, unique=True)
    theme = db.Column("tema", db.String(8), nullable=False, default="CLARO")
    accent_color = db.Column("cor_destaque", db.String(12), nullable=False, default="AZUL")

    user = relationship("User", back_populates="preferences")

