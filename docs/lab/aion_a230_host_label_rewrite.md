# A230 — Renomear todos os controladores não cria independência

**Estado:** pesquisa sintética e somente leitura. **HARD NO-GO · P0 externo 0/6 · `UNCERTAIN=ZERO_AUTO_RESEND`.** Sem contatos, fornecedores escolhidos, chaves reais, credenciais, corretoras, IAM externo, KMS/HSM, assinaturas, merge ou deploy.

## Falha investigada

No A229 encontramos coincidências explícitas entre os cinco rótulos de controle de 12 fontes: controlador, autoridade superior, assinante, auditoria e recuperação. Mas um host comprometido pode trocar nomes e fazer desaparecer todas as coincidências. Um relatório com **zero sobreposições visíveis** não é evidência de que os controladores sejam independentes.

O A230 compara dois conjuntos **sintéticos e não autenticados**, o retrato A229 declarado como *antes* e a lista de rótulos declarada como *depois*. Valida as estruturas e seus vínculos locais; só admite a alteração dos cinco campos de nomes do controle. Não deixa o host trocar escopo, fonte nominal, identidade do emissor ou estado de procedência.

| Caso sintético | Sinal calculado | Interpretação obrigatória |
|---|---|---|
| 2 fontes com controlador igual, depois nomes diferentes | 1 par visível desaparece | A mudança nominal não comprova independência |
| 12 fontes com mesma autoridade superior, depois 12 nomes distintos | 66 pares desaparecem | Nenhuma identidade real foi auditada |
| 3 fontes com controlador igual, depois 1 recebe outro nome | 2 pares desaparecem; 1 continua visível | A ausência parcial de colisões não concede confiança |
| 12 fontes com todos os nomes diferentes desde o início | 0 pares visíveis | Ainda 0 fontes independentemente verificadas |
| Troca de nomes dentro da própria fonte | Colapso interno pode ficar oculto | Nenhuma evidência externa foi obtida |

**Limitação crítica:** se o próprio host fabrica tanto o *antes* quanto o *depois*, até a comparação pode ser manipulada. O código não detecta fatos reais escondidos sem um retrato independente; só calcula diferenças nos dados que recebeu. O hash SHA-256 utilizado é um vínculo de texto local, **não uma assinatura ou prova de procedência**.

## Regra de bloqueio

O preflight recusa envelopes ambíguos, escopos incorretos, fontes duplicadas, troca de identidade/procedência, falsa assinatura do proprietário, P0 inflado, alteração de modelo, `GO`, e reenvio de operação incerta. O decodificador JSON estrito pode recusar o envelope serializado completo acima de 8.192 bytes; o laboratório usa dicionários Python estruturados e mantém esse limite sem ampliá-lo.

Todos os resultados, inclusive os de formato coerente, preservam:
- `actual_control_domains_independent=False` e `actual_issuer_identities_verified=False`;
- `external_evidence_accepted=False`, `owner_signoff_valid=False` e `provider_final_effect_verified=False`;
- **todos** os `may_*=False`, inclusive `may_confirm` e `may_auto_resend`.

## Entregáveis

- `labs/a230_host_label_rewrite.py`: verificação somente leitura de vínculos locais, pareamento de sobreposições nominais e mudanças de rótulos.
- `labs/test_a230_host_label_rewrite.py`: 50 testes novos de bloqueio e manipulação nominal, incluindo 66 pares ocultados.
- `.github/workflows/aion-a230-host-label-rewrite-readonly.yml`: Python 3.12, Ubuntu/Windows, ações fixadas por SHA, **905 testes esperados por SO (50 novos + 855 regressões)**; a contagem será confirmada nos logs, não presumida.

Raiz offline e KMS/HSM continuam em comparação, sem escolha. A próxima prova real precisará vir de um processo fora do host, com identidade verificável, poderes separados e auditor independente.

**Conclusão:** alterar os nomes não altera a autoridade real; mesmo zero coincidências visíveis implica **zero independências comprovadas**.
