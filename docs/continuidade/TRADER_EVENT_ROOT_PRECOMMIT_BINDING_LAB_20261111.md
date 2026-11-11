# AtlasQuant Trader — raiz de evento econômico pré-registrada (LAB, 11/11/2026)

## Objetivo

A PR #1851 já reunia previsão, recibos locais e auditoria seletiva de acertos por evento. Ainda era possível preencher `event_root_id` apenas no relatório posterior, dividindo um único evento em vários nomes para inflar a quantidade aparente de observações independentes.

O novo `atlasquant_trader_event_root_precommit_guard_lab.py` registra previamente uma relação **slot → identificação da divulgação econômica → raiz do evento**. Para o mesmo `source_event_id` é obrigatório usar a mesma raiz. O registro é conferido contra todas as previsões, recibos e observações, sem omissões e antes de qualquer taxa descritiva.

**Exemplo:** sete pares ligados ao mesmo PPI americano não podem ser sete raízes independentes quando a divulgação tem o mesmo identificador de origem. Renomear uma raiz no relatório posterior faz a checagem falhar. Alterar o manifesto requer alterar também o checksum preservado, o que não constitui atestado externo.

## Garantias e limites

- Confere campanha, versão, horário de pré-registro, ID e ordem de cada oportunidade, mapeamento entre fonte e raiz, SHA-256 fornecido e recibos anteriores.
- Exige congelamento da classificação **antes da primeira previsão**, não após a divulgação.
- Não considera um checksum local, a data registrada pelo próprio programa ou nomes de eventos fornecidos pelo usuário como provas independentes. Alguém pode inventar nomes de notícias e recriar o manifesto inteiro. O teste adversarial documenta essa limitação.
- Não valida a existência da fonte econômica, horário oficial, calendarização do broker, independência estatística dos catalisadores, previsões reais ou resultado financeiro.
- `validated_accuracy=null`, `operational_bias=AGUARDAR`, `trade_authorized=false`, `publishable=false` sempre. Sem redes, ordens, notificações, trabalhadores, gastos ou deploy.
- O caminho de integração real com um atestado externo continua pendente; dados sintéticos de teste não contam como prova prospectiva.

## Validação

`test_atlasquant_trader_event_root_precommit_guard_lab.py` executa cenários de conformidade e de adulteração: divisão retroativa de PPI, dois IDs de raiz para a mesma divulgação, checksum alterado, ausência e reordenação de slots, congelamento tardio, alteração da campanha e ausência de recibos.

Adicionado ao workflow offline do Trader em Python 3.11 e 3.12. A aprovação em CI verifica lógica e regressões, **não** precisão de viés.

## Próximo marco

Para avançar além de consistência documental, é necessário buscar registro externo confiável e preservado **antes** do movimento, mais verificação ponto-no-tempo das notícias, preços fechados e rótulos de resultados. Nenhuma operação real deve ser liberada.
