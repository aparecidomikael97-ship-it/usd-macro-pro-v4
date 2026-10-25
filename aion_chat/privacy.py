"""Credential redaction: defense in depth, not universal DLP."""
import re
from collections.abc import Mapping

PATTERNS = [re.compile(r"(?i)\b(password|senha|api[_ -]?key|access[_ -]?token|secret|authorization)\b\s*[:=]\s*[^\s,;]+"),
            re.compile(r"\b(?:sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9_]{8,})\b"),
            re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*"),
            re.compile(r"-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----")]


def redact(value):
    if isinstance(value, str):
        for p in PATTERNS:
            value = p.sub("[REDACTED]", value)
    elif isinstance(value, Mapping):
        # G66: custom Mapping (e.g. UserDict) must not become an opaque
        # default=str repr with sensitive fields exposed in local JSON.
        # Preserve ordinary key labels; redact their sensitive values.
        sensitive = (r"(?i)(?:password|senha|secret|token|credential|"
                     r"authorization|access[_-]?token|accessToken|"
                     r"client[_-]?secret|clientSecret|api[_-]?key|apiKey)")
        value = {k: "[REDACTED]" if re.fullmatch(sensitive, k)
                 else redact(v) for k, v in value.items()}
    elif isinstance(value, (list, tuple)):
        # G62: json.dumps serializes tuples as JSON arrays, but the previous
        # redactor left their nested secrets untouched. Normalize both to a
        # redacted list BEFORE staging/hashing so no tuple bypass remains.
        value = [redact(v) for v in value]
    return value
