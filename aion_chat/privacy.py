"""Credential redaction: defense in depth, not universal DLP."""
import json
import re
from collections.abc import Mapping

PATTERNS = [re.compile(r"(?i)\b(password|senha|api[_ -]?key|access[_ -]?token|refresh[_ -]?token|private[_ -]?key|client[_ -]?secret|secret|authorization)\b\s*[:=]\s*[^\s,;]+"),
            re.compile(r"\b(?:sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9_]{8,})\b"),
            re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*"),
            re.compile(r"-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----")]


# G69: fallback for JSON-looking members embedded in ordinary prose or
# incomplete JSON. Decode only the quoted key before deciding whether the
# associated quoted value requires masking; do NOT rewrite the whole prose.
_G69_JSON_MEMBER = re.compile(
    r'(?P<prefix>(?P<key>"(?:\\.|[^"\\])*")\s*:\s*")'
    r'(?:\\.|[^"\\])*"'
)
# G69: a truncated quoted value at end-of-prose must not leave a fake
# credential visible merely because its terminating quote never arrived.
_G69_JSON_MEMBER_UNFINISHED = re.compile(
    r'(?P<prefix>(?P<key>"(?:\\.|[^"\\])*")\s*:\s*")'
    r'(?:\\.|[^"\\])*\\?\Z'
)
_G69_SENSITIVE_KEY = re.compile(
    r"(?i)(?:password|senha|secret|token|credential|authorization|"
    r"access[_-]?token|accessToken|refresh[_-]?token|refreshToken|"
    r"private[_-]?key|privateKey|client[_-]?secret|clientSecret|"
    r"api[_-]?key|apiKey)"
)
_G69_MAX_JSON_INPUT_BYTES = 262144
_G69_MAX_JSON_DEPTH = 64


def _g69_preparse_chat_json(value):
    """Bound UTF-8 bytes and bracket depth BEFORE json.loads materializes.

    Quotes/backslashes are tracked without parsing nodes. An invalid bracket
    sequence is left for JSONDecodeError + old text fallback rather than
    labeling arbitrary plain text as excessive JSON nesting.
    """
    if len(value) > _G69_MAX_JSON_INPUT_BYTES:
        raise ValueError("G69_CHAT_JSON_INPUT_BYTES_DENY")
    try:
        if len(value.encode("utf-8")) > _G69_MAX_JSON_INPUT_BYTES:
            raise ValueError("G69_CHAT_JSON_INPUT_BYTES_DENY")
    except UnicodeEncodeError:
        raise ValueError("G67_INVALID_UNICODE_DENY") from None
    stack = []
    quoted = False
    escaped = False
    excess = False
    # Malformed bracket-like public text uses fallback for modest depth;
    # huge mismatched streams must still be denied before json.loads.
    extremely_deep = False
    unbalanced = False
    for char in value:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            stack.append(char)
            if len(stack) > _G69_MAX_JSON_DEPTH:
                excess = True
            if len(stack) > 128:
                extremely_deep = True
        elif char in "]}":
            if not stack:
                unbalanced = True
            else:
                opening = stack.pop()
                if (opening == "[" and char != "]") or (
                    opening == "{" and char != "}"
                ):
                    unbalanced = True
    # G69 second RED: an unterminated but otherwise consistent 2000-[ JSON
    # candidate must be rejected BEFORE json.loads, not allowed to recurse.
    # Genuine unmatched/mismatched plain bracket text retains text fallback.
    if excess and (not unbalanced or extremely_deep):
        raise ValueError("G69_CHAT_JSON_NESTING_DENY")


def _g69_redact_quoted_member(match):
    try:
        key = json.loads(match.group("key"))
    except (ValueError, UnicodeError):
        return match.group(0)
    if isinstance(key, str) and _G69_SENSITIVE_KEY.fullmatch(key.strip()):
        return match.group("prefix") + '[REDACTED]"'
    return match.group(0)


def _g69_redact_unfinished_member(match):
    try:
        key = json.loads(match.group("key"))
    except (ValueError, UnicodeError):
        return match.group(0)
    if isinstance(key, str) and _G69_SENSITIVE_KEY.fullmatch(key.strip()):
        return match.group("prefix") + "[REDACTED]"
    return match.group(0)


def _g68_unique_chat_json_pairs(pairs):
    """Reject duplicate logical JSON keys, including Unicode-escaped aliases."""
    result = {}
    for key, item in pairs:
        if key in result:
            raise ValueError("G68_DUPLICATE_CHAT_JSON_KEY_DENY")
        result[key] = item
    return result


def redact(value):
    if isinstance(value, str):
        # G68: use decoded member names when the ENTIRE text is JSON, so
        # Unicode-escaped aliases cannot bypass a literal-name regex.
        # Preserve original formatting when nothing needs masking.
        # Re-encode structurally if changed: legacy assignment regex alone
        # could consume JSON delimiters and corrupt an otherwise valid blob.
        # Avoid allocating a potentially huge value.lstrip() copy before
        # the G69 input-byte check. Only inspect the first non-space codepoint.
        first_nonspace = next((ch for ch in value if not ch.isspace()), "")
        if first_nonspace in ("{", "["):
            _g69_preparse_chat_json(value)
            try:
                decoded = json.loads(
                    value, object_pairs_hook=_g68_unique_chat_json_pairs
                )
            except json.JSONDecodeError:
                pass  # Not valid full JSON: retain legacy text-pattern redaction.
            else:
                if isinstance(decoded, (dict, list)):
                    masked = redact(decoded)
                    if masked != decoded:
                        return json.dumps(
                            masked, ensure_ascii=False,
                            separators=(",", ":"), allow_nan=False
                        )
                    return value
        value = _G69_JSON_MEMBER.sub(_g69_redact_quoted_member, value)
        value = _G69_JSON_MEMBER_UNFINISHED.sub(
            _g69_redact_unfinished_member, value
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
