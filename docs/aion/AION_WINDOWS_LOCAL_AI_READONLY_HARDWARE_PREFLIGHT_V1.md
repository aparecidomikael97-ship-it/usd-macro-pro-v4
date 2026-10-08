# AION Local-First — Verificação segura de capacidade do computador V1

**Data:** 08/10/2026  
**Base:** #1072 (inventário de despesas e pré-chamada paga em CI)  
**Estado:** Draft, diagnóstico read-only, sem instalação ou execução no computador do proprietário.

## Por que

O orçamento operacional inicial do AtlasQuant/AION permanece em **R$ 200
mensais** como meta de despesas recorrentes custeadas pelo proprietário,
excluindo equipamentos, internet e eletricidade. O AION deve preferir
modelos locais *quando forem seguros, capazes e rápidos o suficiente*.
Sem medir hardware, seria incorreto afirmar que o AION consegue executar
um modelo local avançado ou dispensar todas as APIs pagas.

## Implementação

O script `scripts/aion_local_ai_windows_readonly_hardware_probe_v1.ps1`
lê **somente** métricas agregadas, por CIM/WMI do Windows, e exibe
um relatório JSON no terminal, sem gravar arquivo e sem enviar dados.

Campos:
- RAM física total em GiB;
- número de processadores lógicos;
- espaço livre na unidade do sistema, em GiB;
- classes genéricas de fornecedor de vídeo
  (`INTEL`, `AMD`, `NVIDIA`, `OTHER_OR_UNKNOWN`);
- campos de confiança explicitamente falsos, incluindo
  memória dedicada de GPU ainda não verificada.

**Não coleta/exporta** número de série, nome do PC, Windows username,
listas de aplicativos/processos, contatos, IP, tokens, diretórios
pessoais, arquivos, chaves, nome de usuário, informações financeiras
nem imagens de tela. Também não instala drivers, modelos ou serviços,
nem faz chamadas de rede.

O modo de automação `-CIProbe` é executável **somente** quando as
variáveis do runner GitHub indicam Windows + pull_request. Isso valida o
comando no **computador temporário do GitHub**, não no PC do usuário.
Variáveis de ambiente não são uma autenticação de hardware.

Para uso futuro no **computador do proprietário**, o próprio usuário
deve abrir o script e executar explicitamente `-OwnerReadOnlyConsent`
no seu ambiente Windows. **Não faremos isso remotamente ou
automaticamente**. A saída deve ser revisada antes de compartilhada.

## Revisão de capacidade em Python

O módulo `atlasquant_aion_local_ai_hardware_readonly_capacity_v1.py`
rejeita campos estranhos e valores não finitos/fora de faixa, exige os
flags de confiança falsos e fornece APENAS uma faixa conservadora de
**candidato a teste de modelos locais**.

Mesmo um PC com RAM abundante e um rótulo NVIDIA/AMD não comprova
memória de GPU disponível, suporte CUDA/ROCm, velocidade de tokens por
segundo, qualidade, compatibilidade de modelos ou custo de energia.
WMI pode listar iGPUs/dispositivos virtuais e não fornece verificação
suficiente da VRAM dedicada; por isso **não declaramos modelo pronto**.

As recomendações dependem de um futuro benchmark local de RAM/VRAM,
contexto/quantização, latência de inferência, tempo de carregamento,
qualidade por tarefa e consumo elétrico. Zero mensalidade em API não
significa operação sem custo de energia, manutenção, backups ou conexão.

## Resultados máximos possíveis

- `HARDWARE_CONSTRAINED_BENCHMARK_REQUIRED`
- `LIGHT_LOCAL_MODEL_EXPERIMENT_CANDIDATE`
- `CPU_OR_UNKNOWN_GPU_LOCAL_BENCHMARK_CANDIDATE`
- `GPU_LOCAL_MODEL_BENCHMARK_CANDIDATE`

Todos os resultados são provisórios. A maioria das decisões de modelo
(3B, 7B, 14B, MoE etc.) exige testes e quantização específicos;
esta V1 deliberadamente não promete nenhuma dessas capacidades.

## Protocolo para executar no PC futuramente

1. Verificar e revisar a PR e o script, depois realizar aprovação
   específica para uma leitura local sem privilégio administrativo.
2. No Windows, executar manualmente o script assinado/conferido ou
   sob política de execução existente, com `-OwnerReadOnlyConsent`.
   Não modificar ExecutionPolicy para contornar segurança.
3. Examinar a saída localmente: dados exclusivamente agregados;
   nenhuma transmissão automática.
4. Informar os números (não nome do PC, serial, conta ou IP) para
   planejar o melhor modelo, custo de energia e necessidade de fallback.
5. Apenas depois decidir se será necessária GPU nova, API remota,
   armazenamento ou implementação local; não comprar sem aprovação.

## Não ações

Sem execução no computador do proprietário, sem registro de usuário,
sem download de IA, sem acesso a arquivos pessoais ou financeiros,
sem instalação, deploy, Worker, merge ou gasto. Os testes no GitHub
usam os runners temporários Windows/Linux e relatórios artificiais.

**Checkpoint máximo:** `READY_FOR_OWNER_HARDWARE_READONLY_PROBE_SECURITY_REVIEW`.
