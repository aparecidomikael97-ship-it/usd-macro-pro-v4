"""Credential redaction: defense in depth, not universal DLP."""
import re

PATTERNS = [re.compile(r"(?i)\b(password|senha|api[_ -]?key|access[_ -]?token|secret|authorization)\b\s*[:=]\s*[^\s,;]+"),
            re.compile(r"\b(?:sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9_]{8,})\b"),
            re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*"),
            re.compile(r"-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----")]


def redact(value):
    if isinstance(value, str):
        for p in PATTERNS:
            value = p.sub("[REDACTED]", value)
    elif isinstance(value, dict):
        value = {k: "[REDACTED]" if re.fullmatch(r"(?i)(password|senha|secret|api_key|token|credential)", k)
                 else redact(v) for k, v in value.items()}
    elif isinstance(value, list):
        value = [redact(v) for v in value]
    return value
