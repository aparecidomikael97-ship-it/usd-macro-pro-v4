# AION — Política do Proprietário: infraestrutura econômica V1

**Data:** 2026-10-08 · **Situação:** proposta em Draft / preflight somente leitura.

## Decisão do proprietário

- **Meta e limite inicial de planejamento:** R$ 200,00 por mês de custos recorrentes do ecossistema AtlasQuant/AION, incluindo serviços externos faturados, hospedagem, banco de dados, backups, APIs e assinaturas operacionais. Não inclui compra/depreciação de hardware próprio, internet residencial nem energia elétrica. Essa exclusão não equivale a custo econômico zero.
- O limite NÃO implica que a plataforma completa, 24/7 ou com centenas de clientes, será viável nesse valor. O crescimento terá orçamento e margem reavaliados com evidências e aprovação do proprietário.
- **Sem compra, assinatura, elevação de quota, troca automática de plano ou aumento de teto** sem autorização explícita e específica do HUMAN_OWNER.
- Local-first, modelos abertos e fallback offline para tarefas elegíveis; serviços pagos somente para casos justificados por qualidade, privacidade, disponibilidade ou custo total. Nada de autorização automática por aparente economia.
- Os gastos de clientes AION Negócios devem ser medidos por tenant e refletidos no preço cobrado, com margem positiva **após custos diretos e parcela dos compartilhados**, impostos, suporte e contingências. Receita não confirmada não pode financiar capacidade antecipadamente.

## Inventário e auditoria necessários antes de qualquer ativação

1. Registrar cada serviço/fornecedor, titular, modalidade de pagamento, conta responsável, custo fixo e variável, periodicidade, limites, condições de cobrança e forma segura de cancelar. Não registrar segredos nem informações bancárias no Git.
2. Reconciliar compromissos (assinaturas já contratadas), gastos liquidados, reservas, consumo ainda não faturado e serviços compartilhados **sem dupla contagem**.
3. Converter compromissos em USD para BRL somente com taxa e data verificáveis; impostos, IOF, spreads, câmbio e arredondamento devem compor a estimativa. Taxa ausente => **gasto desconhecido**, nunca zero.
4. Conservar cota de emergência e medir economia por unidade útil concluída. Antes de escalar novos clientes, comprovar margens reais, SLA, suporte, privacidade/LGPD e capacidade contratada.
5. Verificar configurações reais dos fornecedores: autoescalonamento, limites duros quando disponíveis, alertas de faturamento, backups e política de retenção. **Uma previsão no software não cancela uma fatura de um serviço externo.**

## Regras do preflight implementado nesta proposta

O arquivo `atlasquant_aion_finops_owner_brl_cap.py` complementa, não substitui:
- `atlasquant_aion_finops_metering.py` (medição e admissão por escopo em USD);
- `atlasquant_aion_finops_work_unit_economics.py` (custo por trabalho);
- `atlasquant_aion_model_gateway_v2.py` (escolha de provedor e fallback local).

O preflight é **global para todas as contas/ambientes do proprietário**, não um limite de R$ 200 multiplicado por tenant. Recebe um comprovante mensal consolidado, explicitamente verificado pelo chamador autorizado, com despesas em centavos de BRL e snapshots com no máximo 60 minutos. Sem cobertura completa, comprovação de câmbio ou custos conhecidos, **bloqueia a recomendação de nova operação paga**.

O resultado é `ALLOW_PRECHECK` até 70% do teto, `ALLOW_WITH_WARNING` a partir de 70%, `DEGRADE_PAID` a partir de 85% e `BLOCK_PAID` a partir de 100% ou na falta de evidência. Para preservar folga, novo trabalho pago é bloqueado mesmo quando preencheria exatamente 100%. O modo `ALLOW_LOCAL_ONLY` não exige comprovante financeiro se o chamador confiável já demonstrou, fora do módulo, que a operação não aciona nenhum serviço faturável.

**Essas saídas NÃO fazem bloqueio efetivo em produção:** são sugestões para integração futura. O módulo não fornece identidade, câmbio, faturamento, lock atômico de reservas, acesso a contas, aprovação do proprietário, execução de modelo ou cobrança. O provedor continua podendo cobrar por serviços já contratados. Campos `state=VERIFIED`, `scope=OWNER_ALL_ENVIRONMENTS` ou `mode=LOCAL_ZERO_VENDOR_CHARGE` só são confiáveis se autenticados pela camada de ingresso.

## Próximos trabalhos — ainda não executados

- Auditoria das despesas e planos reais de Render, armazenamento, domínio, fornecedores de modelos e integrações; nenhuma estimativa sem dados.
- Adaptador confiável para consolidar dados de consumo **USD + BRL** e câmbio auditável, com reconciliação de fatura de cada conta/tenant e do custo global.
- Reserva atômica pré-execução para impedir concorrência ultrapassar orçamento; enforcement no execution gateway e roteamento local-first seguro.
- Alarmes graduais + limites duros nos provedores que os oferecem; proteção de serviços essenciais e tratamento de custos fixos/comprometidos.
- Painel para HUMAN_OWNER com custo real/previsto mensal, compromissos, valores desconhecidos, custo por cliente, margem e justificativa para escala.
- Testes em ambiente autorizado antes de habilitar qualquer tráfego pago. Ativação, planos, cartões, deploy, Worker e merge exigem decisão própria.

## Limites nesta PR

`merge=false` · `deploy=false` · `worker=false` · `billing=false` · `provider_calls=false` · `no_real_money_evidence` · `no_owner_approval_forged`.

Esta etapa é um contrato verificável para **não perder a diretriz de economia**, não uma promessa de que hoje as despesas reais já estão limitadas a R$ 200.
