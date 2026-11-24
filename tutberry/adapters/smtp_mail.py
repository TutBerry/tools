"""SMTP transport for booking notifications."""
import smtplib
from email.message import EmailMessage

from tutberry.workers.errors import PermanentFailure, TransientFailure


class SmtpMail:
    def __init__(self, host, port):
        self.host, self.port = host, port

    def send(self, to, subject, body):
        message = EmailMessage()
        message["From"] = "noreply@tutberry.example"
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        try:
            with smtplib.SMTP(self.host, self.port, timeout=2) as smtp:
                smtp.send_message(message)
        except smtplib.SMTPRecipientsRefused as exc:
            if all(code >= 500 for code, _ in exc.recipients.values()):
                raise PermanentFailure("Recipient rejected") from exc
            raise TransientFailure("Recipient temporarily unavailable") from exc
        except smtplib.SMTPResponseException as exc:
            if exc.smtp_code >= 500:
                raise PermanentFailure("SMTP permanent rejection") from exc
            raise TransientFailure("SMTP temporary rejection") from exc
        except OSError as exc:
            raise TransientFailure("SMTP unavailable") from exc
