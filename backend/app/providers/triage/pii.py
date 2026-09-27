"""PII redaction applied before complaint text leaves our infrastructure.

See docs/adr/0004-pii-and-data-governance.md. Only the complaint body and the
location are ever sent to the hosted model; `reporter_contact` never is. This
module removes the obvious direct identifiers that citizens type into the body.
It is a best-effort filter, not a guarantee — which is why the ADR also limits
*what* is sent, not just how it is scrubbed.
"""

from __future__ import annotations

import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Pakistani CNIC: 12345-1234567-1 (with or without dashes, 13 digits)
_CNIC = re.compile(r"\b\d{5}-?\d{7}-?\d\b")
# Phones: +92 3xx xxxxxxx, 03xx-xxxxxxx, landlines like 021-3456789, or any 10+ digit run
_PHONE = re.compile(r"(?:\+?92[\s-]?|0)\d{2,3}[\s-]?\d{6,8}\b|\b\d{10,}\b")


def redact(text: str) -> str:
    text = _EMAIL.sub("[EMAIL]", text)
    text = _CNIC.sub("[CNIC]", text)
    text = _PHONE.sub("[PHONE]", text)
    return text
