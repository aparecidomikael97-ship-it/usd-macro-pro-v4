"""Credential redaction: defense in depth, not universal DLP."""
import re
from collections.abc import Mapping

PATTERNS = [re.compile(r"(?i)\b(password|senha|api[_ -]?key|access[_ -]?token|refresh[_ -]?token|private[_ -]?key|client[_ -]?secret|secret|authorization)\b\s*[:=]\s*[^\s,;]+"),
            re.compile(r"\b(?:sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9_]{8,})\b"),
            re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*"),
            re.compile(r"-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----")]


# G68: quoted JSON member names in chat text have a closing '"' between
# the field name and ':'. Preserve JSON punctuation and replace only the
# string value (including escaped quote sequences), not the whole member.
_QUOTED_JSON_SECRET = re.compile(
    r'(?i)(?P<prefix>"(?:password|senha|secret|token|credential|'
    r'authorization|access[_-]?token|accessToken|refresh[_-]?token|'
    r'refreshToken|private[_-]?key|privateKey|client[_-]?secret|'
    r'clientSecret|api[_-]?key|apiKey)"\s*:\s*")'
    r'(?:\\.|[^"\\])*"'
)


def redact(value):
    if isinstance(value, str):
        value = _QUOTED_JSON_SECRET.sub(
            lambda match: match.group("prefix") + '[REDACTED]"', value
        )
        for p in PATTERNS:
            value = p.sub("[REDACTED]", value)
    elif isinstance(value, Mapping):
        # G66: custom Mapping (e.g. UserDict) must not become an opaque
        # default=str repr with sensitive fields exposed in local JSON.
        # Preserve ordinary key labels; redact their sensitive values.
        sensitive = (r"(?i)(?:password|senha|secret|token|credential|"
                     r"authorization|access[_-]?token|accessToken|"
                     r"refresh[_-]?token|refreshToken|"
                     r"private[_-]?key|privateKey|"
                     r"client[_-]?secret|clientSecret|api[_-]?key|apiKey)")
        def masked_items():
            for k, v in value.items():
                # G67: the redactor is shared by Outbox and chat/store,
                # which does not run the Outbox's G66 pre-BEGIN key guard.
                if not isinstance(k, str):
                    raise ValueError("G67_NONSTRING_REDACT_KEY_DENY")
                yield k, ("[REDACTED]" if re.fullmatch(sensitive, k.strip())
                          else redact(v))
        value = dict(masked_items())
    elif isinstance(value, (list, tuple)):
        # G62: json.dumps serializes tuples as JSON arrays, but the previous
        # redactor left their nested secrets untouched. Normalize both to a
        # redacted list BEFORE staging/hashing so no tuple bypass remains.
        value = [redact(v) for v in value]
    return value
