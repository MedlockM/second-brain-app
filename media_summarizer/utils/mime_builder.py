from __future__ import annotations

import email
import time
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _message_id(domain: str | None = None) -> str:
    if not domain:
        domain = "example.local"
    return f"<{uuid.uuid4().hex}.{int(time.time())}@{domain}>"


def build_multipart_amp_email(
    subject: str,
    from_addr: str,
    to_addr: str,
    text_part: str,
    amp_part: str,
    html_part: str,
    message_id_domain: str | None = None,
) -> str:
    """
    Build a raw RFC-822 message with multipart/alternative parts in the order:
    - text/plain
    - text/x-amp-html
    - text/html

    Returns the message serialized as string for SES send_raw_email.
    """
    outer = MIMEMultipart("alternative")
    outer["Subject"] = subject
    outer["From"] = from_addr
    outer["To"] = to_addr
    outer["MIME-Version"] = "1.0"
    outer["Message-ID"] = _message_id(message_id_domain)
    outer["Date"] = email.utils.formatdate(localtime=True)

    txt = MIMEText(text_part, _subtype="plain", _charset="utf-8")
    amp = MIMEText(amp_part, _subtype="x-amp-html", _charset="utf-8")
    html = MIMEText(html_part, _subtype="html", _charset="utf-8")

    # The order matters for Gmail AMP
    outer.attach(txt)
    outer.attach(amp)
    outer.attach(html)

    return outer.as_string()