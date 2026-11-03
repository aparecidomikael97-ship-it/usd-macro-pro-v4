"""AtlasQuant Trader — biblioteca editorial de impactos econômicos.

Explicação EDUCACIONAL e CONDICIONAL. Não fornece notícias, probabilidades,
previsões, ordens ou sinal. Classifica apenas o tipo de evento recebido de
fonte externa. Valor/consenso/unidade devem vir do provedor autenticado.
Prioridade de reconhecimento: indicador específico antes do indicador genérico.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Mapping


def _plain(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()[:220]


# key, regex aliases, explain mechanism, stronger-than-consensus,
# softer-than-consensus, evidence required, interpretive caveat.
# Country-sensitive variants are below (Brazil-specific and EU rates).
_GUIDES = (
    ("us_core_inflation", r"\b(core cpi|core pce|cpi core|pce core)\b",
     "Inflação subjacente: filtra componentes voláteis; sua persistência interessa aos bancos centrais.",
     "Uma surpresa acima pode aumentar expectativas de juros por mais tempo e favorecer USD via taxas.",
     "Uma surpresa abaixo pode reduzir expectativas de juros e pressionar USD via taxas.",
     "Núcleo versus índice cheio, serviços, salários, Treasury 2Y e comunicação do Fed.",
     "Núcleo e índice cheio podem divergir. Não conclua direção sem comparar composição e política monetária."),
    ("pce", r"\b(pce|personal consumption expenditures price|personal consumption expenditure price)\b",
     "Índice de preços PCE: medida de inflação acompanhada especialmente pelo Fed dos EUA.",
     "PCE mais quente pode sustentar juros esperados e, condicionalmente, apoiar USD.",
     "PCE mais frio pode reduzir juros esperados e, condicionalmente, pesar sobre USD.",
     "PCE cheio/núcleo, serviços, Treasury 2Y/10Y e reação do DXY.",
     "O PCE não é igual ao CPI; diferenças de composição e revisão podem mudar a interpretação."),
    ("cpi", r"\b(cpi|consumer price index|consumer prices|inflation rate)\b",
     "Inflação ao consumidor: compara a variação dos preços das famílias na base informada.",
     "Inflação acima do esperado pode elevar apostas de juros e favorecer a moeda local no curto prazo.",
     "Inflação abaixo do esperado pode reduzir apostas de juros e enfraquecer a moeda local.",
     "Índice cheio e núcleo, serviços, moradia, yields curtos e expectativas do banco central.",
     "Preços maiores não significam automaticamente moeda mais forte: crescimento e risco podem dominar."),
    ("producer_prices", r"\b(ppi|producer price index|producer prices)\b",
     "Preços ao produtor: mede pressões de custos; o repasse ao consumidor não é automático.",
     "PPI acima pode sinalizar pressão de custos; efeito cambial depende do repasse e da política monetária.",
     "PPI abaixo pode sinalizar alívio de custos; efeito cambial depende do CPI/PCE e da atividade.",
     "Composição de bens/serviços, margens, CPI/PCE posteriores e reação dos títulos.",
     "Não tratar PPI como inflação ao consumidor já realizada."),
    ("ipca", r"\b(ipca|ipca 15|igp m|inflacao oficial)\b",
     "Indicador de preços brasileiro: mede a inflação na metodologia do índice divulgado.",
     "Inflação acima do consenso pode elevar a precificação da Selic e apoiar BRL se o risco fiscal não dominar.",
     "Inflação abaixo do consenso pode reduzir juros esperados e pressionar BRL, dependendo do cenário.",
     "Composição do IPCA, Focus, curva DI, Copom e comportamento USD/BRL.",
     "Selic mais alta pode coexistir com desvalorização do real se houver deterioração fiscal."),
    ("hicp", r"\b(hicp|harmonised index of consumer prices)\b",
     "Inflação harmonizada europeia: referência de preços para o BCE.",
     "HICP acima pode sustentar juros europeus e favorecer EUR em certas condições.",
     "HICP abaixo pode reduzir juros esperados e pressionar EUR.",
     "BCE, inflação de serviços, salários europeus, EUR/USD e yields alemães.",
     "Choques de energia podem elevar inflação e enfraquecer crescimento simultaneamente."),
    ("unemployment", r"\b(unemployment rate|taxa de desemprego|jobless rate)\b",
     "Taxa de desemprego: indica folga no mercado de trabalho; maior não significa emprego mais forte.",
     "Desemprego acima do esperado pode apontar enfraquecimento do emprego e reduzir juros esperados.",
     "Desemprego abaixo do esperado pode sugerir mercado de trabalho firme e sustentar juros esperados.",
     "Taxa de participação, revisão, salários, Payroll e rendimentos curtos.",
     "Uma queda por menor participação não é a mesma coisa que melhora da contratação."),
    ("jobless_claims", r"\b(initial jobless claims|jobless claims|initial claims|continuing claims|unemployment claims|seguro desemprego)\b",
     "Pedidos de seguro-desemprego: maior número costuma sinalizar mais desligamentos ou dificuldade de recolocação.",
     "Pedidos acima podem indicar emprego mais fraco; potencial pressão sobre juros esperados e USD.",
     "Pedidos abaixo podem indicar emprego resiliente; potencial apoio ao USD via juros.",
     "Média móvel de quatro semanas, sazonalidade, revisões e Payroll.",
     "Pedidos semanais são voláteis e não equivalem à taxa de desemprego."),
    ("nfp", r"\b(nonfarm payrolls?|non farm payrolls?|nfp|payroll|employment situation)\b",
     "Payroll/NFP: variação do emprego não agrícola nos EUA; é parte de um relatório mais amplo.",
     "Contratações acima podem sustentar taxas americanas e apoiar USD, dependendo de salários e desemprego.",
     "Contratações abaixo podem pesar sobre taxas e USD, dependendo de revisões e participação.",
     "Revisões de meses anteriores, desemprego, participação, média salarial, Treasury 2Y e DXY.",
     "Número de vagas positivo não garante alta do dólar; o relatório pode ter sinais conflitantes."),
    ("adp", r"\b(adp|private payrolls?|private sector employment)\b",
     "ADP: estimativa de emprego privado nos EUA; não é o Payroll oficial.",
     "ADP acima sugere força na contratação privada, mas não autoriza antecipar o NFP.",
     "ADP abaixo sugere moderação privada, mas não confirma resultado fraco do NFP.",
     "Diferenças metodológicas ADP/NFP, salários e publicações oficiais posteriores.",
     "Não usar ADP como previsão precisa do Payroll."),
    ("jolts", r"\b(jolts|job openings|quits rate|job openings and labor turnover)\b",
     "JOLTS: vagas disponíveis e rotatividade indicam demanda por trabalho.",
     "Vagas acima podem indicar mercado de trabalho pressionado e juros mais persistentes.",
     "Vagas abaixo podem indicar arrefecimento da demanda e redução de pressões salariais.",
     "Taxa de demissões voluntárias, vagas por desempregado, revisões e Payroll.",
     "Vagas não são contratações efetivamente realizadas."),
    ("wages", r"\b(average hourly earnings|wage growth|earnings growth|salario medio|average earnings)\b",
     "Salários: crescimento da remuneração é relevante para serviços e inflação persistente.",
     "Salários acima podem reforçar preocupações inflacionárias e juros esperados.",
     "Salários abaixo podem reduzir pressão sobre inflação de serviços e juros.",
     "Variação mensal/anual, inflação real, emprego e produtividade.",
     "Salário nominal, salário real e custo unitário do trabalho são medidas distintas."),
    ("fomc", r"\b(fomc|federal funds rate|fed interest rate|fed rate|fed funds)\b",
     "FOMC/Fed: decisão e comunicação do banco central dos EUA.",
     "Juros acima do consenso podem apoiar USD pelo diferencial, salvo riscos macro ou de crescimento.",
     "Juros abaixo do consenso podem pressionar USD, salvo reação de aversão ao risco.",
     "Comunicado, projeções/dot plot, coletiva, juros 2Y/10Y e DXY.",
     "O comunicado e a projeção futura podem inverter a reação à taxa anunciada."),
    ("selic", r"\b(selic|copom)\b",
     "Copom/Selic: decisões de juros e sinalização do Banco Central do Brasil.",
     "Decisão mais restritiva pode apoiar BRL via diferencial de juros, se confiança fiscal permitir.",
     "Decisão mais flexível pode pesar sobre BRL via diferencial de juros, dependendo da atividade.",
     "Comunicado Copom, expectativas Focus, DI, inflação e risco fiscal.",
     "Queda de USD/BRL corresponde a BRL mais forte; juros altos não impedem saída de capital."),
    ("bank_rates", r"\b(interest rate decision|bank rate|policy rate|deposit facility|cash rate|overnight rate|refinancing rate|benchmark rate)\b",
     "Taxa de política monetária: altera custo de financiamento e retorno relativo da moeda.",
     "Taxa acima do consenso pode apoiar a moeda local se o comunicado não sinalizar cortes imediatos.",
     "Taxa abaixo do consenso pode pressionar a moeda local se reduzir o diferencial de juros.",
     "Banco central do país, projeções futuras, curva de juros e comunicação.",
     "Decisões já precificadas podem ter pouco efeito; a sinalização futura costuma importar mais."),
    ("pmi", r"\b(ism manufacturing|ism services|manufacturing pmi|services pmi|composite pmi|pmi|purchasing managers index)\b",
     "ISM/PMI: pesquisa de gestores; acima de 50 normalmente indica expansão e abaixo de 50 contração.",
     "Índice acima do consenso pode sugerir atividade mais forte e apoiar moeda/juros, conforme preços pagos.",
     "Índice abaixo do consenso pode sugerir desaceleração e pressionar moeda/juros.",
     "Nível em relação a 50, novos pedidos, emprego, preços pagos e revisão.",
     "Surpresa positiva pode ocorrer mesmo com PMI abaixo de 50: melhoria não significa expansão."),
    ("gdp", r"\b(gdp|gross domestic product|pib|ibc br)\b",
     "PIB/atividade: avalia crescimento real na base e período divulgados.",
     "PIB acima pode melhorar expectativa de crescimento e juros; efeito cambial depende da inflação.",
     "PIB abaixo pode reduzir expectativas de atividade e juros; risco pode dominar.",
     "Revisões, deflator, consumo, investimentos, comércio exterior e base trimestral/anual.",
     "PIB nominal, real, anualizado e trimestral não são intercambiáveis."),
    ("retail", r"\b(retail sales|vendas no varejo|retail turnover)\b",
     "Vendas no varejo: indicador de consumo; pode ser nominal ou real conforme fonte.",
     "Varejo acima pode indicar demanda forte e aumentar expectativas de juros.",
     "Varejo abaixo pode apontar demanda fraca e reduzir expectativas de juros.",
     "Varejo sem automóveis, preços, renda real e tendência das revisões.",
     "Alta nominal pode refletir inflação, não aumento de volume vendido."),
    ("industrial", r"\b(industrial production|producao industrial|factory output)\b",
     "Produção industrial: sinaliza volume produzido e capacidade, mas não resume toda a economia.",
     "Produção acima pode sugerir atividade mais firme e favorecer a moeda conforme juros.",
     "Produção abaixo pode sugerir fraqueza cíclica e reduzir expectativa de juros.",
     "Utilização de capacidade, estoques, PMI e exportações.",
     "Produção mensal é volátil e pode sofrer revisões."),
    ("durables", r"\b(durable goods|bens duraveis)\b",
     "Bens duráveis: pedidos de bens de maior prazo de uso, relevantes ao investimento.",
     "Pedidos acima podem sugerir investimento firme, dependendo de transporte/aviões.",
     "Pedidos abaixo podem sugerir investimento fraco, dependendo do núcleo da série.",
     "Pedidos sem aeronaves, bens de capital e revisões.",
     "Uma encomenda grande pode distorcer o índice cheio."),
    ("housing", r"\b(housing starts|building permits|new home sales|existing home sales|housing market)\b",
     "Moradia: indicador sensível a taxas hipotecárias, disponibilidade e renda.",
     "Habitação acima pode sugerir resiliência da demanda, mas inflação de moradia pode persistir.",
     "Habitação abaixo pode sinalizar fraqueza de demanda e efeito de juros altos.",
     "Juros hipotecários, estoques, licenças, revisões e sazonalidade.",
     "Dados de moradia são sensíveis a condições climáticas e revisões."),
    ("confidence", r"\b(consumer confidence|consumer sentiment|university of michigan|sentimento do consumidor|confianca do consumidor)\b",
     "Confiança: pesquisa sobre percepção e expectativas, não gasto efetivamente observado.",
     "Confiança acima pode sinalizar intenção de consumo maior, sujeita a confirmação nos dados reais.",
     "Confiança abaixo pode sinalizar cautela e intenção de consumo menor.",
     "Expectativas de inflação, renda, varejo e comparação com a série histórica.",
     "Sondagens de confiança nem sempre antecipam consumo ou preço de ativos."),
    ("trade_balance", r"\b(trade balance|balanca comercial|current account|conta corrente)\b",
     "Balança comercial/conta corrente: saldo depende da unidade, sinais positivos/negativos e fluxo de capitais.",
     "Um número maior não implica moeda mais forte sem saber se representa superávit ou déficit.",
     "Um número menor não implica moeda mais fraca sem compreender sinal e base estatística.",
     "Importações/exportações, revisão, termos de troca, câmbio e financiamento externo.",
     "Direção INDETERMINADA: saldo mais negativo pode representar déficit maior, não melhora."),
    ("oil_inventory", r"\b(eia crude oil inventories|crude oil inventories|oil inventories|estoques de petroleo)\b",
     "Estoques de petróleo: mudança de oferta/estoque, não indicador direto do dólar.",
     "Estoque acima pode pressionar preços do petróleo se indicar excesso de oferta, salvo demanda/produção.",
     "Estoque abaixo pode apoiar preços do petróleo se indicar aperto de oferta, salvo contexto.",
     "Refino, gasolina, destilados, produção, demanda, OPEP e curvas de futuros.",
     "Alta do petróleo pode afetar CAD, NOK, inflação e índices por canais diferentes; não é sinal do WIN."),
)


def indicator_guide(title: Any, country: Any = "", comparison: Any = "") -> dict[str, str]:
    """Editorial guidance for known indicators, otherwise explicit indeterminacy.

    Never assert an API event existed or had any numeric value. Returns no bias.
    """
    label = _plain(title)
    found = next(
        (guide for guide in _GUIDES if re.search(guide[1], label)), None
    )
    # Country-specific ambiguity: "CPI" from BR data could refer to an index
    # other than Brazilian IPCA. Keep guidance generic rather than relabel it.
    if found is None:
        return {
            "key": "unknown",
            "mechanism": "Indicador não identificado com segurança no catálogo editorial.",
            "above": "Não há efeito direcional comprovável apenas por um número acima do consenso.",
            "below": "Não há efeito direcional comprovável apenas por um número abaixo do consenso.",
            "watch": "Confirmar definição, base, país, unidade, comunicado e reação do mercado.",
            "caution": "Sem classificação inequívoca, qualquer viés seria especulativo.",
            "certainty": "CONDICIONAL · SEM VIÉS",
        }
    key, _, mechanism, above, below, watch, caution = found
    return {
        "key": key,
        "mechanism": mechanism,
        "above": above,
        "below": below,
        "watch": watch,
        "caution": caution,
        "certainty": "EDUCATIVO · CENÁRIOS CONDICIONAIS",
    }


__all__ = ["indicator_guide"]
