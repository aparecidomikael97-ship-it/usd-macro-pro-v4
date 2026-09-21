"""Educational economic-indicator scenario guide for AtlasQuant.

The guide explains Previous / Consensus / Actual and common macro interpretation
of ABOVE / INLINE / BELOW surprises. It never turns a release into a guaranteed
price reaction or an automatic order.
"""
from __future__ import annotations

import re
from typing import Any

SCHEMA="ATLASQUANT_INDICATOR_SCENARIOS_V1"

FIELD_GUIDE={
    "Anterior":"Última leitura publicada disponível antes do novo release. Pode ter revisão posterior.",
    "Consenso":"Estimativa agregada do mercado/analistas antes da divulgação. É a referência principal para medir surpresa.",
    "Atual":"Número divulgado no novo release. Deve ser lido junto de revisões, componentes e contexto.",
}

_SPECS=(
    {
        "id":"cpi",
        "title":"CPI / IPC",
        "aliases":("cpi","consumer price index","ipc"),
        "above":"Inflação ao consumidor mais forte que o consenso. Tudo mais constante, pode reforçar leitura de juros mais altos por mais tempo e suporte ao USD.",
        "below":"Inflação mais fraca que o consenso. Tudo mais constante, pode reduzir pressão hawkish e retirar suporte do USD.",
        "inline":"Leitura próxima do consenso. O mercado tende a procurar Core CPI, composição, revisões e o que já estava precificado.",
        "caveat":"Headline e núcleo podem divergir; uma única leitura não define o Fed.",
    },
    {
        "id":"core-cpi",
        "title":"Core CPI",
        "aliases":("core cpi","cpi core","núcleo do cpi","nucleo do cpi"),
        "above":"Núcleo mais persistente que o esperado, normalmente interpretado como pressão inflacionária mais difícil de remover.",
        "below":"Núcleo mais fraco que o esperado, podendo aliviar expectativas de aperto monetário.",
        "inline":"Em linha: composição mensal/anual e tendência de vários meses ganham importância.",
        "caveat":"Reação depende da narrativa do Fed, serviços, habitação e precificação de juros.",
    },
    {
        "id":"pce",
        "title":"PCE / Core PCE",
        "aliases":("pce","core pce","personal consumption expenditures"),
        "above":"Inflação PCE acima do consenso pode reforçar cautela do Fed com cortes, tudo mais constante.",
        "below":"PCE abaixo do consenso pode aliviar pressão sobre juros, tudo mais constante.",
        "inline":"Em linha: mercado tende a olhar núcleo, revisões e tendência.",
        "caveat":"O efeito no preço depende do que já estava embutido na curva de juros.",
    },
    {
        "id":"nfp",
        "title":"Payroll / NFP",
        "aliases":("nonfarm","non-farm","non farm","payroll","nfp","employment change"),
        "above":"Criação de empregos acima do consenso sugere mercado de trabalho mais resistente e pode reduzir expectativa de afrouxamento, tudo mais constante.",
        "below":"Criação de empregos abaixo do consenso sugere trabalho mais fraco e pode aumentar expectativa de afrouxamento, tudo mais constante.",
        "inline":"Em linha: salários, desemprego e revisões dos meses anteriores podem dominar a leitura.",
        "caveat":"Payroll não deve ser lido sozinho; Average Hourly Earnings, unemployment e revisões podem inverter a narrativa.",
    },
    {
        "id":"unemployment",
        "title":"Taxa de desemprego",
        "aliases":("unemployment rate","taxa de desemprego","desemprego"),
        "above":"Desemprego acima do consenso costuma sinalizar trabalho mais fraco e pode favorecer leitura mais dovish.",
        "below":"Desemprego abaixo do consenso costuma sinalizar trabalho mais apertado e pode manter pressão sobre juros.",
        "inline":"Em linha: participação, salários e Payroll ganham peso.",
        "caveat":"Mudanças na participação da força de trabalho podem alterar a interpretação.",
    },
    {
        "id":"wages",
        "title":"Average Hourly Earnings / salários",
        "aliases":("average hourly earnings","hourly earnings","salários","salarios","wages"),
        "above":"Salários acima do consenso podem reforçar pressão de serviços/inflação e leitura mais hawkish.",
        "below":"Salários abaixo do consenso podem aliviar pressão inflacionária do trabalho.",
        "inline":"Em linha: combinação com Payroll e desemprego define melhor a leitura.",
        "caveat":"Mensal e anual podem contar histórias diferentes; composição do emprego também pesa.",
    },
    {
        "id":"jobless-claims",
        "title":"Pedidos de seguro-desemprego",
        "aliases":("jobless claims","initial claims","initial jobless","pedidos de seguro"),
        "above":"Pedidos acima do consenso sugerem mais demissões/fragilidade no trabalho e tendem a ser leitura mais fraca.",
        "below":"Pedidos abaixo do consenso sugerem mercado de trabalho mais firme.",
        "inline":"Em linha: tendência de várias semanas e continuing claims ajudam a contextualizar.",
        "caveat":"Série semanal é ruidosa; feriados e fatores sazonais podem distorcer uma leitura.",
    },
    {
        "id":"adp",
        "title":"ADP Employment",
        "aliases":("adp","adp employment"),
        "above":"Emprego privado ADP acima do consenso sinaliza atividade de contratação mais forte na própria pesquisa.",
        "below":"ADP abaixo do consenso sinaliza contratação privada mais fraca na própria pesquisa.",
        "inline":"Em linha: outros indicadores de trabalho ganham peso.",
        "caveat":"ADP não é uma previsão direta e infalível do Payroll/NFP; metodologia e cobertura diferem.",
    },
    {
        "id":"ppi",
        "title":"PPI / IPP",
        "aliases":("ppi","producer price","ipp"),
        "above":"Preços ao produtor acima do consenso podem sugerir maior pressão de custos/inflacionária.",
        "below":"PPI abaixo do consenso pode sinalizar menor pressão de custos.",
        "inline":"Em linha: componentes e transmissão ao consumidor passam a importar.",
        "caveat":"Nem toda pressão de produtor chega ao consumidor na mesma intensidade.",
    },
    {
        "id":"pmi-ism",
        "title":"PMI / ISM",
        "aliases":("pmi","ism manufacturing","ism services","ism non-manufacturing","purchasing managers"),
        "above":"Atividade acima do consenso sugere economia mais firme; componentes de preços e emprego podem mudar a leitura de juros.",
        "below":"Atividade abaixo do consenso sugere desaceleração relativa ao esperado.",
        "inline":"Em linha: preços pagos, emprego, novos pedidos e nível acima/abaixo de 50 ganham importância.",
        "caveat":"Serviços e manufatura podem divergir; o nível 50 e a surpresa são conceitos diferentes.",
    },
    {
        "id":"gdp",
        "title":"PIB / GDP",
        "aliases":("gdp","gross domestic product","pib"),
        "above":"Crescimento acima do consenso sugere atividade mais forte que o esperado.",
        "below":"Crescimento abaixo do consenso sugere atividade mais fraca que o esperado.",
        "inline":"Em linha: composição, deflator e revisões podem importar mais.",
        "caveat":"PIB possui estimativas e revisões; uma leitura passada pode mudar.",
    },
)


def _norm(value:Any)->str:
    text=str(value or "").casefold().strip()
    text=re.sub(r"[^a-z0-9áàãâéêíóôõúç/% -]+"," ",text)
    return re.sub(r"\s+"," ",text)


def indicator_spec(event_name:Any)->dict[str,Any]|None:
    raw=_norm(event_name)
    if not raw:
        return None
    # Longer aliases first to avoid generic matches winning unnecessarily.
    matches=[]
    for spec in _SPECS:
        for alias in spec["aliases"]:
            a=_norm(alias)
            if a and a in raw:
                matches.append((len(a),spec))
    if not matches:
        return None
    matches.sort(key=lambda x:x[0],reverse=True)
    return dict(matches[0][1])


def indicator_scenario_guide(event_name:Any)->dict[str,Any]:
    spec=indicator_spec(event_name)
    if spec is None:
        return {
            "schema":SCHEMA,
            "recognized":False,
            "event":str(event_name or ""),
            "fields":dict(FIELD_GUIDE),
            "scenarios":{},
            "automatic_execution":False,
            "interpretation":(
                "Indicador ainda sem regra educativa específica. O AtlasQuant não aplica "
                "uma regra genérica 'acima sobe / abaixo cai'."
            ),
        }
    return {
        "schema":SCHEMA,
        "recognized":True,
        "event":str(event_name or ""),
        "indicator_id":spec["id"],
        "title":spec["title"],
        "fields":dict(FIELD_GUIDE),
        "scenarios":{
            "ABOVE":{"label":"Acima do consenso","macro_context":spec["above"]},
            "INLINE":{"label":"Em linha com o consenso","macro_context":spec["inline"]},
            "BELOW":{"label":"Abaixo do consenso","macro_context":spec["below"]},
        },
        "caveat":spec["caveat"],
        "price_reaction_guaranteed":False,
        "automatic_execution":False,
        "interpretation":(
            "Os cenários descrevem uma tendência de interpretação macro, condicionada ao "
            "contexto. Não são ordem nem garantia da reação do preço."
        ),
    }


def indicator_catalog()->list[dict[str,Any]]:
    return [
        {"id":x["id"],"title":x["title"],"aliases":tuple(x["aliases"])}
        for x in _SPECS
    ]


__all__=[
    "SCHEMA","FIELD_GUIDE","indicator_catalog","indicator_spec",
    "indicator_scenario_guide",
]
