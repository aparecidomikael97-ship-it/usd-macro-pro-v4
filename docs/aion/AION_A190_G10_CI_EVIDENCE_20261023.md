# A190 G10 — evidência da decisão documental e guardas FinOps

**Data local:** 23/10/2026 (Cuiabá/AMT). **PR Draft #1497** empilhada sobre #1496; sem contas, Worker ou provedor ativado.

## CI de pré-flight confirmada

**Código, testes e workflow SHA:** a2f7bfe1cfe535d57969c572efd52a1b3bb9d625.

- [Workflow GitHub Actions #40050043556](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40050043556): **completed / success**.
- Job **120740490028**, Ubuntu: **12 tests, OK**.
- Job **120740489822**, Windows: **12 tests, OK**.
- Total **24 execuções unitárias de laboratório documental**. Python 3.12; apenas biblioteca padrão. Não são testes com serviços AWS, Google, Cloudflare ou Supabase.

## Evidência por classificação

| Marcador nos dois logs | Critério testado |
| --- | --- |
| A190_G10_ALL_DOCUMENTED_OPTIONS=HARD_NO_GO_NO_PROVIDER_CHOSEN | 4 opções pesquisadas continuam NO-GO operacional |
| A190_G10_CLOUDFLARE_PITR_AND_ADMIN_BOUNDARY=RED_EXTERNAL_FLOOR_NOT_PROVEN | Preço gratuito não remove possibilidade de restauração por administrador |
| A190_G10_DYNAMODB_CONDITIONAL_WRITE_NOT_VENDOR_EFFECT=DENY | Reserva condicional não é recibo do fornecedor de efeito |
| A190_G10_FIRESTORE_EXISTS_FALSE_NO_INDEPENDENT_ROOT=DENY | Create-if-absent não prova custódia independente |
| A190_G10_SUPABASE_FREE_H0_AVAILABILITY=NOT_PROVEN | Pausa/inatividade, sem SLA/backups Free, impedem alegar H0 homologado |
| A190_G10_FORGED_SELF_ATTESTED_ALL_EXTERNAL_GATES=NO_GO | Mesmo 12 reivindicações de prova externas enviadas pelo chamador não promovem GO |
| A190_G10_UNKNOWN_VENDOR=DENY | Fornecedor não pesquisado não recebe permissão |
| A190_G10_UNKNOWN_FX_BILL_TAX=DENY_PROVISIONING | Sem fatura, câmbio e tributos confiáveis, não aprova desembolso |
| A190_G10_R200_CAP_AND_R250_EXCEPTION=OWNER_APPROVAL_REQUIRED | Estimativa dentro do teto excepcional não equivale à aprovação de Mikael |
| A190_G10_ZERO_COST_DOES_NOT_PROVE_INDEPENDENT_ROOT=DENY | Faixa gratuita não supera falha de raiz |
| A190_G10_H0_AUTHORITY_ABSENT=DENY_AND_ZERO_AUTO_RESEND | Autoridade indisponível não habilita efeito novo nem reenvio |
| A190_G10_INVALID_FINOPS_INPUT=FAIL_CLOSED | NaN, números negativos ou dados malformados não autorizam custo |

## Alcance limitado: PASS de regra de decisão, NÃO de fornecedor

O avaliador roda **offline** com fixtures de recursos documentados de páginas oficiais. Não se conecta a nenhuma API de terceiro, não verifica conta, IAM, snapshot, revogação, assinatura raiz, efeito externo, fatura verdadeira ou SLA real. Não homologa nenhuma capacidade; os tests só demonstram que o gate **não concede uma aprovação por declarações sem comprovação externa**.

As páginas originais e datas de referência, limites, preços e riscos administrativos ficam registradas no arquivo principal G10: docs/aion/AION_A190_G10_EXTERNAL_CUSTODY_OPTIONS_20261023.md.

**Riscos que não foram solucionados:**
- raiz externa/prova HUMAN_OWNER, pin e emissor independente;
- idempotência do provedor REAL de efeito, não da tabela de reserva;
- rollback conjunto de host+cloud, superusuário de conta cloud, restauração privilegiada ou má distribuição de credenciais;
- H0 efetivo com queda de energia e indisponibilidade prolongada;
- custos e margens operacionais verificados, aprovação do proprietário, LGPD/SLA;
- Quality/Security canônicas, cinco external-RED por SO e 43 advisories herdados.

## Governança

PR permanece Draft sem merge/main/deploy/Worker. Sem abrir conta, cadastrar cartão, ativar Free/Paid, adquirir assinatura, armazenar credenciais, faturar ou enviar efeitos.

**0/6 P0 — HARD NO-GO — UNCERTAIN — ZERO_AUTO_RESEND.**

A próxima decisão que depende de novo escopo/autorização do proprietário é escolher se haverá futuramente um sandbox externo específico para prova adversarial. Até lá, capacidade descrita em documentação oficial ≠ capacidade comprovada para o AION.
