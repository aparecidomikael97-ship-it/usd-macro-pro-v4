# AION — Runtime Checkpoint Bootstrap + Foundation V14

Data: 2026-09-25

## Prioridade técnica

Este bloco fecha a prioridade número 1 da hierarquia aprovada:

1. persistência runtime real do Checkpoint Mestre;
2. soberania e resiliência;
3. confiabilidade da memória + Epistemic Core;
4. Data/Decision Fabric;
5. observabilidade/autodiagnóstico;
6. avaliação/melhoria controlada;
7. autonomia adicional somente depois dos gates.

## Checkpoint V14

V14 mantém todas as estruturas V13 e atualiza a fundação canônica com decisões
aprovadas posteriormente, incluindo:

- Memory Fabric e confiabilidade da memória;
- Epistemic Core/metacognição;
- Resolução Científica de Problemas e curiosidade controlada;
- soberania/resiliência, watchdogs, circuit breakers e secure recovery;
- Cofre Pessoal de Documentos;
- replay de decisão e RCA pós-trade;
- regra mestre de Stop Loss/Take Profit e liquidez contextual;
- radar de investimentos/ações/dividendos;
- módulo de Fundos Imobiliários e motor de carteira;
- Motor de Receita para vendas/afiliados/tráfego pago;
- Radar de Tendências;
- robustez transversal entre módulos.

## Bootstrap runtime

O arquivo alvo continua:

`dados/aion/checkpoint_master.json`

no branch dedicado:

`atlasquant-runtime`

O workflow `.github/workflows/aion-runtime-bootstrap.yml` roda após mudança
canônica na main e utiliza o próprio mecanismo oficial do AION:

1. lê o runtime;
2. executa preflight;
3. se o arquivo estiver ausente, cria o Checkpoint canônico;
4. faz leitura pós-escrita;
5. compara SHA/digest/integridade;
6. exige Checkpoint >= V14;
7. falha se não houver confirmação.

## Idempotência

Se o Checkpoint já existir e estiver CONFIRMED:

- o bootstrap NÃO sobrescreve;
- apenas verifica;
- memória mutável existente é preservada.

Se existir com mismatch/migração/incerteza:

- falha fechado;
- não grava automaticamente.

## Credencial

O bootstrap usa `${{ github.token }}`, token efêmero do GitHub Actions com
`contents: write` no próprio repositório.

Nenhum token é escrito no Checkpoint ou em arquivo do projeto.

## Verdade operacional

Somente após o workflow executar com sucesso e o arquivo ser lido de volta no
branch runtime podemos declarar persistência runtime CONFIRMED.

A presença da arquitetura na main, sozinha, não é considerada prova.

## Restrições preservadas

- nenhuma escrita de runtime em main;
- nenhuma sobrescrita silenciosa;
- nenhum serviço pago;
- nenhum deploy externo;
- nenhum trading real;
- nenhuma expansão de autoridade.
