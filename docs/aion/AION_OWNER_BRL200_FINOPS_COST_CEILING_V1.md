# AtlasQuant/AION — Diretriz FinOps de R$ 200 mensais V1

**Data:** 2026-10-08  
**Status:** IMPLEMENTATION SAFE — Draft/CI-only, sem cobrança ou deploy  
**Base:** main `5744b2b7b17c84331e6f27c569064993ff587782`

## Objetivo econômico

Meta inicial de despesas operacionais **recorrentes pagas pelo proprietário**:
**até R$ 200 por mês**. Não inclui aquisição de computador/GPU,
internet residencial ou energia, que devem continuar sendo informadas
à parte para aferir o custo econômico real. A exclusão do orçamento não
torna esses recursos gratuitos.

O limite deve ser reavaliado conscientemente se houver faturamento e
expansão. Não é estimativa suficiente para operação de centenas de
empresas com disponibilidade permanente. Nenhuma receita prevista de
clientes reduz automaticamente as despesas que o proprietário contrata
e paga. Despesas de clientes, descontos, impostos e margem devem ser
medidos separadamente.

## Princípios obrigatórios

1. **Local-first / AION-first:** usar recursos locais e software livre
   quando o equipamento suportar desempenho, memória e qualidade
   suficientes. Modelo local consome energia e hardware e pode não
   equivaler à capacidade de um serviço remoto.
2. **Provedor pago é exceção:** nunca fazer fallback pago automático.
   Qualquer requisição paga exige estimativa, conferência de saldo e
   autorização separada do proprietário. Sem autorização ou custo
   conhecido: bloquear e preservar modo local seguro, quando viável.
3. **Uma conta, vários componentes:** somar hospedagem, banco, backups/
   armazenamento, APIs de IA, voz/vídeo, comunicações, domínio,
   observabilidade e outros compromissos recorrentes do proprietário.
4. **Margem:** estimar o custo mensal integral de cada cliente antes
   da proposta; receita deve exceder custo com margem de segurança,
   incluindo suporte, impostos, reprocessamentos e infra compartilhada
   na análise futura. Preço e cobrança continuam sujeitos a aprovação.
5. **Resiliência:** se uma função ficar cara, usar primeiro redução
   de consumo, cache, loteamento, agendamento, modelo local ou fila;
   funções críticas nunca devem mentir sobre sucesso ou abrir brecha
   de segurança para economizar.

## Preflight em reais — entregue neste Draft

O novo `atlasquant_aion_owner_brl200_finops_ceiling_v1.py` fornece:

- **Teto rígido de planejamento:** 20.000 centavos/mês.
- **Aviso/degradação:** 14.000 centavos/mês (70%).
- **Alerta crítico:** 18.000 centavos/mês (90%).
- Entrada conservadora de despesas em BRL (centavos inteiros) e USD
  (micros inteiros); a cotação BRL/USD é um *input manual ou de fatura*
  datado, sem consulta cambial automática.
- Cotação deve ter no máximo **3 dias**, não pode estar no futuro,
  e custos em dólar têm **reserva cambial de 10%** e arredondamento
  para cima para centavos. Isso é proteção estimativa, não taxa
  oficial nem previsão garantida.
- Identidade de proprietário e mês conferidas; categorias conhecidas,
  IDs duplicados idênticos deduplicados, IDs conflitantes bloqueados.
- Compromissos confirmados, reservados e previstos entram na mesma
  projeção. Despesa de montante desconhecido bloqueia; não é zero.
- Snapshot com digest não autenticado para detectar adulterações
  acidentais, sem fingir ser recibo bancário.
- Resultado de decisão **sem efeito colateral**: bloqueia qualquer
  solicitação paga acima do limite ou sem custo verificável; abaixo do
  limite ainda retorna `REQUIRES_SEPARATE_OWNER_APPROVAL`, NUNCA
  `PAID_EXECUTION_AUTHORIZED`.
- Solicitações de trabalho de custo marginal zero podem ser propostas
  como `LOCAL_ONLY_ADVISORY`; não são execuções automáticas.
- Análise básica de margem do cliente não contabiliza faturamento
  previsto como saldo líquido disponível para custear a conta do dono.

## Exemplos apenas ilustrativos (não são despesas confirmadas)

- Com R$ 90 já previstos, restariam R$ 110 da **meta**. Isso NÃO
  confirma saldo bancário disponível ou cobertura de todas as faturas.
- Com R$ 140 já previstos, o modo de planejamento entra em degradação.
- Com R$ 180, entra em alerta crítico.
- Com R$ 199, um novo serviço de R$ 3 ficaria bloqueado na prévia.
- Com R$ 200, uma nova contratação paga também fica bloqueada.

## Limites honestos do que ainda NÃO está ativo

- O código ainda não intercepta chamadas reais de todos os provedores,
  hospedagens ou assinaturas e **NÃO pode impedir um prestador externo de
  efetuar cobrança**. Nem a cobrança real nem o total de faturas foi lido.
- Não há ligação com faturas de cartão/banco/Render/serviços/API para
  conciliação, nem tarifa histórica/cotação cambial autenticada.
- Não há ledger de reservas atômicas persistente, proteção de
  concorrência em chamadas simultâneas, gateway de execução integrado
  ou auditoria financeira de ciclo completo.
- Não há prova de que todo gasto recorrente tenha sido informado.
- Não valida se o modelo local desejado cabe em RAM/VRAM e latência
  do computador. Esta medição precisa ocorrer futuramente.
- Não substitui os módulos existentes `atlasquant_aion_finops_metering.py`,
  `atlasquant_aion_cost_center.py` e
  `atlasquant_aion_finops_work_unit_economics.py`.
  É um contrato específico de meta mensal do proprietário em BRL para
  futura integração mediante teste e autorização.

## Critérios para ativação futura (não autorizada aqui)

- Inventário confirmado das despesas recorrentes, proprietário
  responsável e renovação; fontes de fatura confiáveis.
- Registro durável e atômico de comprometimentos, conciliação de
  prévia x fatura real e limites por fornecedor/tenant com bloqueio
  antes do gasto.
- Verificação separada do modelo local e capacidade da máquina.
- Planejamento de backup/atualizações sem custos ocultos e medição
  de operação noturna/24h.
- Publicação de relatórios de FinOps e custo por cliente sem dados
  pessoais expostos.
- Aprovação explícita antes de comprar/assinar, mudar orçamento,
  mesclar na main, fazer deploy ou ativar qualquer Worker.

**O máximo que esta PR pode demonstrar é a correção de um preflight
de planejamento em testes; não é enforcement financeiro em produção.**
