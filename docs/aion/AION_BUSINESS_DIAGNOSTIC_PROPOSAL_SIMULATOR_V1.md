# AION BUSINESS Diagnostic + Proposal Simulator V1

Schema: `ATLASQUANT_AION_BUSINESS_DIAGNOSTIC_PROPOSAL_SIMULATOR_V1`

## Objetivo

Treinar o fluxo completo de uma futura venda consultiva do AION Business sem
contato real com empresas e sem nenhuma ação externa.

O simulador recebe dados fictícios, monta um diagnóstico preliminar, organiza o
Radar do Negócio, sugere um pacote e gera um rascunho profissional de proposta.

## Entrada

O exercício aceita:

- nome e segmento da empresa fictícia;
- canais utilizados;
- leads por semana;
- tempo médio de resposta;
- orçamentos/leads abandonados;
- percentual de clientes que retornam;
- frequência de conteúdo;
- existência de follow-up;
- existência de CRM;
- existência de SLA;
- medição de conversão;
- objetivos e observações.

Todo dado do simulador recebe truth state `DEMO_USER_INPUT`.

## Diagnóstico

O diagnóstico organiza alertas nos quatro pilares:

- Atrair;
- Atender;
- Converter;
- Reter.

Cada alerta mostra evidência de entrada, severidade e próximo passo sugerido.

## Radar

O Radar resume os quatro pilares em uma leitura simples, com score didático e
próximas ações para revisão.

O Radar do simulador nunca é apresentado como dado real de cliente.

## Pacote

A sugestão preliminar escolhe entre:

- Atendimento & Conversão;
- Marketing & Vendas;
- Gestão Inteligente;
- AION Business Completo.

O encaixe é somente didático. Empresa real exige diagnóstico, escopo,
integrações e volume confirmados antes da proposta final.

## Proposta

O rascunho inclui:

- objetivo;
- resumo do diagnóstico;
- pacote recomendado;
- entregas;
- fases de implantação;
- manutenção mensal;
- métricas a combinar;
- exclusões;
- próximo passo.

Preços ficam obrigatoriamente `A DEFINIR APÓS ESCOPO`.

## Segurança

O simulador não:

- envia proposta;
- contata cliente;
- assina contrato;
- solicita pagamento;
- publica;
- faz deploy;
- ativa runtime;
- promete aumento de vendas ou lucro.

O resultado é sempre `DRAFT_NOT_SENT`.
