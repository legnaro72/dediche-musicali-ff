"""
Invia la notifica email quando un Ferrando salva un Votami Plus.

Usa gli stessi secret SMTP del deploy. Il destinatario e' il primo indirizzo
di DEPLOY_NOTIFICATION_TO, oppure massimiliano.ferrando@gmail.com.
"""
import argparse
import os
from email.message import EmailMessage

from send_deploy_email import DEFAULT_TO, send_message


def first_recipient() -> str:
    raw = os.environ.get("DEPLOY_NOTIFICATION_TO", DEFAULT_TO)
    recipients = [item.strip() for item in raw.split(",") if item.strip()]
    return recipients[0] if recipients else DEFAULT_TO


def build_message(args: argparse.Namespace) -> EmailMessage:
    sender = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USERNAME")
    if not sender:
        raise ValueError("SMTP_FROM o SMTP_USERNAME non configurato.")

    thought = args.thought.strip() or "(nessuna frase inserita)"
    body = (
        "Un Ferrando ha votato!!!\n\n"
        f"Data: {args.date}\n"
        f"Ora: {args.time}\n"
        f"Dedica: {args.title} - {args.artist}\n"
        f"Voto: {args.score}\n"
        f"Frase: {thought}\n"
    )

    message = EmailMessage()
    message["From"] = sender
    message["To"] = first_recipient()
    message["Subject"] = "Un Ferrando ha votato!!!"
    message.set_content(body)
    return message


def main() -> None:
    parser = argparse.ArgumentParser(description="Invia email Votami Plus.")
    parser.add_argument("--date", required=True)
    parser.add_argument("--time", required=True)
    parser.add_argument("--score", required=True)
    parser.add_argument("--thought", default="")
    parser.add_argument("--title", default="")
    parser.add_argument("--artist", default="")
    args = parser.parse_args()

    message = build_message(args)
    send_message(message)
    print(f"Email voto inviata a {message['To']}")


if __name__ == "__main__":
    main()
