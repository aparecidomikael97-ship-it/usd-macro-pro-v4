# AION — decisão técnica H0/F1/T1: custodiante externo de high-water (SEM CONTRATAÇÃO)

**19/10/2026 | PROPOSTA NÃO AUTORIZANTE | HARD NO-GO, 0/6 P0.**

## Decisão de arquitetura que realmente falta

Depois de demonstrar que um SQLite válido pode ser restaurado manualmente de um backup antigo, o núcleo **não pode** decidir sozinho que seu último `UNCERTAIN` é atual. Um SHA-256 local, uma cópia em outro diretório, o GitHub da mesma conta, uma assinatura gerada pelo próprio AION, um token de serviço mantido no PC ou um `verified=true` no payload **não** formam custódia independente.

Não existe neste repositório uma conta externa, chave de verificação realmente matriculada, backend CAS monotônico de outro domínio, dono comprovado, nonce realmente consumido remotamente, nem recibo terminal de fornecedor. Não transformar simulação local em autoridade.

**Requisito de primeiro efeito:** o escritor local declara intenção única, digest de payload, owner/tenant/workspace/host, nonce, epoch e sequência. Antes de qualquer chamada externa, um serviço **sob outra conta/identidade administrativa** deve atestar, de forma atômica e durável, um fence `ATTEMPT_RESERVED_OR_STARTED` específico da intenção, impedindo outra concessão concorrente/repetida. AION só aceita resposta autenticada vinculada à mesma operação, à versão/chave PINNED e a um head fresco obtido do custodiador. Timeout, perda da resposta, rollback, conta divergente, cópia antiga, indisponibilidade, chave revogada, nonce repetido => **BLOCKED / OUTCOME_UNKNOWN**. Mesmo uma reserva remota bem-sucedida **NÃO** confirma que Twilio, corretora ou outro fornecedor executou a ação: sem recibo confiável de efeito/no-effect, segue sem auto-reenvio.

## Duas opções concretas, ainda NÃO selecionadas

| Alternativa | Capacidade verificada em documentação pública | Ganho possível | Riscos ainda exigindo desenho |
|---|---|---|---|
| **Cloudflare Durable Objects com SQLite**, em conta separada da hospedagem/backup do AION | DO SQLite tem armazenamento transacional e fortemente consistente, classe disponível no Workers Free; a documentação de limites informa armazenamento Free de até 5 GB | Protótipo de monotonic CAS e serialização por chave em possível faixa gratuita, **sem ativar agora** | Serviço permite recuperação point-in-time e administradores podem modificar/deletar dados; portanto precisa administração isolada, trilha/auditoria externa imutável, política contra PITR/rollback, assinatura de recibos, autenticação e bloqueio de rotas privilegiadas. "Workers" da Cloudflare **não é** o Global Worker do AION. Free tem limites e custos podem mudar. |
| **Amazon DynamoDB**, em conta AWS separada | `UpdateItem` suporta `ConditionExpression`, e `GetItem(ConsistentRead=true)` recupera versão mais recente confirmada do item | CAS por intenção/epoch e readback fortemente consistente, modelo IAM granular e opção de ampliar escala | Operação condicional tem custo inclusive em falhas; IAM/delete/restore/cópia e outras credenciais administrativas precisam ser segregadas; assinatura independente, logs de auditoria, retenção e preço devem ser avaliados; **nenhuma conta/criação nesta rodada**. |

Documentação oficial consultada em outubro de 2026:
- https://developers.cloudflare.com/durable-objects/platform/limits/
- https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/
- https://developers.cloudflare.com/workers/platform/pricing/
- https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/WorkingWithItems.html
- https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_GetItem.html

**Regra de orçamento:** o teto operacional existente de R$ 200/mês permanece; qualquer criação de conta, cobrança, credencial, Worker da Cloudflare, operação AWS, CI externo adicional ou transferência de dados reais requer aprovação prévia com estimativa e limites configurados. Não afirmar que "Free" é custo sempre zero no futuro.

## Contrato mínimo verificável antes de escrever uma linha produtiva

1. **Dois domínios operacionais distintos**: custodiador com conta, MFA, backups e administradores separados do executor/backup, com log independente e mecanismo de recuperação que não rebaixe sequência.
2. **Identidade:** custodiante autenticado fora do payload e fora de GitHub da mesma credencial; issuer, key ID/version, owner/tenant/workspace/host e identidade de recurso assinados, com rotação e revogação; nenhuma inscrição autoafirmada.
3. **Registro monotônico:** chave por `tenant/workspace/action/intent_id`, head/digest/epoch, sequência CAS, prev_digest, status reservado/observado, nonce single-use durável e prazo. Nenhuma diminuição/eliminação; corrida entre dois hosts produz um vencedor e um negado.
4. **Falhas de fronteira:** pedido CAS chega mas resposta desaparece; processo local morre entre CAS remoto e chamada de fornecedor; queda após chamada e antes do recibo; retorno HTTP 5xx; rollback do SQLite; rollback/PITR do próprio custodiador; compromisso de credencial; clock skew; rede offline. **Todos estes casos devem negar efeitos enquanto incertos**, nunca fazer retry cego.
5. **Leitura com autenticidade e frescor:** endpoint fixado e TLS, assinatura verificada usando chave enrolada por canal separado; readback fortemente consistente com identidade e cabeçalho/versão; comparação com local no boot, antes da primeira tentativa, depois de reinício e em toda transição perigosa. Uma leitura eventual/stale nunca libera.
6. **Operação externa ainda separada:** recibo do produtor com assinatura/identidade, correlação exata de intenção, confirmação durável de efeito OU fence terminal de no-effect, e aprovação HUMAN_OWNER para ações críticas. O witness do AION não substitui a verdade do prestador.
7. **LGPD e minimização:** enviar somente digests/HMAC com chave custodiada, ids opacos e metadados mínimos; nenhum telefone, mensagem, documento, contrato ou dado de cliente em log de witness. Revisão da retenção.
8. **Fail-closed no caminho real**: protótipo deve ser integrado sob testes ao H0 inicial, Outbox antes do primeiro efeito e Worker antes de lease CAS. Não aceitar um booleano de ambiente `WITNESS_ENABLED` como bypass. Testar Windows/Linux e reinício físico; rodar Quality/Security históricos sem esconder RED.

## Defesa de regressão criada nesta rodada

`atlasquant_aion_p0_h0_boundary_drift_sentinel_lab.py` analisa a AST dos caminhos atuais e detecta remoção/reordenação simples de travas **já existentes** no Worker, Outbox e restauração, além de campos falsos do observador H0. `test_aion_p0_h0_boundary_drift_mutations_lab.py` altera o código **apenas em memória** para remover essas travas e verificar que o sentinel acusa regressão. CI em Ubuntu/Windows. O sentinel só confirma padrões de sintaxe; **não oferece prova formal de ausência de bypass e não autentica testemunha**. Sua própria saída inclui `external_witness_enrolled=false`, `first_effect_authorized=false` e `worker_armed=false`.

## Próxima aprovação que faz sentido pedir

Antes de provisionar um serviço e antes de continuar simulando sem realidade, submeter ao proprietário uma escolha de **custodiador externo e conta administrativa separada** com modelo de custo, IAM, autenticação e recuperação. Sugestão para análise, **não decisão implantada**: priorizar avaliar Cloudflare Durable Objects SQLite Free porque existe no plano gratuito documentado, **desde que** custódia distinta de verdade, PITR e revogação sejam resolvidos; DynamoDB com `ConditionExpression` e leitura forte é a alternativa para análise de governança. Nenhum desses provedores, por si só, garante proteção contra rollback de um administrador que controla os dois lados.

**Status final: proposta técnica e testes de regressão em LAB; nenhum serviço instalado, nenhuma testemunha enrolada, nenhum efeito ou custo, 0/6 P0 homologados e HARD NO-GO.**
