from pathlib import Path
from datetime import timezone
from zoneinfo import ZoneInfo

from flask import Flask, g

from .config import Config
from .extensions import csrf, db, login_manager, migrate


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    if app.testing:
        @app.before_request
        def refresh_test_user_cache():
            # The pytest fixture keeps one app context open, unlike a production request cycle.
            g.pop("_login_user", None)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Entre para acessar o sistema."
    login_manager.login_message_category = "warning"

    @app.template_filter("fortaleza_time")
    def fortaleza_time(value):
        if value is None:
            return ""
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(ZoneInfo("America/Fortaleza"))

    from . import models
    from .tenancy import install_tenant_isolation
    install_tenant_isolation()
    from .auth.routes import bp as auth_bp
    from .inventory.routes import bp as inventory_bp
    from .main.routes import bp as main_bp

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(models.User, int(user_id))

    app.register_blueprint(auth_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(main_bp)

    from .cli import register_commands
    register_commands(app)

    return app

