"""Declarative intent selection; ambiguous intents never switch task context."""
from dataclasses import dataclass
import re
import unicodedata

from .context import Context, FUTURE_DOMAINS
from .registry import Registry, SPECS, SPEC_BY_NAME


def words(text: str) -> set[str]:
    if not isinstance(text, str) or not text.strip() or len(text) > 8000:
        raise ValueError("bounded non-empty intent required")
    normalized = unicodedata.normalize("NFKD", text).casefold()
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    return set(re.findall(r"[a-z0-9]+", normalized))


@dataclass(frozen=True)
class Route:
    status: str
    capability: str | None
    reason: str
    candidates: tuple[str, ...] = ()
    required_context: str | None = None


def route(intent: str, context: Context, registry: Registry, *, capability: str | None = None) -> Route:
    tokens = words(intent)
    if context.domain in FUTURE_DOMAINS:
        return Route("UNAVAILABLE", None, "FUTURE_CONTEXT_DISABLED")
    # Metadata registry is the source of aliases; scoring never activates modules.
    scored = []
    for item in registry.metadata.list():
        score = len(tokens & set(item.aliases))
        if score:
            scored.append((score, item.specialist.upper()))
    scored.sort(key=lambda x: (-x[0], x[1]))
    if capability is None:
        if not scored:
            return Route("UNKNOWN", None, "INTENT_NOT_RECOGNIZED")
        candidates = tuple(name for score, name in scored if score == scored[0][0])
        if len(candidates) > 1:
            return Route("CLARIFICATION_REQUIRED", None, "AMBIGUOUS_INTENT", candidates)
        capability = candidates[0]
    spec = SPEC_BY_NAME.get(capability)
    if spec is None:
        return Route("UNAVAILABLE", capability, "CAPABILITY_NOT_REGISTERED")
    if spec.admin_only and context.role != "ADMIN":
        return Route("DENIED", capability, "ROLE_DENIED")
    state = registry.get(capability)
    if not state["available"]:
        return Route("UNAVAILABLE", capability, state["reason"])
    if spec.domain and context.domain != spec.domain:
        return Route("CONTEXT_SWITCH_REQUIRED", capability, "EXPLICIT_CONTEXT_REQUIRED",
                     required_context=spec.domain.value)
    return Route("SELECTED", capability, "LOCAL_DATA_ONLY")
