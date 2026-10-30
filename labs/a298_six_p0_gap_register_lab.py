"""A298 LAB: six canonical AION P0 blocker map and no-cost dependency audit.

Source mapping: archived AION_P0_AUDITORIA_RAPIDA_CLAUDE_2026-10-22.md
and GitHub PR descriptions #1464, #1504, #1624, #1625, #1693,
#1694, #1696, #1743-#1748. PR descriptions are evidence ABOUT work,
not inspection of native code or independent Security homologation.

ZERO new paid services; no production operation, Worker or deploy.
"""
from dataclasses import asdict, dataclass
import json

SCHEMA = "ATLASQUANT_AION_SIX_CANONICAL_P0_GAP_REGISTER_LAB_V1"
REPO = "https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4"
HARD_NO_GO = "HARD_NO_GO"
ZERO_AUTO_RESEND = True


@dataclass(frozen=True)
class CanonicalP0:
    id: str
    title: str
    acceptance: str
    observed_gap: str
    free_lab_next_action: str
    needs_real_independence: str
    evidence_prs: tuple
    homologated: bool = False


P0_REGISTRY = (
    CanonicalP0(
        "P0-1", "Identidade e autorização real do proprietário",
        "Comprovar origem HUMAN_OWNER, cadeia de aprovações, revogação, "
        "anti-replay e posse das chaves em raiz de confiança independente.",
        "Duas assinaturas locais e booleans de aprovação podem ser "
        "recriadas ou falsificadas pelo mesmo host; A295 demonstrou isso.",
        "Desenhar cerimônia offline de matrícula/consentimento/revogação "
        "e testes de impersonação, sem registrar chaves reais.",
        "Identidade de proprietário controlada fora do host AION, "
        "prova de consentimento verificável e revisão independente.",
        (1694, 1746, 1747),
    ),
    CanonicalP0(
        "P0-2", "Autenticidade dos recibos externos",
        "Validar recibos reais emitidos por origem confiável, "
        "custodiantes distintos, versão mais recente, high-water, "
        "disponibilidade, revogação e recuperação histórica.",
        "Ed25519 sintética e HMAC local verificam formato/consistência, "
        "mas não comprovam emissor, custódia ou efeito do provedor.",
        "Definir esquema estrito de recibo e testes negativos de "
        "troca de chave, falso emissor, perda e replay, sem fornecedor real.",
        "Raiz verificável de provedor/custodiante verdadeiramente "
        "independente com recibos reais e custódia durável.",
        (1694, 1745, 1747),
    ),
    CanonicalP0(
        "P0-3", "Primeira operação e duplicidade semântica",
        "Demonstrar reserva durável da PRIMEIRA tentativa por evento "
        "de negócio, sem reenvio após TIMEOUT/UNKNOWN e sem duplicar "
        "quando IDs técnicos mudam.",
        "PR #1464 mostra que apagar o diário reabre a reserva; "
        "#1625 reintroduz mesma operação após rollback; guard local "
        "ou callback host pode mentir (#1693).",
        "Especificar identidade semântica e matriz concorrência/"
        "crash/novo request-ID, preservando UNKNOWN e zero SEND.",
        "Primeira reserva e reconhecimento de efeito ligados a "
        "custódia imutável independente e provedor real reconciliável.",
        (1464, 1625, 1693),
    ),
    CanonicalP0(
        "P0-4", "H0 reinício, rollback e reconciliação",
        "Demonstrar cold restart, recuperação após queda e restauração, "
        "high-water independente, rejeição de estado ambíguo e "
        "autorização renovada ao reabrir incidente.",
        "Rollback conjunto SQLite + testemunha local permite reexecutar "
        "evento; o mesmo host pode re-ancorar histórico antigo.",
        "Automatizar casos de restauração total, queda, ACK perdido "
        "e incidente reaberto em tempdir/CI, sem restaurar cliente.",
        "Testemunha de alta-maré imutável fora do host, "
        "reconciliação autoritativa e processo externo de recuperação.",
        (1624, 1745, 1748),
    ),
    CanonicalP0(
        "P0-5", "Identidade do SQLite realmente acessado",
        "Autenticar o arquivo/handle nativo que a conexão SQLite "
        "efetivamente usa (VFS/FD), entre leitura, caminho e WAL/SHM, "
        "incluindo Windows/Linux e troca de arquivo.",
        "path/stat/inode/data_version detectam algumas trocas, "
        "mas não provam FD/VFS nem histórico após reposição; "
        "#1504 testou extensão C NATIVA apenas no LAB.",
        "Inventariar G17/G18, revisar carregamento da extensão C e "
        "testar troca de arquivo, mesma inode e sidecars sem instalar.",
        "Verificação nativa segura e autenticada, supply chain revisada "
        "e integração real comprovada na conexão usada em operação.",
        (1504, 1618, 1696, 1744),
    ),
    CanonicalP0(
        "P0-6", "Escrita SQLite, COMMIT e durabilidade nativa",
        "Provar transações WAL, concorrência, COMMIT e recuperação "
        "após perda de confirmação, falha de energia, rollbacks "
        "e efeitos duplicados na operação real.",
        "A292 prova COMMIT antes/depois do ACK nos seis writers, mas "
        "métodos SQL auxiliares e escrita de outro PID contornam "
        "o marcador; persistência e recuperação independente faltam.",
        "Ampliar testes de falha WAL/SHM/COMMIT e inventário de "
        "mutadores sem alterar logs canônicos nem efetuar SEND.",
        "Garantia nativa efetiva de durabilidade, identidade, ACK/"
        "reconciliação e custódia contra adulteração/rollback externo.",
        (1743, 1744, 1748),
    ),
)


def registry_as_dict():
    return {
        "schema": SCHEMA,
        "source_class": "CANONICAL_HISTORICAL_P0_MAPPING_AND_PR_DESCRIPTIONS",
        "source_not_equivalent_to_native_code_review": True,
        "p0": [asdict(item) for item in P0_REGISTRY],
        "hard_no_go": True,
        "worker_disabled": True,
        "deploy_disabled": True,
        "zero_auto_resend": True,
        "new_spending_authorized": False,
        "can_homologate_from_lab": False,
        "known_homologated_count": 0,
        "no_claim_of_external_identity_or_custody": True,
    }


def audit_six_p0_registry():
    """Fail closed on missing/duplicated P0 and accidental GO metadata."""
    report = registry_as_dict()
    issues = []
    ids = [item.id for item in P0_REGISTRY]
    if ids != [f"P0-{i}" for i in range(1, 7)]:
        issues.append("CANONICAL_SIX_P0_ORDER_OR_COUNT_CHANGED")
    if any(item.homologated for item in P0_REGISTRY):
        issues.append("UNAUTHORIZED_P0_HOMOLOGATION")
    for item in P0_REGISTRY:
        if not all((
            item.id, item.title, item.acceptance, item.observed_gap,
            item.free_lab_next_action, item.needs_real_independence,
        )):
            issues.append("P0_MISSING_ACCEPTANCE_OR_BLOCKER:" + item.id)
        if len(item.evidence_prs) < 2:
            issues.append("P0_EVIDENCE_REFERENCES_TOO_FEW:" + item.id)
        if len(set(item.evidence_prs)) != len(item.evidence_prs):
            issues.append("P0_DUPLICATE_EVIDENCE_REFERENCE:" + item.id)
        if not all(type(n) is int and n > 0 for n in item.evidence_prs):
            issues.append("P0_INVALID_EVIDENCE_PR:" + item.id)
    report.update({
        "issues": sorted(set(issues)),
        "valid_lab_inventory": not issues,
        "homologated_count_computed": sum(
            item.homologated for item in P0_REGISTRY
        ),
        "blocked_count_computed": sum(
            not item.homologated for item in P0_REGISTRY
        ),
        "decision": HARD_NO_GO,
        "ready_for_real_worker": False,
        "external_trust_verified": False,
        "all_evidence_is_pr_description_or_prior_lab": True,
    })
    return report


def render_lab_status_json():
    """Machine-readable handoff; every consumer must preserve HARD NO-GO."""
    return json.dumps(
        audit_six_p0_registry(), ensure_ascii=False, sort_keys=True,
        indent=2,
    )


__all__ = [
    "SCHEMA", "REPO", "HARD_NO_GO", "ZERO_AUTO_RESEND",
    "CanonicalP0", "P0_REGISTRY", "registry_as_dict",
    "audit_six_p0_registry", "render_lab_status_json",
]
