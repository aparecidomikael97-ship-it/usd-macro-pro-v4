# AION P0 — dimensionamento e orçamento da testemunha externa (não contratação)

**Data:** 10/10/2026. **Base:** Draft #1185 `d4d400aab0bb7a9f72d7a65aa134c1b227672074`. **Questão:** #1178. **Estado:** `RESEARCH ONLY / ALL 18 ENROLLMENT GATES BLOCKED / HARD NO-GO`.

## Meta desta rodada

Deixar de abrir apenas protocolos criptográficos sintéticos e examinar **volume, quotas e custo total de operar dois domínios externos**, sem provisionar recursos. A pesquisa **não** altera o orçamento de R$200/mês nem autoriza criar contas, assinar chaves reais, usar AWS/Cloudflare, mergear ou ativar o Worker.

**Fontes primárias consultadas em 10/10/2026:**
- [Cloudflare Durable Objects Pricing](https://developers.cloudflare.com/durable-objects/platform/pricing/) (atualização 30/09/2026): Free com SQLite e **100.000 DO requests/dia; 13.000 GB-s de duração/dia; 5 milhões rows-read/dia; 100.000 rows-written/dia; 5 GB storage**. Exceder limites Free **falha**, não cria autorização de uso. Workers Paid oferece 1 milhão DO requests/mês e 400.000 GB-s/mês incluídos, com mínimo de **US$5/mês** e taxas de uso acima da cota. Duração e linhas de SQL exigem métricas reais. Chamadas do Workers externo também são uma dimensão separada.
- [Workers Pricing](https://developers.cloudflare.com/workers/platform/pricing/): cota de Workers chamadores e CPU/requests deve ser avaliada **à parte**.
- [Cloudflare DO Storage](https://developers.cloudflare.com/durable-objects/best-practices/access-durable-objects-storage/): persistência SQL forte; porém o PITR pode restaurar até 30 dias, inclusive a própria cabeça; sem segunda autoridade independente não há prova contra rollback administrativo.
- [AWS S3 Pricing](https://aws.amazon.com/s3/pricing/): tarifas variam por região, classe, GB, chamadas PUT/GET/LIST, transferência, retenção de todas as versões. Esta página não constitui **cotação personalizada** nem comprova preço final em BRL.
- [AWS Object Lock](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html): COMPLIANCE resguarda versões retidas, não impede novos *delete markers* ou novas versões; GET de uma versão protegida não demonstra *head latest*.

## Três cargas HIPO TÉ TICAS para medição de capacidade (não tráfego medido)

Assumimos **12 verificações/leitura de checkpoint por tenant por dia**, **4 writes de controle por tenant por dia**, **2 DO calls por read**, **4 DO calls por write**, **2 linhas SQL lidas por DO request**, **3 linhas SQL escritas por write**, 0,005 GB-s por request, recibo de 2 KiB, retenção de 90 dias e 0,1 GB de DO storage. São hipóteses de laboratório, **não uma telemetria do projeto**, e precisam de validação antes de escolher cotas/arquitetura.

| Cenário | Tenants | DO requests/dia | SQL rows-read/dia | SQL rows-written/dia | S3 PUT/mês | S3 versões após 90 dias |
|---|---:|---:|---:|---:|---:|---:|
| Baixo | 1 | 40 | 80 | 12 | 120 | 360 |
| Esperado hipotético | 100 | 4.000 | 8.000 | 1.200 | 12.000 | 36.000 |
| Pico hipotético | 1.000 | 40.000 | 80.000 | 12.000 | 120.000 | 360.000 |

**Importante:** todos os três exemplos ficam matematicamente abaixo dos limites **Durable Objects Free** listados **somente para essa carga isolada**. **Ainda não foram incluídos no cálculo acima os limites independentes de requisições e CPU do Worker chamador, nem picos de tráfego**. Isso **não significa que o plano Free será suficiente** quando somarmos outros Workers, tenants ativos, métricas reais de compute, alarmes, limites globais de conta, retenção, picos e quotas já consumidas. Com 1.000 tenants e 80 gravações/dia/tenant, seriam **240.000 rows-written/dia**, acima da cota Free (100.000), e o simulador deve bloquear o pressuposto de gratuidade.

## O que está comprovado e o que NÃO pode ser inferido

- **Comprovado da documentação:** limites públicos, possibilidade de plano Free e que os excessos Free falham; PITR de 30 dias; S3 Object Lock COMPLIANCE protege versões, não “latest head” arbitrário.
- **Não comprovado:** valor total do novo serviço, tarifa específica AWS por região, região de residência de dados, segurança das chaves, independência de administradores, consumo de fato no projeto, telemetria de CPU/rows, custos existentes, limites por conta, FX em data de compra, tributos brasileiros, KMS, networking/egress, registros LGPD e garantias de disponibilidade.
- **Falso positivo proibido:** “Cloudflare Free → AION custa R$0” e “hipótese abaixo de R$200 → autorizado”. Tampouco uma matriz sem evidência pode virar aprovação do HUMAN_OWNER.

## Ferramenta offline de sensibilidade a preço e capacidade

`atlasquant_aion_external_witness_cost_capacity_reference_v1.py` possui uma única função pura `model_witness_cost(plan, quote=None)`. A referência calcula DO requests/rows/duration, versões S3 sob retenção em regime permanente e quantidade de PUT/GET/LIST; confere limites Free conhecidos.

O segundo argumento opcional exige **cesta completa informada explicitamente** (FX, infra existente em reais, tarifas de storage+PUT+GET+LIST AWS, egress, KMS, monitoramento, impostos e margem). Sem valores para TODOS, retorna `COST_NOT_QUOTED`, sem total. Quando fornecidos, devolve somente `quoted_partial_brl`, rotulado como **cálculo PARCIAL autodeclarado**: não cobre tarifa/uso do Worker que chama DO, capacidade já utilizada, metadados mínimos do S3, descontos/variações ou contrato real. **Nunca** preenche `full_stack_monthly_cost_brl`, `budget_certified` ou `worker_authorized`. Cálculo abaixo do limite **não é prova de custo real nem consentimento**.

Exemplo de uso só com números hipotéticos:

```python
from atlasquant_aion_external_witness_cost_capacity_reference_v1 import model_witness_cost
plan = {
    "tenant_count": 1, "reads_per_tenant_per_day": 12,
    "writes_per_tenant_per_day": 4, "do_requests_per_read": 2,
    "do_requests_per_write": 4, "do_rows_read_per_request": 2,
    "do_rows_written_per_write": 3,
    "do_duration_gb_s_per_request": "0.005", "do_storage_gb": "0.1",
    "s3_receipt_bytes": 2048, "s3_retention_days": 90,
}
assert model_witness_cost(plan)["status"] == "COST_NOT_QUOTED"
assert model_witness_cost(plan)["worker_authorized"] is False
```

**Testes previstos em Windows/Linux:** três cenários, limites DO, campo de tarifa/FX ausente, zero/NaN/valores negativos, tarifa hipotética sob/acima do teto, divergência do custo parcial e flags sempre FALSE, e verificação estática de que o módulo nunca é importado como permissão pelo Worker.

## Ordem de execução, com decisão humana separada

1. Coletar telemetria **sem dados privados**, via testes offline/candidatos locais já autorizados, de frequência de READ, writes, bytes de recibo, SQL rows e duração. Medidas físicas do proprietário continuam pendentes.
2. Escolher regiões e coletar cotação **específica** de AWS e Cloudflare + custo atual de infraestrutura, câmbio, impostos, margem, LGPD. Distinguir Free e Paid e totalize a cadeia.
3. Apresentar um orçamento consolidado em R$ confrontado com R$200, e a matriz de custódia de contas IAM administradas separadamente. **Pedir aprovação explícita antes de gastos/criar serviços**.
4. Só após autorizações próprias: matrícula externa do proprietário e tenant com chaves públicas, witness real com nonce fresco/latest head; testes físicos de A→B, PITR, Object Lock/delete marker, perda de resposta entre CF/S3 e UNKNOWN_OUTCOME.
5. Só então considerar uma integração revisada; nenhuma Flag/CI ou cálculo aprova merge/deploy/Worker automaticamente.

**Estado:** `PARTIALLY_CLOSED / HARD NO-GO`. Nenhuma compra, assinatura real, deploy ou conta criada. Core V1, main e as proteções #1180–#1182 continuam intactos. P0 #1178 e B2B #1169 permanecem abertos.

## Correção de auditoria: Workers Free e picos (10/10/2026, Draft sucessora)

A primeira calculadora considerava só Durable Objects. A documentação oficial [Cloudflare Workers Pricing](https://developers.cloudflare.com/workers/platform/pricing/) distingue as **requisições de entrada do Worker Free (100.000/dia, compartilhadas no plano/conta)** e o limite **10 ms CPU por invocação** dos pedidos RPC ao Durable Object (limite Free DO de 100.000/dia). Estar abaixo de 100.000 DO RPCs **não garante** caber nas requisições do Worker ou cumprir CPU. Os limites gratuitos são independentes, mas dependem também de outros projetos da conta. Cloudflare Workers Paid (mínimo US$5/mês por conta mais usos) não está autorizado nem inserido como tarifa certificada.

A função pura `model_witness_cost(plan, quote=None, *, worker_profile=None)` mantém as suposições antigas compatíveis e admite um perfil **opcional, autodeclarado, não medido** com:

- `requests_per_read`, `requests_per_write`: requisições inbound ao Worker por operação lógica.
- `other_account_requests_per_day`: parte de outros Workers na mesma conta, **declarada e não verificada**.
- `cpu_ms_per_invocation`: CPU por invocação assumida, sem medição.
- `peak_day_multiplier`: multiplicador hipotético para um dia de pico, aplicado também a requests/linhas/duração de Durable Objects.

**Sem o perfil:** retorna `WORKERS_FREE_USAGE_AND_PEAK_NOT_MODELED`, além das demais lacunas, sem alegar que a cota Free é suficiente.

**Com perfil:** produz `workers_total_peak_requests_per_day_modeled`, `do_peak_requests_per_day` e alertas quando o limite Workers Free de 100.000/dia, o CPU Free de 10 ms/invocação ou alguma cota DO Free é ultrapassada. `WORKERS_FREE_AND_OTHER_ACCOUNT_ONLY_SELF_DECLARED` continua obrigatório. Os limites consideram dia agregado; surtos por minuto, hibernação, CPU real, execução simultânea, outras contas e perfis reais também exigem auditoria posterior.

| Exemplo novo, apenas matemático | DO RPC/d médio | DO RPC/d pico | Worker inbound/d no pico | Estado |
|---|---:|---:|---:|---|
| 1 tenant, 1 Worker request por leitura e escrita, pico 1× | 40 | 40 | 16 | Cabe nas cotas listadas isoladamente; **não validado na conta** |
| 1.000 tenants, 6 inbound/read e 8 inbound/write, pico 1× | 40.000 | 40.000 | 104.000 | **Excede Workers Free**, mesmo abaixo de DO requests Free |
| 1.000 tenants, 1 inbound/read e 1 inbound/write, pico 3× | 40.000 | 120.000 | 48.000 | **Excede DO Free por pico**, mesmo abaixo de Workers Free |

Esses números não são throughput medido. A comparação **não** substitui métricas reais da conta, invoices, autenticação independente da testemunha ou cálculo completo do custo Cloudflare/AWS. Mesmo um `quoted_partial_brl` hipotético abaixo de R$200 mantém `full_stack_monthly_cost_brl=null`, `budget_certified=false`, `spending_approved=false`, `worker_authorized=false`. Nenhuma conta/deploy/compra foi realizada.

Fontes primárias: [Workers Pricing](https://developers.cloudflare.com/workers/platform/pricing/) (02/10/2026), [Durable Objects Pricing](https://developers.cloudflare.com/durable-objects/platform/pricing/) (30/09/2026). O modelo é uma **revisão conservadora de planejamento** e não uma nova condição positiva no Worker.


## Revisão de capacidade por objeto e bypass sob falta de quota (10/10/2026)

**Fonte Cloudflare primária:** [Durable Objects limits](https://developers.cloudflare.com/durable-objects/platform/limits/) estabelece **1 GB de armazenamento por SQLite DO no plano Free**, além dos **5 GB totais por conta**. O cálculo anterior conferia apenas o total da conta e poderia indicar uso grátis com um único objeto de 1,5 GB e conta de 2 GB. O parâmetro opcional `largest_do_storage_gb` cobre a dimensão por objeto. Sem ele, retorna o bloqueio `CF_DO_SINGLE_OBJECT_STORAGE_NOT_MODELED`; se maior que 1 GB, marca `CF_DO_FREE_SINGLE_OBJECT_STORAGE_EXCEEDED` e `FREE_CAPACITY_EXCEEDED`. É input **sintético**, nunca medição de capacidade. Retenções, índices e metadados contam para ocupação real.

**Fonte Cloudflare primária:** [Workers limits](https://developers.cloudflare.com/workers/platform/limits/) mostra que quando o plano gratuito atinge 100.000 requisições/dia, o endpoint configurado como **Fail Open** pode **passar requisições diretamente ao origin**, sem executar o Worker de verificação. Para um Worker de autenticação, exigir rota/endpoint realmente **sem bypass**, com `Fail Closed` quando aplicável e resultado erro 1027. Isso é **gate de segurança da futura infraestrutura**, não algo que a calculadora consiga comprovar por campos autodeclarados. Mesmo worker_profile abaixo do limite, conta e fail mode reais não foram atestados.

Essa descoberta impede usar estimativas hipotéticas como autorização e adiciona dois gates P0 ao manifesto de enrollment da #1185. Ainda não há uma conta de Cloudflare, route, object ID, relatório provider-side ou autorização para testá-los.
