# AION Backup & Recovery Policy V1

## Objetivo

Reduzir risco de perda silenciosa de código, memória e continuidade.

## Camadas obrigatórias

1. **Source Archive**  
   ZIP do repositório com SHA256, teste de extração e arquivos críticos.

2. **Checkpoint Version History**  
   Histórico separado do checkpoint/runtime, com verificação de integridade.

3. **Secondary Copy**  
   Cópia adicional separada da referência primária.

## Source Backup

O workflow de backup de código agora:
- gera manifest;
- gera SHA256;
- executa `sha256sum -c`;
- executa `unzip -t`;
- valida presença de arquivos críticos;
- só depois publica o artefato;
- mantém real execution desligado.

## Runtime

O checkpoint de runtime não deve ser empacotado como se fosse apenas código da
main. Ele continua em fluxo versionado e de recovery separado.

## RPO e RTO

O sistema não inventa metas. O administrador define:
- RPO: perda máxima de dados aceitável em horas;
- RTO: tempo-alvo de recuperação em horas.

Essas metas são planejamento interno, não SLA comercial automático.

## Restore

Restore real:
- exige integridade;
- exige revisão humana;
- não pode ser acionado automaticamente;
- primeiro deve ser ensaiado em local/sandbox/staging;
- produção permanece fora deste contrato.

## Cópia secundária

O backup não é considerado completo sem uma referência secundária diferente da
cópia primária. A implementação física desse destino continua pendente.
