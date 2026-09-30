# ADR-0012 — Escopo primário e pacote de certificação do AION Business Expert

- Título: Escopo primário e pacote de certificação do AION Business Expert
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

A aba Negócios evoluiu de um catálogo centrado em marketplace para uma operação
de soluções de IA para empresas, com cinco motores de receita, pacotes fechados,
implantação, recorrência e experiência simples para o cliente.

O repositório ainda contém código histórico de marketplace. Removê-lo de uma vez
aumentaria risco de regressão, mas mantê-lo sem distinção poderia gerar dúvida
sobre o escopo oficial do BUSINESS.

## Problema

Era necessário separar escopo de produto atual, compatibilidade histórica,
readiness comercial e certificação técnica do especialista.

## Alternativas consideradas

Apagar imediatamente todo código de marketplace foi rejeitado por risco de
regressão. Manter marketplace como frente principal foi rejeitado por divergir
da decisão atual. Certificar o Business Expert apenas porque existe código foi
rejeitado pelo ADR-0010 e pelo Specialist Certification Gate.

## Decisão

O escopo principal do BUSINESS passa a ser os cinco motores:

1. Automação B2B e Agentes de IA.
2. Micro-SaaS / software próprio com AION.
3. Serviços de IA.
4. Revenue Operations e Captação.
5. Produtos Digitais próprios.

O pacote inicial gerenciado pode usar o nome provisório AION Presença &
Conversão. O modelo comercial preferido é pacote fechado com implantação e
recorrência, sem promessa de resultado.

Marketplace, dropshipping, afiliados, Shopee, Mercado Livre, TikTok Shop como
motor principal e e-commerce genérico ficam fora do escopo primário atual.
Código legado pode permanecer temporariamente por compatibilidade, sem contar
como readiness ou certificação do BUSINESS.

A certificação exige separadamente readiness de produto, prova técnica atestada
por CI e revisão humana exata. Certificação não ativa runtime.

## Consequências

A aba Negócios ganha uma fonte única de verdade para o escopo atual. Código
histórico deixa de definir a prioridade do produto. O treinamento, demo,
privacidade, margem, suporte e experiência do cliente entram no gate antes da
certificação.

## Componentes afetados

AION Business Expert, Specialist Certification, aba Negócios, documentação,
Quality Tests e futura interface Business.

## Segurança

Nenhum gate autoriza contato externo, contrato, cobrança, publicação, gasto,
merge, deploy ou trading real. Ações de alto impacto continuam sob aprovação
humana e gates próprios.

## Compatibilidade

O módulo `atlasquant_aion_business.py` pode continuar disponível como legado.
O novo contrato de certificação não depende de marketplace e não reativa esse
foco.

## Rollback/migração

O escopo pode ser substituído por novo ADR. A retirada futura do legado deve ser
feita com auditoria de referências e testes, não por deleção em massa.

## PR/commit relacionado

Implementação preparada em branch empilhada sobre a PR #395. Nenhum commit
desta branch é prova de produção.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
