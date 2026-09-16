# Plano de ativação do runtime

Status: proposta preparada, não executada. Nenhuma autorização de promoção foi concedida nesta retomada.

## Objetivo e problema confirmado

Separar dados mutáveis de código sem perder histórico, reintroduzir dados antigos ou zerar o budget Twelve Data. A main ainda grava dados na própria branch; a DEV já configura `atlasquant-runtime`. A branch runtime existe, mas os novos arquivos Flight Recorder, Shadow e Quota não estão presentes na árvore consultada.

## Preparação em DEV

1. Capturar SHAs de origem e destino e inventário por caminho, hash, tamanho, schema, timestamps internos e contagem de registros. Usar refs imutáveis; interromper uma futura aplicação se as refs mudarem.
2. Mapear todos os leitores/escritores da aplicação e dos dois workflows, incluindo snapshots, históricos, cache diário, cache OHLC e budget. Os sete arquivos citados no Word não são uma lista completa de migração.
3. Gerar um relatório somente leitura: igual, somente na origem, somente no destino, divergente ou inválido. Um arquivo só no destino deve ser preservado. Um conflito exige regra específica; nunca decidir somente pela data do commit.
4. Validar JSON/JSONL/CSV, campos obrigatórios, timestamps, IDs e duplicatas. Dados sem timestamp confiável não podem ganhar selo de frescor por migração.
5. Preparar casos de teste offline para origem inválida, destino com registros extras, conflitos de IDs, budget divergente e concorrência. Nenhuma chamada ao provedor é necessária para esses testes.

## Regras de reconciliação propostas

| Tipo de dado | Regra a validar antes de aplicar |
| --- | --- |
| Snapshot atual | Comparar timestamp estruturado e schema; preservar o válido mais recente; bloquear empate conflitante ou timestamp ausente |
| Histórico CSV/JSONL | União por identificador estável; deduplicar somente registros equivalentes; divergência no mesmo ID exige revisão |
| Cache OHLC | Preservar instrumentos, intervalos e candles fechados válidos; não tornar dado antigo atual |
| Budget Twelve | Preservar consumo/bloqueios da janela corrente; não somar nem escolher contadores arbitrariamente sem compreender sua semântica; bloquear migração se não houver reconciliação demonstrável |
| Novos stores ausentes | Não fabricar amostras ou métricas; criação pela captura real depois da ativação validada |

## Execução futura após autorização específica

1. Apresentar ao usuário o diff exato a promover, refs, resultado dos testes, relatório de reconciliação e plano de rollback. A promoção ampla da DEV contém muitas mudanças além da separação runtime; seu escopo precisa ficar explícito.
2. Na janela autorizada, suspender os escritores agendados e outras sessões escritoras identificadas; aguardar execuções em curso terminarem. Não cancelar gravações no meio nem manter escritores antigos e novos concorrendo.
3. Capturar cópias imutáveis dos dados e SHAs de todas as branches, sem exportar secrets. Recalcular inventário e conferir que as refs não mudaram.
4. Aplicar somente a reconciliação aprovada no destino com proteção de concorrência, preservando originais e arquivos exclusivos do destino. Não executar exclusões implícitas.
5. Promover o diff autorizado; conferir configuração efetiva tanto no runner quanto no aplicativo Streamlit. O redirecionamento de branches de código não garante que uma configuração explícita de outra branch esteja correta. Alterações de secrets exigem sua própria autorização.
6. Executar uma rodada controlada, respeitando quota e gates, verificar leituras e gravações e só então reativar agendamentos. Não ativar 28FX live nesta migração.

## Critérios de aceite

- Compilação e suíte do commit candidato aprovadas; inicialização, leitura do cache e health check sem regressão crítica.
- Gravações operacionais atingem runtime e não geram commits de dados em branches de código.
- Dados históricos e orçamento preservados; erros de leitura/escrita ficam visíveis e não provocam sobrescrita com estado vazio.
- Captura real e hidratação após nova sessão verificadas para Flight Recorder/Shadow; Quota Shadow confirma persistência no Autopilot. A mera existência de um arquivo não basta.
- Ausência de amostras, mercado fechado ou dados insuficientes permanecem explícitos. Uma rodada bem-sucedida não cumpre os limiares de revisão Shadow/Quota.
- UI consome estado persistente sem disparar refresh Twelve por simples abertura; pares fora do escopo técnico continuam sem autorização de execução.

## Rollback

Se falhar inicialização, integridade ou destino de escrita, interromper novos escritores dentro do plano aprovado. Preservar os registros gerados após o corte. Restaurar o código/configuração da referência aprovada sem reset destrutivo de dados e sem forçar refs. Antes de reativar código antigo, verificar onde ele lê/escreve: voltar o código sozinho pode voltar a gravar em main. Qualquer reconciliação reversa deve preservar os dois históricos e passar pela mesma análise de conflito.

## Evidência desta revisão

Baseline e links do workflow estão em `CONTEXTO_DO_PROJETO.md`. Código examinado: `atlasquant_runtime_store.py`, `atlasquant_release_guard.py`, `autopilot_v107.py`, `atlasquant_quota_shadow.py` e workflows de Autopilot/coleta/qualidade. Este plano não certifica que todos os caminhos de persistência foram auditados; o inventário completo é o próximo trabalho em DEV.
