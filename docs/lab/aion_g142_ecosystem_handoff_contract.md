# AION G142 — quatro espaços e isolamento de contexto (somente LAB)

Data: 2026-10-27 · Estado: DESIGN / HARD NO-GO · 0/6 P0 homologadas.

## Qual é a função do AION

O AION é o orquestrador/assistente central, não um robô de sinais e não um provedor de execução.
A interface do proprietário apresenta as quatro áreas **Trader**, **Negócios**, **Investimentos** e **AION**.
No código já existem contratos de capacidades, orquestração sem efeitos, oito responsabilidades
internas compartilhadas (não oito IAs), contratos para AION pessoal de assinantes e
contratos isolados de B2B. O G142 **não substitui, conecta nem habilita** essas peças.

| Área | Planos possíveis no futuro | Limite atual |
| --- | --- | --- |
| Trader | leitura macro, pares, ICT/SMC, força relativa, explicação e risco | dados verificados necessários; sem ordens reais |
| Investimentos | leitura de portfólio, diversificação, contexto de juros e inflação | dados próprios e consentimento; sem movimentação |
| Negócios | diagnóstico, CRM, rascunhos e visão gerencial | empresa isolada, sem exposição de cliente |
| AION | organizar tarefas, memória de escopo, voz/chat, ensino e revisões | sem confundir plano com execução externa |

## Handoff e escopos

- **OWNER_PRIVATE**: acesso administrativo futuro *somente após autenticação real*. A rota
  NEGOCIOS_OWNER_OVERVIEW_ONLY representa visão de supervisão, **nunca** leitura irrestrita
  dos registros da empresa-cliente.
- **SUBSCRIBER_PERSONAL**: potencial AION pessoal e leitura educativa de Trader/Investimentos
  no namespace do próprio assinante; **não** herda memória ADMIN nem Negócios.
  Não substitui a prova de entitlement, autenticação ou LGPD.
- **BUSINESS_TENANT**: potencial Negócios e assistente AION empresarial, somente no namespace
  da própria empresa. Não herda Trader/Investimentos particulares do proprietário.
- **Qualquer entrada G142 é NÃO CONFIÁVEL**. Nomes de área, IDs de tenant,
  approved=True, supostas provas, assinaturas de fixture e declarações de ADMIN
  não autenticam o ator nem concedem acesso. Mesmo uma rota elegível para planejamento
  retorna identity_authenticated=False, tenant_acl_verified=False e
  data_read_authorized=False.

## Critérios adversariais

1. Tráfego ou transcrição de uma empresa não escolhe a memória de outra.
2. Identidade/namespace trocado ou não autenticado resulta em planejamento bloqueado.
3. O proprietário não vira automaticamente o usuário de um tenant empresarial.
4. Solicitações de real trade, publicação, envio, cobrança, custo, deploy ou escrita automática
   não passam pelo contrato, mesmo se o chamador diz ter aprovação.
5. Resposta e snapshot do laboratório jamais declaram P0 homologada, autoridade externa ou execução.
6. Testes de laboratório verdes **não** satisfazem G122 nem prova externa do custodiante.
7. A separação precisa ser aplicada no *backend e no armazenamento reais*, com token validado
   externamente, ACL por linha/chave, isolamento de cache, anexos, embeddings,
   busca, logs, backup, exportações, revogação e tentativas adversariais reais.

## FinOps e operação

**Sem custos novos até 2026-11-05**, por decisão do proprietário. A partir de
**2026-11-06** apenas reconsiderar orçamento e eventual autorização explícita;
não há autorização antecipada para conta AWS, retenção S3, IAM, KMS ou execução.

É obrigatório manter Worker, provider SEND, trades reais, merge/deploy e cobranças
bloqueados. O G142 é uma inspeção pura de metadados de roteamento, sem rede,
sem arquivos de clientes, sem tokens de execução e sem efeito externo.

Revisão futura: ligar cada sessão autenticada a uma identidade confiável fornecida
pelo *sistema de autenticação*, jamais por texto do usuário; escrever testes de acesso
a dados reais apenas sob ambiente sintético e depois homologação P0 independente.
