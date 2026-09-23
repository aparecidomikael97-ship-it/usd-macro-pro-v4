from pathlib import Path

SOURCE=Path("autopilot_v107.py").read_text(encoding="utf-8")

def test_provider_gate_uses_canonical_registry_not_seven_pair_error():
    assert "Consulta fora do universo canônico de 28 pares." in SOURCE
    assert "Consulta fora dos sete pares/intervalos previstos." not in SOURCE

def test_scanner_is_wired_to_adaptive_28_plan():
    assert "scan_jobs=build_scan_plan" in SOURCE
    assert 'ordered_pairs=[j.display_pair for j in scan_jobs]' in SOURCE
    assert '"execution_expansion_enabled"]=False' in SOURCE

def test_new_crosses_use_m15_derivation_and_remain_research_only():
    assert 'if not _legacy_pair:' in SOURCE
    assert 'derive_from_m15(_m15_for_derive,"1h")' in SOURCE
    assert 'derive_from_m15(_m15_for_derive,"4h")' in SOURCE
    assert 'tec["p0_execution_expansion_enabled"]=False' in SOURCE
