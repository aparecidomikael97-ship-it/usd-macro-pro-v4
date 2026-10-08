# AION Local-First + FinOps — Planejamento de modelos e fallback V1

**Data:** 2026-10-08  
**Status:** PR Draft / CI com dados 100% artificiais  
**Base:** PR #1073 (diagnóstico read-only de hardware); #1070–#1072 (FinOps R$ 200 e simulações)

## Objetivo

O AION deve buscar inteligência forte com o menor custo sustentável,
mas **não pode confundir um computador aparentemente potente com
capacidade real de executar um modelo**. Tampouco deve transformar
um fallback pago em uma cobrança sem autorização.

Esta etapa prepara um **contrato de decisão** para o momento em que
houver dados reais do computador e testes de inferência. Os
resultados presentes são apenas fixtures falsos para validar lógica.
Nenhum modelo é baixado, carregado, executado ou treinado.

## 1. Requisitos por tarefa, não por propaganda de modelo

As tarefas de AION são agrupadas em:

- `GENERAL_TEXT`: conversa geral;
- `B2B_DOCUMENT_DRAFT`: textos e documentos de Negócios;
- `MACRO_EDUCATION`: conteúdos didáticos de macroeconomia, **sem execução de trade**;
- `VOICE_INTENT_TEXT_ONLY`: interpretação de comandos já transcritos,
  **sem capturar microfone nem processar áudio real**.

A CI usa limiares **apenas ilustrativos** para pontuação artificial
de qualidade/segurança e p95 de latência artificial. Eles NÃO
representam benchmarks medidos, padrões homologados ou garantia de
segurança operacional.

Os nomes de modelos são restritos a `ci-model-...` para impedir que
fixtures pareçam certificados sobre modelos comerciais reais.

## 2. Capacidade antes de escolha local

O revisor aceita apenas o relatório agregado e não autenticado da
#1073; desconfia dos próprios inputs. Ele verifica:

- RAM em uso estimada no fixture limitada a no máximo **65% da RAM total**
  declarada, conservando margem para Windows, AION, navegador e memória;
- pesos do modelo dentro de **75% do espaço livre** informado;
- p95 de latência, qualidade e segurança **fictícios** frente a critérios
  mínimos de comparação por tarefa;
- qualquer dependência de VRAM dedicada diferente de zero impede
  conclusão: a etapa #1073 **não mede VRAM dedicada de forma confiável**.

Esses percentuais são margens de planejamento, não validação física:
dependem de modelo, quantização, contexto, CPU/GPU/driver, memória
compartilhada, sistema operacional e número de usuários.

Um candidato sintético aprovado vira apenas
`CI_SYNTHETIC_LOCAL_OPTION_FOR_REVIEW_ONLY`.
A avaliação negativa gera
`CI_LOCAL_QUEUE_OR_DEGRADE_REVIEW_ONLY`.
Nenhum resultado pode autorizar instalação ou inferência local real.

## 3. Roteamento de custo: bloqueio antes do pagamento

O planejador exige o snapshot de orçamento do proprietário da #1070
validado novamente pela #1071, o mês/owner esperados e uma referência
externa exata da análise sintética. Os digests detectam divergência
acidental, mas **não são assinaturas nem prova independente**.

Fluxo de decisão:

1. Se a opção local é apenas candidata pelos **fixtures**, propor
   teste local futuro e **não propor imediatamente API paga**.
2. Se o fixture indica desempenho/qualidade insuficiente e não foi
   fornecido orçamento para API, recomendar fila ou redução de tarefa.
3. Se o fixture falha e existe orçamento/estimativa de fallback pago
   dentro dos R$ 200 declarados, emitir somente proposta que
   **requer autorização separada do HUMAN_OWNER**.
4. Se o teto projetado é superado, a taxa cambial é inválida ou
   a cotação é desconhecida, bloquear a proposta paga.

Mesmo o resultado favorável **não cria reserva real**, não aciona API,
não usa credencial, não solicita pagamento, não aprova cobrança, não
ativa roteador de produção e não modifica o PC.

O limite **R$ 200/mês** é meta inicial de despesas operacionais
recorrentes do proprietário, sem equipamento, internet e energia.
Ainda não foi comprovado por todas as faturas, e não garante
operação de centenas de clientes 24 horas por dia.

## 4. Evidências exigidas futuramente

Antes da escolha de qualquer IA local de produção:

- Medir o equipamento do usuário com consentimento explícito e
  determinar CPU, RAM livre sob carga e VRAM real por API confiável.
- Confirmar licença/model card, hash e proveniência dos pesos/modelo.
- Medir latência real p50/p95, throughput, pico de RAM/VRAM, consumo
  elétrico, qualidade e taxa de erro por tarefas representativas.
- Validar isolamento de dados e confidencialidade entre tenants,
  controle de ferramentas, prompts adversariais e LGPD.
- Medir volume de requisições concorrentes, disponibilidade, custos
  de energia e manutenção. Medir custo por cliente B2B com margem
  positiva real depois de impostos e suporte.
- Conectar fontes reais de fatura somente com autorização, reconciliar
  compromissos e limitar despesas também dentro de cada fornecedor.
- Implantar um gateway confiável que exija autorização específica por
  solicitação paga e reserva financeira durável; nada disso é ativado aqui.

**Proibição contínua:** sem merge, deploy, Worker, download de modelos,
ativação de serviços, acesso ao PC, execução de gastos, alteração do
Windows Registry/ACL/startup ou autoatualização de orçamento.

**Status máximo de V1:**
`READY_FOR_LOCAL_MODEL_AND_FINOPS_ROUTING_SECURITY_REVIEW`
(CI-only, não é implementação de roteador em produção).
