from getpass import getpass

import click
from sqlalchemy import func, select

from .extensions import db
from .models import Classification, Establishment, Presentation, User


def register_commands(app):
    @app.cli.command("create-admin")
    def create_admin():
        """Create the first administrator interactively."""
        name = click.prompt("Nome do administrador").strip()
        establishment_name = click.prompt("Nome do estabelecimento").strip()
        email = click.prompt("E-mail").strip().lower()
        if not name or "@" not in email:
            raise click.ClickException("Informe nome e e-mail válidos.")
        exists = db.session.scalar(select(User.id).where(func.lower(User.email) == email))
        if exists:
            raise click.ClickException("Já existe um usuário com esse e-mail.")
        password = getpass("Senha (mínimo de 12 caracteres): ")
        confirmation = getpass("Confirme a senha: ")
        if len(password) < 12:
            raise click.ClickException("A senha precisa ter pelo menos 12 caracteres.")
        if password != confirmation:
            raise click.ClickException("As senhas não conferem.")
        establishment = Establishment(name=establishment_name)
        db.session.add(establishment)
        db.session.flush()
        user = User(name=name, email=email, establishment_id=establishment.id)
        user.set_password(password)
        db.session.add(user)
        for model, names in (
            (Classification, ("Pistola", "Escolha", "Espigão", "Misturado")),
            (Presentation, ("Inteiro", "Descabeçado", "Filé")),
        ):
            db.session.add_all(model(establishment_id=establishment.id, name=value) for value in names)
        db.session.commit()
        click.echo("Administrador criado.")

    @app.cli.command("seed-catalogs")
    def seed_catalogs():
        """Insert the initial shrimp classifications and presentations."""
        establishments = db.session.scalars(select(Establishment)).all()
        for establishment in establishments:
            for model, names in (
            (Classification, ("Pistola", "Escolha", "Espigão", "Misturado")),
            (Presentation, ("Inteiro", "Descabeçado", "Filé")),
            ):
                for name in names:
                    exists = db.session.scalar(select(model.id).where(
                        model.name == name, model.establishment_id == establishment.id
                    ))
                    if not exists:
                        db.session.add(model(name=name, establishment_id=establishment.id))
        db.session.commit()
        click.echo("Classificações e apresentações iniciais conferidas.")

