# AION — Fortaleza & Soberania

Data: 2026-09-25

## Escopo desta implementação

Esta etapa transforma parte dos requisitos NextGen em contratos técnicos
determinísticos fora do modelo.

Implementado:

- classificação de autoridade pela origem;
- site/documento/e-mail/tool output/outra IA como conteúdo sem autoridade;
- instruction boundary fail-closed;
- Autonomy Budget;
- Proof of Safety pré-execução;
- Cyber Immune defensive plan;
- emergency cutoff posture consultivo;
- regras explícitas no prompt do provedor;
- visualização no Laboratório/Admin.

## Regra de autoridade

A origem do texto é parte da política.

- SYSTEM_POLICY autenticada pode restringir.
- ADMIN autenticado pode fornecer intenção.
- Checkpoint/memória fornecem contexto/evidência.
- TOOL_OUTPUT, WEB, DOCUMENT, EMAIL, EXTERNAL_AI e UNKNOWN não podem comandar ferramentas.

Conteúdo externo pode ser lido e usado como evidência, mas não pode:

- ampliar permissão;
- desligar Guardian;
- autorizar publicação/pagamento/deploy;
- revelar segredo;
- liberar trading;
- tornar a si próprio uma autoridade.

## Autonomy Budget

Autonomia é reduzida por:

- risco Guardian;
- impacto;
- incerteza;
- efeitos externos;
- irreversibilidade.

O orçamento de autonomia **não concede permissão**. Ele só restringe a lane
operacional.

## Proof of Safety

A prova é um preflight auditável, não uma prova criptográfica e não um token de
execução.

Para ação sensível, verifica no mínimo:

- origem autorizada;
- Guardian;
- escopo;
- testes;
- rollback;
- incerteza;
- aprovação;
- efeitos externos.

Estados:

- PASS;
- REVIEW;
- BLOCK.

PASS significa apenas que um executor downstream pode continuar avaliando a
ação. Nenhuma ferramenta é chamada automaticamente.

## Cyber Immune

A camada defensiva:

- preserva evidência;
- recomenda isolamento/quarentena quando aplicável;
- nunca desativa antivírus/EDR;
- não apaga automaticamente;
- não faz contenção automática;
- exige revisão humana para ação destrutiva.

## Emergency Cutoff

A camada calcula postura para controlador independente.

O módulo não corta ferramentas por si só. O objetivo é permitir que um
controlador externo ao modelo aplique o kill switch em etapas futuras.

## Restrições permanentes

- trading real bloqueado;
- nenhum deploy automático;
- nenhuma publicação automática;
- nenhum pagamento automático;
- nenhuma expansão de privilégios pelo modelo;
- nenhuma instrução externa vira autoridade por conteúdo textual.
