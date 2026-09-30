"""Central catalogue uses existing capability metadata; no inferred activation."""
from dataclasses import dataclass
from types import MappingProxyType

from atlasquant_aion_capabilities import CapabilityRegistry
from .context import Domain


@dataclass(frozen=True)
class Spec:
    name: str
    domain: Domain | None
    legacy_id: str | None
    description: str
    aliases: tuple[str, ...]
    dependency: str | None = None
    future: bool = False
    admin_only: bool = False


SPECS = (
    Spec("ADMINISTRATION", Domain.ADMIN, "admin.status", "Estado do sistema e pendências",
         ("estado", "sistema", "saude", "status", "administracao", "integracoes", "erros"), admin_only=True),
    Spec("MEMORY", None, None, "Decisões e requisitos do contexto atual",
         ("decidimos", "decisao", "decisoes", "memoria", "lembrar", "requisitos", "checkpoint"), "checkpoint"),
    Spec("DEVELOPER", Domain.DEVELOPER, "development.inspect", "Análise e planejamento de código",
         ("codigo", "code", "bug", "regressao", "testes", "revisao"), admin_only=True),
    Spec("RESEARCH", Domain.RESEARCH, "research.synthesize", "Plano e síntese de evidências fornecidas",
         ("pesquise", "pesquisa", "research", "fontes", "assunto", "pesquisar")),
    Spec("VOICE", None, None, "Voz neural oficial via adapter local; geração exige clique explícito",
         ("voz", "audio", "ouvir", "narrar", "transcrever"), "voice.transcription"),
    Spec("CONTENT", Domain.CONTENT, "studio.prepare", "Rascunho de roteiro e briefing",
         ("roteiro", "conteudo", "legenda", "video", "script"), admin_only=True),
    Spec("AUTOMATION", Domain.ADMIN, None, "Agenda persistida; executor de background permanece separado",
         ("automatize", "automacao", "agende", "agendar", "agenda"), "automation.scheduler", admin_only=True),
    Spec("OBSERVABILITY", None, None, "Eventos locais do contexto",
         ("eventos", "observabilidade", "logs"), "checkpoint"),
    Spec("BUSINESS_FUTURE", Domain.BUSINESS, None, "Fora deste sprint",
         ("negocio", "negocios", "business", "vendas"), future=True),
    Spec("TRADER_FUTURE", Domain.TRADER, None, "Fora deste sprint",
         ("trader", "trading", "trade", "mercado", "ordem"), future=True),
    Spec("INVESTMENTS_FUTURE", Domain.INVESTMENTS, None, "Fora deste sprint",
         ("investimento", "investimentos", "investir"), future=True),
)
SPEC_BY_NAME = MappingProxyType({x.name: x for x in SPECS})


class Registry:
    def __init__(
        self,
        *,
        checkpoint_connected: bool,
        voice_connected: bool = False,
        automation_connected: bool = False,
    ):
        for value in (checkpoint_connected, voice_connected, automation_connected):
            if type(value) is not bool:
                raise ValueError("adapter connection state must be an exact bool")
        self._checkpoint = checkpoint_connected
        self._voice = voice_connected
        self._automation = automation_connected
        self.metadata = CapabilityRegistry([
            {"capability_id": "core." + s.name.lower(), "specialist": s.name.lower(),
             "domains": [s.domain.value.lower() if s.domain else "context"],
             "description": s.description, "aliases": s.aliases,
             "allowed_roles": ["ADMIN"] if s.admin_only else ["USER", "ADMIN"],
             "execution_mode": "DRAFT_ONLY" if s.name == "CONTENT" else "READ_ONLY",
             "availability": "UNAVAILABLE" if s.future or s.dependency else "AVAILABLE"}
            for s in SPECS
        ])

    def get(self, name: str) -> dict:
        spec = SPEC_BY_NAME.get(name)
        if spec is None:
            return {"name": name, "state": "UNAVAILABLE", "available": False,
                    "reason": "CAPABILITY_NOT_REGISTERED", "dependencies": []}
        dependency_ready = {
            "checkpoint": self._checkpoint,
            "voice.transcription": self._voice,
            "automation.scheduler": self._automation,
        }
        missing = bool(
            spec.dependency and not dependency_ready.get(spec.dependency, False)
        )
        reason = (
            "FUTURE_DISABLED"
            if spec.future
            else "ADAPTER_NOT_CONNECTED"
            if missing
            else "LOCAL_ADAPTER_CONNECTED"
            if spec.dependency
            else "LOCAL_DATA_ONLY_IMPLEMENTATION"
        )
        runtime_available = not (spec.future or missing)
        profile_registered = spec.name in {"BUSINESS_FUTURE", "TRADER_FUTURE", "INVESTMENTS_FUTURE"}
        return {"name": name, "state": "UNAVAILABLE" if spec.future or missing else "AVAILABLE",
                "available": runtime_available, "reason": reason,
                "dependencies": [spec.dependency] if spec.dependency else [],
                "domain": spec.domain.value if spec.domain else "CURRENT_CONTEXT",
                "domain_recognized": spec.domain is not None,
                "specialist_profile_registered": profile_registered,
                "runtime_capability_available": runtime_available,
                "specialist_certified": False,
                "certification_state": "NOT_CERTIFIED" if profile_registered else "NOT_APPLICABLE",
                "legacy_capability_id": spec.legacy_id,
                "description": spec.description, "mode": "DATA_ONLY",
                "external_integration_active": False, "execution_authorized": False}

    def snapshot(self) -> list[dict]:
        return [self.get(s.name) for s in SPECS]
