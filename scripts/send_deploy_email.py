"""
Invia la notifica email di deploy giornaliero completato.

Configurazione via variabili d'ambiente o GitHub Secrets:
    SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD
    SMTP_FROM, DEPLOY_NOTIFICATION_TO
    SMTP_USE_TLS, SMTP_USE_SSL
"""
import argparse
import datetime
import os
import smtplib
from email.message import EmailMessage

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None


DEFAULT_TO = "massimiliano.ferrando@gmail.com"
DEFAULT_BODY = """Ferrandi la DDG \u00e8 online!! Gloria al Doria e ai Ferrandi !!!

Clicca sul seguente Link per accedere al Sito !!!
https://legnaro72.github.io/dediche-musicali-ff/
"""


def ensure_expected_repository() -> bool:
    expected = os.environ.get("DEPLOY_EXPECTED_REPOSITORY", "").strip().lower()
    current = os.environ.get("GITHUB_REPOSITORY", "").strip().lower()
    if not expected or not current or expected == current:
        return True
    print(f"Email notifica saltata: repository corrente {current}, atteso {expected}.")
    return False


def get_rome_today() -> str:
    if ZoneInfo is not None:
        return datetime.datetime.now(ZoneInfo("Europe/Rome")).date().isoformat()
    return datetime.date.today().isoformat()


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def build_message(date_str: str) -> EmailMessage:
    sender = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USERNAME")
    recipients = [
        recipient.strip()
        for recipient in os.environ.get("DEPLOY_NOTIFICATION_TO", DEFAULT_TO).split(",")
        if recipient.strip()
    ]
    if not sender:
        raise ValueError("SMTP_FROM o SMTP_USERNAME non configurato.")
    if not recipients:
        raise ValueError("DEPLOY_NOTIFICATION_TO non contiene destinatari validi.")

    message = EmailMessage()
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message["Subject"] = f"DDG {date_str} online"
    message.set_content(os.environ.get("DEPLOY_NOTIFICATION_BODY", DEFAULT_BODY))
    return message


def send_message(message: EmailMessage) -> None:
    host = os.environ.get("SMTP_HOST", "").strip()
    username = os.environ.get("SMTP_USERNAME", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "")
    default_port = "465" if env_bool("SMTP_USE_SSL") else "587"
    port_value = os.environ.get("SMTP_PORT", "").strip() or default_port
    port = int(port_value)

    if not host or not username or not password:
        raise ValueError("SMTP_HOST, SMTP_USERNAME e SMTP_PASSWORD sono obbligatori.")

    use_ssl = env_bool("SMTP_USE_SSL", False)
    use_tls = env_bool("SMTP_USE_TLS", not use_ssl)

    smtp_cls = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with smtp_cls(host, port, timeout=30) as smtp:
        if use_tls and not use_ssl:
            smtp.starttls()
        smtp.login(username, password)
        smtp.send_message(message)


def main() -> None:
    parser = argparse.ArgumentParser(description="Invia email DDG online.")
    parser.add_argument("--date", default="", help="Data pubblicata YYYY-MM-DD.")
    args = parser.parse_args()

    date_str = args.date.strip() or os.environ.get("DDG_ONLINE_DATE", "").strip() or get_rome_today()
    if not ensure_expected_repository():
        return
    message = build_message(date_str)
    send_message(message)
    print(f"Email notifica inviata a {message['To']}")


if __name__ == "__main__":
    main()
