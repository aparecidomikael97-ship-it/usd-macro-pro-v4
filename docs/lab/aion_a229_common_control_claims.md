# A229 — Doze nomes diferentes podem depender da mesma autoridade

**Estado:** somente simulação em laboratório. **HARD NO-GO · P0 externo 0/6 · `UNCERTAIN=ZERO_AUTO_RESEND`.** Não foi consultada nenhuma autoridade, chave, pessoa, fornecedor, corretora, ambiente KMS/HSM ou custódia offline real.

## A pergunta do A229

Os 12 requisitos A227 parecem vir de 12 fontes distintas. Mas será que dois ou mais dependem da **mesma credencial de administração, autoridade superior, assinante, auditoria ou recuperação**? Se sim, uma única falha pode afetar muitas supostas “testemunhas”.

O A226 fazia essa pergunta para **duas fontes**. O A229 amplia para **12 fontes nominais**, procura colapsos dentro de uma única fonte e cruza papéis diferentes entre fontes. Ele **não autentica nenhum dos rótulos**, porque todos são declarações do host.

| Dependência alegada | O que o código detecta no texto | O que ele NÃO consegue afirmar |
|---|---|---|
| Controlador administrativo | Mesmo identificador declarado em duas fontes | Quem de fato controla as permissões |
| Autoridade superior (*ultimate parent*) | Mesmo identificador de autoridade ancestral | Que o ancestral existe ou é independente |
| Principal de assinatura | Mesmo identificador declarado de assinatura | Quem detém ou usa a chave real |
| Armazenamento de auditoria | Mesmo identificador do depósito de logs | Integridade real ou controle dos registros |
| Principal de recuperação | Mesmo identificador de recuperação | Que o host não conseguiria recuperar a chave |

Também detecta o uso do **mesmo rótulo em papéis diferentes** de duas fontes e o colapso de papéis **dentro de uma fonte** (por exemplo, um rótulo só para administrador e assinante).

## Resultados sintéticos importantes

- Uma sobreposição entre duas fontes: **1 par afetado**, não 12 independências.
- Três fontes com a mesma autoridade superior: **3 pares** afetados.
- As doze com a mesma autoridade superior: **66 pares possíveis** (`12 × 11 ÷ 2`), indicando que todos os 12 requisitos foram afetados por sobreposição declarada.
- Nomes e controladores todos diferentes: **0 sobreposições visíveis**, mas **0 fontes independentes verificadas**.
- A matriz experimental percorre **330 injeções de rótulos iguais** (`66 pares × 5 tipos de dependência`) em um dos **50 testes A229**.

O código devolve contagem de pares com alguma sobreposição, cinco contagens por categoria, pares com sobreposição entre papéis, fontes com colapso interno e os IDs de requisitos afetados. Um par com cinco dependências iguais conta **uma vez** no total de pares, mas **uma vez em cada categoria**.

## Vínculo e limites

O pré-voo A229 recebe uma matriz **A228 já bloqueada** com uma ou mais falhas sintéticas. Seu digest SHA-256 liga somente o conteúdo local de pesquisa; não transforma a matriz anterior em autenticação. Recusa:

1. IDs de requisitos fora do catálogo, repetidos ou faltantes;
2. IDs nominais de fonte duplicados, campos extras, rótulos inválidos e formatos ambíguos;
3. Divergência de escopo owner/tenant/workspace ou digest local A228 adulterado;
4. A228/A227 que tentem declarar aprovação ou condições externas verdadeiras;
5. Qualquer tentativa de reportar `VERIFIED`, `OBTAINED`, dono aprovou, modelo selecionado, P0 concluído ou `GO`;
6. Qualquer solicitação de reenvio automático em condição incerta.

As contagens são **sinais sobre declarações host-controlled**, não evidências de segurança real. Colisões explícitas alertam para dependência comum; ausência de colisões jamais equivale a independência. `actual_control_domains_independent`, `actual_issuer_identities_verified`, `external_evidence_accepted`, `owner_signoff_valid` e `provider_final_effect_verified` são sempre `False`, assim como todos os `may_*`.

## Entregáveis de laboratório

- `labs/a229_common_control_domain_claims.py`: comparação pura de 12 fontes nominais, 5 tipos de dependência e colapsos intra/interfonte.
- `labs/test_a229_common_control_domain_claims.py`: **50 testes novos**, incluindo as **330 injeções sintéticas** e ataques a formato, escopo e alegações de aprovação.
- `.github/workflows/aion-a229-common-control-claims-readonly.yml`: Ubuntu e Windows, **50 novos + 805 regressões A202–A228 = 855 testes por SO**, sujeitos a confirmação da CI.

Nenhuma decisão entre raiz offline e KMS/HSM foi tomada. O estudo é compatível com ambas e evita escolher fornecedor, definir permissões reais ou gerar material criptográfico.

Referências de princípio: [NIST SP 800-57 Part 1 Rev.5](https://csrc.nist.gov/pubs/sp/800/57/pt1/r5/final), [AWS KMS — separation of duties](https://docs.aws.amazon.com/prescriptive-guidance/latest/encryption-best-practices/kms.html), [Google Cloud KMS — separation of duties](https://docs.cloud.google.com/kms/docs/separation-of-duties).

**Conclusão A229:** cinco tipos de dependência nominal podem revelar controle comum, mas os nomes são insuficientes para certificar independência. **HARD NO-GO.**
