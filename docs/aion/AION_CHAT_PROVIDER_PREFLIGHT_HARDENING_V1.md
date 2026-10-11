# AION Chat — Preflight do adaptador de modelos V1 (sem ativação)

**Escopo:** correção estreita do adaptador existente `atlasquant_aion_provider.py`, que já contém um cliente OpenAI Responses capaz de fazer uma chamada quando a aplicação **for explicitamente conectada**. O chat padrão NÃO o chama, e esta PR não instala/ativa tal conexão.

## Problemas e correções

1. **Texto truncado no limite de 40.000 caracteres:** o executor anteriormente chamava `str(prompt).strip()[:MAX_PROMPT_CHARS]`. Em uma integração futura isso poderia trocar silenciosamente o conteúdo aprovado pelo conteúdo transmitido ou suprimir um segredo no fim. Agora recusa prompt vazio, não textual e acima do limite **antes da rede**, sem ecoar o conteúdo na falha. Prompts com sinais de dados sensíveis ainda são recusados pelos filtros existentes. O gerador de prompt `build_provider_prompt()` também tem política de tamanho própria: quem o utilizar deverá provar *end-to-end* que a intenção original, sanitização, aprovação e bytes finais correspondem, pois esta mudança não elimina cortes feitos em etapas anteriores.
2. **Rota implícita:** `ProviderConfig.model_for_lane()` escolhe FAST para qualquer valor que não seja EXTERNAL_REASONING; a chamada direta podia, portanto, enviar `LOCAL_DETERMINISTIC` externamente se mal integrada. O executor agora aceita SOMENTE `EXTERNAL_FAST` ou `EXTERNAL_REASONING`, com tipos estritos, sem fallback silencioso.
3. **Custo positivo arredondado para zero:** preço pequeno + arredondamento `round(cost,6)` podia produzir `0.0`, tratado pelo `budget_decision` como solicitação gratuita e elegível mesmo com orçamento pago desabilitado. Agora estimativas positivas são arredondadas **para cima** ao microunidade USD, mantendo o controle de `allow_paid` e teto, sem afirmar cotação definitiva. Preço não finito retorna `PRICING_INVALID`, não um orçamento aprovadíssimo nem exceção operacional.

## Limites que NÃO foram resolvidos nesta PR

O parâmetro `request_approved=True` é ainda **somente um booleano recebido do chamador**, não uma assinatura verificada de HUMAN_OWNER nem aprovação vinculada a identidade, hash do prompt, modelo/custo, escopo, nonce e um registro durável de consumo. Nunca encaminhar valores do navegador para esse booleano nem usar a presença de API key como aprovação. O futuro host exigirá:
- autenticação server-side e vínculo de HUMAN_OWNER validado independentemente;
- persistência do turno do usuário confirmada ANTES de qualquer chamada com custo;
- orçamento mensal/teto de transação em unidade monetária validada, reconciliação do uso real e controle atômico de reserva para evitar concorrência/overspend;
- aprovação por turno que vincule os **bytes exatos do prompt sanitizado**, modelo, finalidade, custo máximo, escopo e solicitação única;
- gateway neutro com modelo cadastrado e origem do endpoint comprovada, fallback local sem mentir que há LLM offline;
- uma única tentativa após confirmação durável, estado `OUTCOME_UNKNOWN` e reconciliação sem auto-retry quando rede/DB der resultado incerto;
- gravação do output + metadados de proveniência como `MODEL_OUTPUT_UNVERIFIED`, sem permitir que texto do modelo execute ferramentas, faça merge/deploy ou autorize pagamento/trade;
- testes de injeção, redaction, auditoria RLS/scope, streaming parcial, desconexão e credenciais.

A implementação atual de persistência PostgreSQL em `main` é outra fronteira, OFF por padrão. A PR [#976](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/976) já documenta a ativação como revisão de design; #1074/#1075 planejam o modelo local/custo sem inferência real. O pacote do agente Windows e seu witness físico continuam separados (#1117, #1114, #1116).

## Testes

- 7 métodos novos contra: prompt acima do limite com segredo no final, vazio/tipos inesperados, máximo exato permitido sem transporte quando orçamento bloqueia, custo positivo muito pequeno, lanes local/desconhecidas/boolean e pricing infinito.
- Preserva a suíte anterior de provider/gateway/router e acrescenta workflow GitHub Windows/Linux.
- Testes de resposta usam `_FakeSession`, sem chamadas pagas; não ativam env nem deploy. A alteração do código do adaptador é proposta em Draft, sem executar nenhuma chamada de modelo real.

**Estado:** `real_model_connected=false`, `provider_activated=false`, `human_owner_external_approval_verified=false`, `billing_authorized=false`, `installer_authorized=false`, `safe_to_resume=false`.

Esta PR não altera o chat visual, Core congelado ou flags de produção, não instala chave, não faz merge/deploy e não acessa `am12`.