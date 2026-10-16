# AtlasQuant Negócios — Contrato operacional V1.1 (somente LAB)

**Data:** 16/10/2026 · **Estado:** DESIGN + TESTES SINTÉTICOS, SEM HOMOLOGAÇÃO · **Nível:** módulo proposto, não implantação.

**Base didática:** Manual 1.0 (51 páginas, 15/10/2026) + Complemento Operacional V1.1 (13 páginas, 16/10/2026). O original não foi alterado. **Ponto de integração futuro:** recursos operacionais B2B supervisionados; NÃO duplicar o cockpit interno de pesquisa de produtos (`atlasquant_aion_business.py` / `_render_business`), NÃO fundir com o Portal Comercial (`atlasquant_sales_center.py`). Issue #280 documenta essa distinção. CRM real não foi verificado como implantado.

## 0. Invariantes e limites

1. Não usar dados reais de clientes, não conectar bancos, ERP, WhatsApp, e-mail, estoque real ou fornecedor de mensagens. ZERO_AUTO_RESEND, Worker OFF, sem external send/cobrança/reserva real.
2. Cada **tenant** tem espaço separado: nenhum recurso ou consulta pode cruzar `tenant_id`. Escopo e papéis administrativos devem ser validados **no backend autenticado** no futuro. O modelo sintético deste LAB **não** autentica, não é serviço de autorização e não substitui controles do Núcleo.
3. Dados não confirmados devem permanecer **NÃO VERIFICADOS**; registro com `source_ref` simulado prova somente que um campo foi preenchido, não prova fato externo.
4. Toda ação sensível ou irreversível só pode existir em versão futura homologada, com evidências H0/F1/T1/F2, autorização humana e governança adequadas. Este laboratório sempre bloqueia ações externas.
5. Status de orçamento, estoque, faturamento, venda, pagamento e conclusão **não são intercambiáveis**. Retorno do usuário à tela nunca atualiza status automaticamente.
6. LGPD: checklist é ferramenta educativa; não comprova base legal, segurança real, adequação ou autorização. Decisão jurídica/técnica e políticas reais continuam pendentes.
7. No curso: somente identidades inventadas; não persistir PII em logs, provas ou arquivos do laboratório.

## 1. Fluxo pretendido: cinco melhorias

```
CONSULTA
  ↓ demonstra interesse
LEAD_NAO_QUALIFICADO
  ↓ necessidade identificada + atendimento possível + interesse em avançar
LEAD_QUALIFICADO
  ↓ caminho de decisão, responsável, próximo passo / prazo
OPORTUNIDADE
  ↓ orçamento com preço ESTIMADO + revisão humana
ORCAMENTO EM ANALISE
  ├─ estoque: DISPONIVEL / RESERVADO / INDISPONIVEL / NAO_VERIFICADO / NAO_APLICAVEL
  ├─ recebimento: NAO_VERIFICADO / PENDENTE / PARCIAL / CONFIRMADO / CONTESTADO / NAO_APLICAVEL
  └─ situação comercial: ABERTO / PAUSADO / GANHO / PERDIDO / CONCLUIDO
```

Estas são **dimensões independentes**. O funil não vira uma máquina automática de envio e não conta conversão sem critério.

## 2. Contrato mínimo de dados — desenho para futura revisão

| Grupo | Campo | Forma sugerida / regra |
|---|---|---|
| Identidade | `tenant_id`, `case_id` | Obrigatórios, imutáveis; IDs internos sem dados pessoais; chave única escopada por tenant |
| Responsabilidade | `owner_id` | Obrigatório em caso ativo; servidor fará RBAC real, não confiar no campo recebido do navegador |
| Fluxo | `stage` | `CONSULTA`, `LEAD_NAO_QUALIFICADO`, `LEAD_QUALIFICADO`, `OPORTUNIDADE` |
| Comercial | `state` | `ABERTO`, `PAUSADO`, `GANHO`, `PERDIDO`, `CONCLUIDO`; `GANHO` ≠ pago |
| Qualificação | `need_identified`, `can_serve`, `interest_to_proceed`, `decision_path_documented` | Critérios separados; desconhecido **não** é verdadeiro; eventual regressão de etapa requer revisão humana |
| Próxima ação | `next_action`, `next_due_at`, `pause_reason` | Para caso ativo, próximo passo com prazo OU justificativa de pausa; nunca executar contato automaticamente |
| Atualização | `updated_at`, `updated_by` | ISO-8601 com fuso; autor e registro auditável em backend futuro |
| Preferência | `contact_preference` | Valor desconhecido/recusado não autoriza outbound; mesmo valor afirmativo não substitui base legal e revisão humana |
| Estoque | `requires_stock`, `requested_qty`, `stock.state` | Exigir `requested_qty` positiva quando há item e avaliar quantidade observada; insuficiência vira alerta |
| Verificação de estoque | `stock.checked_by`, `stock.checked_at`, `stock.source_ref`, `stock.observed_qty`, `stock.reservation_ref` | `DISPONIVEL`, `RESERVADO`, `INDISPONIVEL` exigem origem; `RESERVADO` também exige referência da reserva; neste LAB `source_ref` inicia `SIM-` |
| Pagamento | `payment.state`, `payment.amount_due_cents`, `payment.amount_received_cents` | Valores monetários em centavos inteiros, não float; `PARCIAL` só se recebido menor que devido; `CONFIRMADO` exige total conferido — ainda assim não prova banco no LAB |
| Verificação financeira | `payment.checked_by`, `payment.checked_at`, `payment.source_ref` | Origem, data e operador; evidência externa independente/conciliada é requisito para futuro produto, não demonstrado neste LAB |
| Privacidade | `purpose_ref`, `legal_basis_ref`, `retention_policy_ref` | Referências políticas específicas, não consentimento genérico nem certificação por checklist |
| Checklist | `privacy_checklist` | Seis verificações humanas com data, responsável e escalonamento no desenho futuro |
| Proposta | `scope`, `price_label`, `disclaimer`, `reviewed_by` | Texto padrão obrigatório, valores identificados como estimativa, revisão humana antes de qualquer envio (aqui nenhum envio) |

**Evidência e custódia futuras:** registrar referências mínimas e sem dados sensíveis; não armazenar comprovantes bancários ou contatos pessoais em anexos de teste; exigir fonte real apropriada, competência de verificador, versão e retenção legítima antes de qualquer alegação financeira. O uso de `source_ref: SIM-...` é etiqueta de cenário fictício, não validação externa.

## 3. Telas e UX — apenas wireframes textuais

### Tela A — Entrada de contatos e triagem
- Cabeçalho: `SIMULAÇÃO • SEM DADOS REAIS • SEM ENVIO`.
- Pergunta inicial é `CONSULTA`, não `OPORTUNIDADE` automaticamente.
- Campos mínimos: caso, origem (categoria), finalidade, necessidade, responsável, preferência de contato, próximo passo, prazo.
- Botão conceitual `Avaliar qualificação` mostra quais critérios faltam; **não** altera etapa sem registro e revisão.
- `Criar oportunidade` conceitual exige caminho de decisão, responsável, prazo e critérios de necessidade/viabilidade/interesse.

### Tela B — Ficha da oportunidade
- Bloco superior: responsável, etapa, último evento, prazo, pendências.
- Três cartões separados: **Comercial**, **Disponibilidade** e **Recebimento**; não utilizar uma única bolinha verde de “tudo resolvido”.
- Se solicitar 4 pneus e observar somente 2, mostrar `INSUFICIENTE (2/4)`. Um `DISPONÍVEL` digitado não remove alerta de quantidade.
- `CONFIRMADO` financeiro só deve ser resultado de conciliação real no produto futuro; LAB conserva `NÃO COMPROVADO EXTERNAMENTE` sempre.

### Tela C — Rotina diária e semanal
- Exibir filas `Sem responsável`, `Sem próximo passo`, `Vencido`, `Sem revisão no período` e `Dependência de confirmação`.
- Fim do dia é configurado **por empresa, fuso e calendário de funcionamento**; cálculo sintético aceita cutoff explícito, sem presumir 18h ou contato em feriados.
- Gestor analisa semanalmente exceções, motivo, próxima ação e métricas com denominador e período visíveis.
- Exceção nunca dispara mensagem nem altera uma ficha silenciosamente.

### Tela D — Proposta e comunicação responsável
- Rascunho deve exibir `NÃO HOMOLOGADO / NÃO ENVIADO` no LAB; não incluir botão funcional de envio.
- Disclaimer mínimo:

> Nosso compromisso é organizar processos, registros e acompanhamento de oportunidades, com entregas e indicadores definidos no escopo. Isso pode contribuir para um atendimento melhor, mas não garantimos aumento de vendas, faturamento ou lucro.

- Revisão humana da **proposta inteira**, pois ter o disclaimer não elimina promessa enganosa escrita em outros trechos. Validar escopo, fontes, preços, condições e responsabilidade antes de futura liberação.

### Tela E — Privacidade e incidentes
- Checklist de finalidade/base legal, minimização, acesso, direitos e preferências, correção/retenção e incidentes.
- `CHECKLIST PREENCHIDO` ≠ `LGPD HOMOLOGADA`. Nenhuma planilha demonstra conformidade jurídica automaticamente.
- Incidente/dúvida ⇒ suspender ação, preservar prova mínima em sistema autorizado, escalar ao responsável; nunca copiar dados de terceiros ao LAB.

## 4. Estados e regras de transição

| Situação | Resultado permitido | Resultado proibido |
|---|---|---|
| Pergunta simples sem contexto | `CONSULTA` | Contabilizar como oportunidade qualificada |
| Lead demonstra interesse sem necessidade confirmada | `LEAD_NAO_QUALIFICADO` | Avançar por inferência de valor/urgência |
| Qualificação sem qualquer critério | Manter etapa, apresentar pendências | Avanço automático |
| Caso ativo sem responsável ou próximo passo | Alertar gestor com prazo | Inventar quem fez contato |
| Registro sem revisão até corte diário | Marcar revisão pendente | Enviar follow-up por conta própria |
| Quantidade solicitada maior que observada | Alerta de insuficiência | Garantir disponibilidade ou reservar peça |
| Sem confirmação de pagamento | `NAO_VERIFICADO` / `PENDENTE` | Marcar como `CONFIRMADO` por `GANHO` |
| Valor recebido menor que devido | `PARCIAL`, registrar saldo | Declarar pagamento integral |
| Contato recusado ou contexto jurídico desconhecido | Bloquear canal automático | Disparar mensagem e alegar opt-in |
| Checklist LGPD todo marcado | `REVISÃO HUMANA NECESSÁRIA` | Certificar adequação automaticamente |
| Tenant alheio | `DENY` no contrato de alteração | Ler ou alterar ficha de terceiro |
| Proposta com disclaimer | Rascunho para revisão | Envio automático ou promessa de vendas |

## 5. Testes sintéticos e evidência

**45 cenários** de `test_contract.py`: estoque sem fonte, comprovante temporal inválido, insuficiência 2/4, reserva sem referência, estado `NÃO APLICÁVEL` conflitante, recebimento parcial/total incoerente, dono/etapa/prazo, corte diário, timestamps sem fuso, tenant diferente, avanço indevido, ausência de interesse, disclaimer, escopo, contato recusado, finalidade/base/retenção/checklist, e recusa de **todas** as ações externas. No LAB, mesmo preenchimento “perfeito” não vira prova de pagamento ou autorização de envio. Não há execução de testes de UI/CI/backend/Windows.

Rodar localmente, Python 3.10+ (stdlib):

```bash
python -m unittest discover -s labs/negocios_operational_v11 -p 'test_*.py' -v
```

O contrato é **oráculo de regras e demonstração do que seria desejado**, não integração com Streamlit, CRM, WebApp, API autenticada ou banco transacional. `advance_stage` valida somente o `tenant_id` fornecido; em um sistema real isso é insuficiente: o servidor deverá checar sessão, assinatura/identidade, RBAC, versão CAS, concorrência, auditoria, autorização de quem pode editar e isolamento multidimensional. `review_record` não envia, não salva, não busca, não altera e não sincroniza registros.

## 6. Critérios de aceite para eventual etapa posterior

- [ ] Revisão de produto confirma onde integrar sem duplicar `atlasquant_aion_business.py` ou `atlasquant_sales_center.py`.
- [ ] Modelo de dados e migrações com versionamento, tenant/RBAC reais, recuperação, auditoria e privacidade aprovados.
- [ ] Conteúdo e UX acessíveis no celular/PC com estados `NÃO VERIFICADO`, `INCONSISTENTE`, `SIMULADO` claramente diferenciados.
- [ ] Testes adversariais backend (concorrência, rollback, IDOR/cross-tenant, replay, papéis, origem dos dados) em ambiente independente, **sem** baixar guardas do AION.
- [ ] Contabilidade/ERP/estoque e conciliação bancária **fora da V1.1**; estudar API/contrato/licenças antes de cada integração.
- [ ] Avaliação de LGPD, fiscal, trabalhista e autorização HUMAN_OWNER específicas antes de dados reais, comercialização, envios, débitos ou produção.
- [ ] Nenhuma entrada `GO` por conta de um teste unitário verde. Respeitar HARD NO-GO dos P0 do Núcleo e matriz histórica aberta.

## 7. Rastreabilidade

- Manual original AtlasQuant Negócios V1.0 (51 pp) permanece intocado.
- Complemento Operacional V1.1 (13 pp), PDF de estudo, permanece separado.
- GitHub: #1225 (Negócios/planejamento); #1158 (AION B2B e UX); #280 (evitar cockpit duplicado); #1190 (Checkpoint Mestre); #1323 (84 diagnósticos do Núcleo).
- Nenhum custo, cliente, registro real, merge, deploy, Worker, serviço externo ou mudança de estado de produção neste LAB.
