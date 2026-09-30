# ADR-0017 — Treinamento do administrador precede atendimento real no AION Business

- Título: Treinamento do administrador precede atendimento real no AION Business
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

A Demo AION Business já apresenta o novo escopo de forma simples, mas o
administrador precisa dominar o discurso comercial, a demonstração e os limites
do produto antes de divulgar ou atender empresas reais.

## Problema

Uma interface bonita não garante que o administrador saiba explicar o problema,
o pacote, a entrega, a manutenção, as métricas e os limites com segurança.

## Decisão

Adicionar uma trilha guiada de treinamento com cenários fictícios de clínica,
imobiliária e prestador de serviços.

A trilha cobre diagnóstico, Radar, escolha didática de pacote, entrega,
manutenção, objeções, venda simulada e checklist de preparação.

O módulo é offline e não possui caminho de contato, cobrança, publicação,
persistência externa ou runtime.

## Consequências

O administrador pode praticar repetidamente antes de conversar com empresas
reais, reduzindo improviso e risco de promessas incorretas.

## Segurança

O treinamento nunca autoriza automaticamente atendimento, venda, runtime,
contato, contrato, pagamento, publicação, gasto, deploy ou trading real.

## Compatibilidade

ADR-0016 define a Demo visual. Este ADR adiciona a camada de aprendizagem sobre
essa Demo e mantém todos os gates operacionais anteriores.

## Rollback

A retirada da trilha remove somente conteúdo de treinamento; não existe efeito
externo a compensar.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
