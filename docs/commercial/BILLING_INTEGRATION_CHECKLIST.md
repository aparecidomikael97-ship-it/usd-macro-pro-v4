# AtlasQuant — Checklist de Pagamento e Assinatura

**PREPARAÇÃO INTERNA — NENHUM PROCESSAMENTO DE PAGAMENTO É HABILITADO POR ESTE DOCUMENTO.**

Antes de integrar cobrança:
- Escolher provedor de pagamento suportado na região.
- Definir produtos, planos, moeda, impostos e período de cobrança.
- Usar checkout hospedado/tokenização; não armazenar número completo de cartão.
- Validar webhooks assinados, idempotência e repetição segura.
- Separar estados: pendente, ativo, inadimplente, cancelado e reembolsado.
- Vincular entitlement de produto sem elevar permissões administrativas.
- Testar sandbox, chargeback, cancelamento e falha de webhook.
- Definir política de reembolso/cancelamento aprovada.
- Auditar logs para não registrar dados sensíveis.
- Ativação pública e `billing_ok=True` exigem integração real verificada e revisão humana.
