"""Commercial launch guard for AtlasQuant.

This is a product-readiness gate, not a legal certification and not a trading
permission. It is intentionally fail-closed and never launches, publishes or
charges customers automatically.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SCHEMA="ATLASQUANT_COMMERCIAL_LAUNCH_GUARD_V1"

@dataclass(frozen=True)
class CommercialEvidence:
    private_access_ok: bool
    account_admin_ok: bool
    distribution_ok: bool
    terms_privacy_ok: bool
    data_licensing_ok: bool
    support_ok: bool
    academy_minimum_ok: bool
    billing_ok: bool
    sales_role_isolated_ok: bool = True
    account_revocation_ok: bool = True
    audit_manifest_ok: bool = True

_FIELDS=(
    "private_access_ok",
    "account_admin_ok",
    "distribution_ok",
    "terms_privacy_ok",
    "data_licensing_ok",
    "support_ok",
    "academy_minimum_ok",
    "billing_ok",
    "sales_role_isolated_ok",
    "account_revocation_ok",
    "audit_manifest_ok",
)

_LABELS={
    "private_access_ok":"Acesso privado/login",
    "account_admin_ok":"Administração de contas",
    "distribution_ok":"Distribuição instalável",
    "terms_privacy_ok":"Termos/privacidade/riscos",
    "data_licensing_ok":"Licenciamento comercial de dados",
    "support_ok":"Suporte operacional",
    "academy_minimum_ok":"Academy mínima para lançamento",
    "billing_ok":"Pagamento/assinatura",
    "sales_role_isolated_ok":"Isolamento do perfil SALES",
    "account_revocation_ok":"Revogação de contas/sessões",
    "audit_manifest_ok":"Auditoria administrativa sem credenciais",
}

def assess_commercial_launch(evidence:CommercialEvidence)->dict[str,Any]:
    invalid=[name for name in _FIELDS if not isinstance(getattr(evidence,name,None),bool)]
    blockers=[]
    if invalid:
        blockers.extend("Flag inválida: "+name for name in invalid)
    for name in _FIELDS:
        value=getattr(evidence,name,None)
        if isinstance(value,bool) and not value:
            blockers.append(_LABELS[name]+" pendente")
    return {
        "schema":SCHEMA,
        "status":"REVIEWABLE" if not blockers else "BLOCKED",
        "blockers":blockers,
        "manual_launch_required":True,
        "automatic_launch":False,
        "legal_certification":False,
        "trading_permission_changed":False,
    }
