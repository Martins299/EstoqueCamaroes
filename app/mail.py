import smtplib
from email.message import EmailMessage

from flask import current_app


def send_password_reset_email(user, reset_url):
    config = current_app.config
    content = (
        f"Olá, {user.name}.\n\n"
        "Recebemos uma solicitação para redefinir a senha da sua conta. "
        f"Acesse o link abaixo em até {config['PASSWORD_RESET_TOKEN_MAX_AGE'] // 60} minutos:\n\n"
        f"{reset_url}\n\n"
        "Se você não solicitou a alteração, ignore esta mensagem."
    )

    if config["EMAIL_PROVIDER"] == "BREVO":
        import requests

        if not config["BREVO_API_KEY"] or not config["MAIL_DEFAULT_SENDER"]:
            raise RuntimeError("Configure BREVO_API_KEY e MAIL_DEFAULT_SENDER para enviar e-mails pelo Brevo.")
        response = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "accept": "application/json",
                "api-key": config["BREVO_API_KEY"],
                "content-type": "application/json",
            },
            json={
                "sender": {"name": config["MAIL_SENDER_NAME"], "email": config["MAIL_DEFAULT_SENDER"]},
                "to": [{"email": user.email, "name": user.name}],
                "subject": "Redefinição de senha — Estoque de Camarões",
                "textContent": content,
            },
            timeout=20,
        )
        response.raise_for_status()
        return

    if not all((config["MAIL_SERVER"], config["MAIL_USERNAME"], config["MAIL_PASSWORD"], config["MAIL_DEFAULT_SENDER"])):
        raise RuntimeError("Configure as variáveis MAIL_* no arquivo .env para habilitar o envio de e-mails.")

    message = EmailMessage()
    message["Subject"] = "Redefinição de senha — Estoque de Camarões"
    message["From"] = config["MAIL_DEFAULT_SENDER"]
    message["To"] = user.email
    message.set_content(content)

    with smtplib.SMTP(config["MAIL_SERVER"], config["MAIL_PORT"], timeout=15) as smtp:
        if config["MAIL_USE_TLS"]:
            smtp.starttls()
        smtp.login(config["MAIL_USERNAME"], config["MAIL_PASSWORD"])
        smtp.send_message(message)
