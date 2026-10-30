# A273 — Fronteira de dados nativos na admissão de provas (LAB 30/10/2026)

**Base A272 #1723, somente PR draft isolada.** Sem merge, Worker, deploy, corretora, ordens, alertas, gasto ou autenticação externa.

## Falha encontrada
`preflight_untrusted_effect_candidate` aceitava qualquer `Mapping` e executava `set(candidate)` e `candidate.get()`. Um `Mapping` hostil pode executar código Python em `__iter__`, `__getitem__`, `__eq__` ou outros métodos, antes de a prova ser recusada. `decode_candidate_json` aceitava subclasses de `str` e chamava `encode()`. A leitura do snapshot local também aceitava subclasses de dicionário e `observed_at` aceitava subclasses de `datetime`.

## Escopo e contrato
- Candidados em memória exigem `type(...) is dict`, chaves `str` nativas e valores primitivos `str/int/float/bool/None`, antes de qualquer comparação de campos. JSON candidato exige `str` exata, sem métodos sobrescritos.
- Desafio local exige `dict` nativa no snapshot e decisão; valida os campos usados antes de comparar ou montar digest. Timestamp textual exige `str` nativa; relógio observado aceita `datetime` nativo.
- Nenhum fluxo positivo de autorização foi adicionado. `matches_local_binding` continua significando apenas comparação de campos locais; `may_confirm=False` sempre. Não há verificação de provedor nem identidade de testemunha.

## Testes
A214 #31–35: `Mapping` hostil não é iterado; `str` subclass não tem `encode/replace` chamado; campo com `__eq__/__ne__` hostil é recusado antes de comparação; `dict` subclass com `get` hostil não é consultado; `datetime` subclass com `utcoffset` hostil não é chamado. Estado UNCERTAIN/zero efeitos preservados. Executar regressões da A214 em Ubuntu/Windows antes de afirmar PASS.

## Limites
A barreira de tipos não é um sandbox contra host Python arbitrário, mutação do runtime nem origem externa forjada. `dict` nativa com valores primitivos também pode ter dados fabricados; atestado independente continua ausente. Seis P0 pendentes, **HARD NO-GO e UNCERTAIN=ZERO_AUTO_RESEND**. Negócios congelada apenas na visão Trader read-only, Investimentos preparado, Trader prioridade.
