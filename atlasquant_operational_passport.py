"""AtlasQuant Operational Passport.

Builds a transparent, human-review research card from observed metrics. A
passport is evidence organization, not a profitability certificate and never
promotes a strategy automatically.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from math import isfinite

SCHEMA="ATLASQUANT_OPERATIONAL_PASSPORT_V1"
PASSPORT_STATES={"TESTING","OBSERVATION","HUMAN_REVIEW_CANDIDATE","PAPER","PAUSED"}


@dataclass(frozen=True)
class OperationalPassportInput:
    strategy: str
    state: str
    trades: int
    expectancy_r: float
    profit_factor: float
    net_r: float
    max_drawdown_r: float
    assets_covered: int
    sessions_covered: int
    regimes_covered: int
    paper_trades: int
    paper_expectancy_r: float | None
    data_quality_pct: float | None
    last_validation_date: date | None = None


def _finite(name: str, value: float) -> float:
    out=float(value)
    if not isfinite(out):
        raise ValueError(f"{name} deve ser finito")
    return out


def build_operational_passport(params: OperationalPassportInput)->dict[str,object]:
    state=str(params.state or "").upper()
    if state not in PASSPORT_STATES:
        raise ValueError("state inválido")
    if params.trades < 0 or params.paper_trades < 0:
        raise ValueError("amostras não podem ser negativas")
    for name,value in (
        ("assets_covered",params.assets_covered),
        ("sessions_covered",params.sessions_covered),
        ("regimes_covered",params.regimes_covered),
    ):
        if int(value) < 0:
            raise ValueError(f"{name} não pode ser negativo")

    expectancy=_finite("expectancy_r",params.expectancy_r)
    pf=_finite("profit_factor",params.profit_factor)
    net=_finite("net_r",params.net_r)
    dd=abs(_finite("max_drawdown_r",params.max_drawdown_r))
    if params.data_quality_pct is None:
        quality=None
    else:
        quality=_finite("data_quality_pct",params.data_quality_pct)
        if not 0 <= quality <= 100:
            raise ValueError("data_quality_pct deve estar entre 0 e 100")

    if params.paper_expectancy_r is None:
        paper_gap=None
    else:
        paper_expectancy=_finite("paper_expectancy_r",params.paper_expectancy_r)
        paper_gap=round(paper_expectancy-expectancy,4)

    evidence_flags=[]
    if params.trades < 50:
        evidence_flags.append("amostra histórica ainda pequena")
    if params.regimes_covered < 2:
        evidence_flags.append("cobertura de regimes insuficiente")
    if params.sessions_covered < 2:
        evidence_flags.append("cobertura de sessões limitada")
    if quality is None:
        evidence_flags.append("qualidade dos dados não registrada")
    elif quality < 70:
        evidence_flags.append("qualidade dos dados abaixo de 70%")
    if params.paper_trades < 20:
        evidence_flags.append("paper trading ainda insuficiente")
    if paper_gap is not None and abs(paper_gap) > 0.25:
        evidence_flags.append("diferença relevante entre paper e backtest")

    human_review_ready=not evidence_flags and state in {"OBSERVATION","HUMAN_REVIEW_CANDIDATE","PAPER"}

    return {
        "schema":SCHEMA,
        "strategy":params.strategy,
        "state":state,
        "observed_metrics":{
            "trades":params.trades,
            "expectancy_r":expectancy,
            "profit_factor":pf,
            "net_r":net,
            "max_drawdown_r":dd,
        },
        "coverage":{
            "assets":params.assets_covered,
            "sessions":params.sessions_covered,
            "regimes":params.regimes_covered,
        },
        "paper":{
            "trades":params.paper_trades,
            "expectancy_r":params.paper_expectancy_r,
            "gap_vs_backtest_r":paper_gap,
        },
        "data_quality_pct":quality,
        "last_validation_date":params.last_validation_date.isoformat() if params.last_validation_date else None,
        "evidence_flags":evidence_flags,
        "eligible_for_human_review":human_review_ready,
        "automatic_promotion":False,
        "profit_probability":None,
        "interpretation":(
            "O passaporte resume evidência observada e lacunas de validação. "
            "Não certifica lucro futuro e não promove o operacional automaticamente."
        ),
        "input":asdict(params),
    }


__all__=["SCHEMA","PASSPORT_STATES","OperationalPassportInput","build_operational_passport"]
