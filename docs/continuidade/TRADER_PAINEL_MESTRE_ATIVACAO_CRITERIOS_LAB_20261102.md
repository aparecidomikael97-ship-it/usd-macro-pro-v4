# AtlasQuant Trader — portão de ativação do Painel Mestre (LAB)

**Data:** 02/11/2026 · **Status:** somente especificação e testes; **HARD NO-GO** para execução real.  
**Referência:** PR #1803, interface visual aprovada preservada.  
**Custos e operação:** nenhuma fonte nova contratada, nenhum segredo consultado,
nenhum banco/Worker/cron criado, nenhum deploy/merge.

## Problema que esta etapa fecha no desenho

Consultar uma fonte às 06h35 não prova que CPI, PCE, NFP, IPCA ou Selic
divulgaram uma observação nova nesse instante. Três fatos precisam ser
independentes:

1. **Consulta:** data e hora da tentativa (`checked_at_utc`), identidade do
   provedor, resultado HTTP/sanitizado, identificador idempotente.
2. **Observação:** indicador, período econômico e unidade, valor conhecido,
   origem e eventual versão. Primeiro registro no AtlasQuant não significa
   publicação nova. Valor alterado não é revisão oficial até haver evidência.
3. **Divulgação:** horário da publicação verificado na fonte responsável;
   sem esse dado, o sistema deve exibir **NÃO CONFIRMADO** e não calcular
   surpresa de divulgação como se ela acabasse de acontecer.

Uma falha da API altera o estado da **consulta**, nunca gera valor fictício
nem transforma o último valor histórico em resultado novo.

## Achados nas documentações dos provedores

- **EODHD:** requisições HTTP e *API calls* cobradas na franquia são conceitos
  distintos; o limite diário principal reinicia à meia-noite GMT, e produtos
  Marketplace podem ter cota separada. O custo efetivo do endpoint na **conta
  existente**, disponibilidade contratual e direito de uso não foram verificados.
  Fonte: https://eodhd.com/financial-apis/api-limits
- **Economic Events EODHD:** o campo `date` é documentado como
  `YYYY-MM-DD HH:MM:SS`, sem offset explícito no formato apresentado.
  Antes da ativação, confrontar eventos reais com o calendário oficial da
  instituição e confirmar UTC/fuso, atraso, revisão e horários. Não inferir
  horário exato de divulgação apenas da string.
  Fonte: https://eodhd.com/financial-apis/economic-events-data-api
- **FRED:** a API de observações tem data da observação e metadados de versão
  temporal; isso não equivale por si só ao carimbo do release econômico.
  Fonte: https://fred.stlouisfed.org/docs/api/fred/series_observations.html
- **BCB/SGS:** frequência e período por série continuam separados da data da
  consulta. Validar metadados e formato da resposta na homologação, sem
  inferir um novo dado mensal a partir de uma consulta diária.

## Contrato de cota compartilhada para futura implementação

O protótipo SQLite já cobre reinícios de processos que apontam para **o
mesmo arquivo**. Ele não é um limitador global entre hosts. Para operação
de várias réplicas, usar transações num armazenamento central aprovado
(por exemplo, PostgreSQL já autorizado, se existente), não um banco
paralelo de memória AION.

A transação de reserva deverá:

1. Receber somente **provedor, data contábil do provedor, chave idempotente,
   custo estimado em unidades faturáveis verificadas, teto diário confirmado**.
   Não aceitar custo desconhecido; nunca persistir token.
2. Dentro de transação, serializar o acesso à linha do orçamento por
   provedor/data (bloqueio de linha ou operação atômica equivalente).
3. Checar se a chave já foi usada e recusar nova cobrança/reexecução.
4. Verificar `unidades_usadas + custo_reservado <= teto`, incluindo reservas
   de outras instâncias, tentativas falhas e reserva mínima sob demanda.
5. Gravar a reserva durável **antes** da chamada; confirmar sucesso/falha
   por identificador. Crash durante a consulta preserva reserva, não reabre
   o orçamento por acidente.
6. Reconciliar o consumo do provedor por meio de leitura autorizada da
   conta e tratar divergência como bloqueio; não assumir que 1 HTTP = 1 unidade.
7. Disponibilizar logs sanitizados, RBAC, retenção, backup, parada imediata e
   evidências de teste com duas réplicas e reinícios. Sem comprovação,
   permanecer em **HARD NO-GO**.

A agenda proposta continua **somente uma prévia**:
06h35/10h45/17h15 BRT (calendário) e 06h40 BRT (séries oficiais).
É necessário provar que a cota e o armazenamento suportam essas janelas
**mais** consultas sob demanda antes de executar qualquer uma.

## Portão de ativação fail-closed

O módulo `atlasquant_trader_master_activation_gate.py` avalia
documentos de evidência com data UTC, revisor e referência interna.
Os 14 itens obrigatórios cobrem:

- Entitlement, fuso, unidades faturáveis da EODHD;
- Acesso/limites FRED e semântica das séries BCB;
- Atomicidade, múltiplas réplicas e recuperação da cota central;
- Armazenamento RBAC/retenção;
- Falhas de fonte sem dados inventados;
- Identidade/auditoria do agendador, kill switch;
- Margem no orçamento e revisão expressa do proprietário.

Provas ausentes, vencidas, futuras ou inválidas bloqueiam a etapa. Mesmo
se **todas** forem relatadas como PASS, o resultado é apenas
`PENDING_INDEPENDENT_REVIEW`: a ferramenta **não valida autenticidade**,
não ativa nada e nunca concede autorização de operação. Testes independentes
com os sistemas reais e aceite humano são necessários em outra fase.

## Implementação e prova desta PR

- Novo módulo puro `atlasquant_trader_master_activation_gate.py`.
- Novos testes `test_atlasquant_trader_master_activation_gate.py`,
  incluídos no Quality CI: ausência de provas, prova falsa/expirada,
  fronteira de 7/30 dias, fuso, ausência de unidades cobradas, cota
  múltiplas réplicas, sigilo de referências e proibição permanente de ativação.
- Nenhuma importação pela interface publicada ou por runners/cron.
- CI e revisão visual exigidos após commit; não declarar aprovação
  sem conclusão do fluxo.

**Próximos bloqueios reais:** acesso/entitlement da conta, fuso comprovado,
valor faturável do endpoint, armazenamento central aprovado e teste de
duas réplicas. Nenhuma dessas verificações pode ser fingida por fixtures.


## Prova adicional — orçamento por unidades consumidas (LAB)

Arquivo de simulação: `atlasquant_trader_master_quota_units_lab.py`.
Evolui o experimento anterior por número de requisições, **sem substituí-lo
em produção**. Um único arquivo SQLite explicitamente inicializado é
usado apenas para simular instâncias concorrentes no mesmo host e testar
a durabilidade após reinícios.

- O orçamento diário do provedor usa **unidades** com custo explícito por
  tentativa, não número de HTTP requests. Custo não conhecido ou não inteiro
  falha fechado; não foi inferido o custo real do plano EODHD.
- Toda tentativa reserva o custo **antes** da chamada. Falha, timeout ou
  crash não liberam créditos artificialmente.
- A chave idempotente impede reserva dupla; várias conexões ao mesmo arquivo
  disputam a mesma transação. Uma política diária já registrada não pode
  ser aumentada silenciosamente.
- O horário de reset nesta simulação é meia-noite UTC, conforme a
  documentação pública da cota diária principal EODHD. Outros produtos,
  planos e cobranças podem obedecer a regras distintas.
- A reserva de demanda protege uma parcela do teto para consultas
  espontâneas, evitando que três janelas planejadas a consumam integralmente.
- O snapshot deixa explícito:
  `provider_meter_verified=False`,
  `global_multi_host_quota_proven=False`, `scheduler_enabled=False`.

`test_atlasquant_trader_master_quota_units_lab.py` cobre 15 cenários,
incluindo peso maior que 1, concorrência simulada por clientes independentes,
falha, crash, reinício, duplicidade, política imutável, virada UTC, reserva
sob demanda e ausência de ações externas. Resultado de CI precisa ser
conferido depois do commit.

**Próximo gate ainda ABERTO:** implementar a mesma transação em um banco
central realmente compartilhado por hosts e comparar os créditos da
conta real mediante autorização específica do proprietário. Esta simulação
não realiza nem comprova esses dois passos; não ativa cron/Worker/deploy.
