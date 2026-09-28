"""Research planning and source-backed synthesis; never fetches or calls a model."""
from datetime import datetime
from atlasquant_aion_cognitive_orchestrator import build_research_plan
from .evidence import Evidence, assess, safe_text


def synthesize(question: str, records: tuple[Evidence, ...], now: datetime) -> dict:
    question = safe_text(question)
    assessment = assess(records, now)
    conflicts = set(assessment["conflict_claims"])
    facts, inferences, unknown = [], [], []
    for original, row in zip(records, assessment["records"]):
        conflicting = " ".join(row["claim"].casefold().split()) in conflicts
        item = {**row, "origin": original.origin.value,
                "uncertainty": original.uncertainty,
                "confirmation_scope": "SUPPLIED_EVIDENCE_ONLY"}
        if conflicting:
            item.update(truth_state="UNKNOWN", uncertainty="CONFLICTING_SOURCES")
        destination = {"CONFIRMED": facts, "INFERENCE": inferences}.get(item["truth_state"], unknown)
        destination.append(item)
    return {
        "status": "CONFLICT" if conflicts else "EVIDENCE_AVAILABLE" if facts else "NEEDS_EVIDENCE",
        "plan": build_research_plan(question, specialists=()),
        "facts": facts, "inferences": inferences, "unknown": unknown,
        "conflicts": sorted(conflicts), "freshness": assessment["freshness"],
        "answers_user_question": False,
        "reason": "Evidence inventory; no semantic answer verification or independent source retrieval.",
        "web_research_executed": False, "provider_called": False,
        "execution_authorized": False,
    }
