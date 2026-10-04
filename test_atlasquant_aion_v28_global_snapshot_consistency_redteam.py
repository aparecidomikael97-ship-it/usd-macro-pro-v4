"""V2.8 global consistency red-team: consistency is never atomicity."""
from copy import deepcopy
import pytest
from test_atlasquant_aion_v26_core_health_adapter import evidence, build, board

class AtomicityTruthTests:
    __test__ = True

    def test_maximum_health_never_claims_atomic_snapshot(self):
        payload = build(**deepcopy(evidence()))
        assert board(payload)["state"] == "CONFIRMED"
        assert payload.get("snapshot_atomic") is False
        assert payload["execution_allowed"] is False

    @pytest.mark.parametrize("claim", [True, "true", 1])
    def test_runtime_atomic_claim_is_overridden(self, claim):
        from atlasquant_aion_core_health_adapter import build_loaded_runtime_health_evidence
        payload = build_loaded_runtime_health_evidence({"snapshot_atomic": claim, "snapshot": {"atomic": claim}})
        assert payload.get("snapshot_atomic") is False
        assert payload["execution_allowed"] is False
