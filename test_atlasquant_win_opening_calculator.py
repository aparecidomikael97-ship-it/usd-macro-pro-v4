"""WIN opening calculator, deterministic arithmetic and no live-signal claims."""
import math

import pytest

from atlasquant_win_opening_calculator import calculate_win_opening
from atlasquant_trader_radar_compact_ui import trader_radar_html
from atlasquant_reference_ui import JS


@pytest.mark.parametrize("iron,oil,vix,wanted,side,level", [
    ("+1,47", "+0,95", "-0,62", 3.04, "Alta", "Moderado"),
    (-1.47, -0.95, 0.62, -3.04, "Baixa", "Moderado"),
    (0, 0, 0, 0, "Neutro", "Indefinido"),
    (1.49, 0, 0, 1.49, "Neutro", "Indefinido"),
    (1.5, 0, 0, 1.5, "Alta", "Fraco"),
    (2.49, 0, 0, 2.49, "Alta", "Fraco"),
    (2.5, 0, 0, 2.5, "Alta", "Moderado"),
    (4.5, 0, 0, 4.5, "Alta", "Moderado"),
    (4.51, 0, 0, 4.51, "Alta", "Forte"),
    (-1.5, 0, 0, -1.5, "Baixa", "Fraco"),
    (-2.5, 0, 0, -2.5, "Baixa", "Moderado"),
    (-4.5, 0, 0, -4.5, "Baixa", "Moderado"),
    (-4.51, 0, 0, -4.51, "Baixa", "Forte"),
])
def test_signed_vix_and_symmetric_score_thresholds(iron, oil, vix, wanted, side, level):
    result=calculate_win_opening(iron_pct=iron,oil_pct=oil,vix_pct=vix)
    assert result is not None
    assert result["score"] == pytest.approx(wanted)
    assert result["side"] == side
    assert result["level"] == level
    assert result["trade_signal"] is False
    assert result["accuracy_verified"] is False


@pytest.mark.parametrize("bad", [None, True, False, "", "   ", "NaN", "Inf",
    "1,2,3", "a1", "1.2.3", "-101", 100.01, float("nan"), math.inf])
def test_invalid_inputs_never_generate_a_bias(bad):
    for field in ("iron_pct", "oil_pct", "vix_pct"):
        data={"iron_pct": 1, "oil_pct": 1, "vix_pct": -1}
        data[field]=bad
        assert calculate_win_opening(**data) is None


def test_manual_calculator_exists_in_both_brazil_tabs_and_starts_blank():
    html=trader_radar_html(selected="radar")
    assert html.count('data-win-calculator') == 2
    for name in ("iron", "oil", "vix"):
        assert html.count('data-win-input="'+name+'"') == 2
    assert "Calculadora do Viés do WIN" in html
    assert "Calcular viés preliminar" in html
    assert 'data-win-clear' in html and 'data-win-example' in html
    assert "Sem sinal" not in html  # no fabricated live order
    assert "Cálculo local, sem envio dos valores." in html
    assert "A leitura manual não verifica fonte" in html
    assert "Automático conectado" not in html


def test_browser_code_handles_each_region_independently_without_network():
    assert "querySelectorAll('[data-win-calculator]').forEach" in JS
    assert "Math.round((iron+oil-vix)*10000)" in JS
    assert "Math.abs(n)<=100" in JS
    assert "setTriggerValue('navigate'" in JS  # navigation remains available
    region=JS.split("// WIN opening manual calculator:",1)[1].split("root.querySelectorAll('[data-route]')",1)[0]
    assert "fetch(" not in region
    assert "setTriggerValue(" not in region
    assert "localStorage" not in region
    assert "EXEMPLO FICTÍCIO" in region
