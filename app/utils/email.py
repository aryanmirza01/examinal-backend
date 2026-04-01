import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings

def send_reply_email(to_email: str, original_subject: str, reply_content: str):
    """
    Sends a professional reply via Gmail SMTP.
    Requires MAIL_PASSWORD to be an App Password if using Gmail.
    """
    if not settings.MAIL_PASSWORD:
        print("MAIL_PASSWORD not set. Recording reply in DB only.")
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = f"Examinal Support <{settings.MAIL_FROM}>"
        msg['To'] = to_email
        msg['Subject'] = f"Response: {original_subject}"

        # High-Fidelity Professional Template
        body = f"""
Hello,

This is an official response from the Examinal Assessment Portal regarding your inquiry.

--------------------------------------------------------------------------------
REPLY CONTENT:
{reply_content}
--------------------------------------------------------------------------------

If you have further questions, please maintain this thread.

Best regards,
Examinal Administration Node
{settings.MAIL_FROM}
        """
        msg.attach(MIMEText(body, 'plain'))

        # SMTP Handshake
        server = smtplib.SMTP(settings.MAIL_SERVER, settings.MAIL_PORT)
        if settings.MAIL_USE_TLS:
            server.starttls()
        
        server.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(settings.MAIL_FROM, to_email, text)
        server.quit()
        print(f"Email successfully transmitted to {to_email}")
        return True
    except Exception as e:
        print(f"Email transmission failure: {e}")
        return False
