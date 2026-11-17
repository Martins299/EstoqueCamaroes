import sys
from types import ModuleType, SimpleNamespace

from app.mail import send_password_reset_email


def test_brevo_sends_password_reset_through_https_api(app, monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return SimpleNamespace(raise_for_status=lambda: None)

    requests_module = ModuleType("requests")
    requests_module.post = fake_post
    monkeypatch.setitem(sys.modules, "requests", requests_module)
    with app.app_context():
        app.config.update({
            "EMAIL_PROVIDER": "BREVO",
            "BREVO_API_KEY": "test-api-key",
            "MAIL_DEFAULT_SENDER": "verified@example.test",
            "MAIL_SENDER_NAME": "Estoque de Camarões",
            "PASSWORD_RESET_TOKEN_MAX_AGE": 3600,
        })
        user = SimpleNamespace(name="Eliseu", email="user@example.test")
        send_password_reset_email(user, "https://app.example.test/auth/reset-password/token")

    assert captured["url"] == "https://api.brevo.com/v3/smtp/email"
    assert captured["headers"]["api-key"] == "test-api-key"
    assert captured["json"]["to"][0]["email"] == "user@example.test"
    assert "https://app.example.test/auth/reset-password/token" in captured["json"]["textContent"]
