# AtlasQuant Trader — Captura HTTPS e conferência BCE G8 no AM12 (LAB, 05/11/2026)

## O que foi executado

O AM12, novamente online em 05/11/2026, foi usado para conferir duas versões locais do histórico de referências do BCE/Eurosistema. Nenhum código foi integrado ao aplicativo, nem houve custos adicionais, ativação de scheduler, worker, sinais ou negociação.

**Captura mais recente:** consulta HTTPS manual única à URL fixa `https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml` pelo módulo `atlasquant_trader_ecb_xml_manual_capture_lab.py`, usando urllib/SSL com a verificação padrão de certificados solicitada.

| Campo do recibo local | Valor |
|---|---|
| Requisição | 1 GET HTTPS, manual, sem redirects admitidos |
| Início da consulta, relógio do AM12 | 2026-11-05T23:25:27.420352+00:00 |
| Conclusão da consulta, relógio do AM12 | 2026-11-05T23:25:29.400101+00:00 |
| Resposta / tipo | HTTP 200 / text/xml |
| URL final | https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml |
| Tamanho | 69.513 bytes |
| SHA-256 dos bytes XML | `952d7f96577de4fa7bf7e9c3865c111ed5e1a690054f1750ba365d721b68fd4b` |
| SHA-256 do recibo JSON local | `4dc9c9f84540b1419d89ae847bf28584b05834f9fe4379c664aeee072b8afbce` |
| Nome do XML | `ecb_hist90d_20261105T232529406960Z_952d7f96577d.xml` |
| Nome do recibo | `ecb_hist90d_20261105T232529406960Z_952d7f96577d.receipt.json` |

O par de arquivos permanece **apenas no AM12**, dentro de `evidence/verificacao_bce_g8_20261105/` do laboratório. Nenhum XML bruto foi colocado no GitHub. A integridade do conteúdo e o tamanho foram revalidados contra o recibo, sem reescrever os arquivos.

## Conciliação com a versão existente

O arquivo anterior `ecb_eurofxref_hist_90d_capture_20261105.xml` já estava em `evidence/`, tinha 69.509 bytes, data de criação local declarada 05/11/2026 02h23 UTC e SHA-256 `5505c5bd9b1a8883d62991ccde9ad9fadba9245d612ff635dce2a5c7e0cd1690`.

- Arquivo antigo: **64 datas**, 07/08–04/11/2026. Arquivo novo: **64 datas**, 10/08–05/11/2026.
- **63 dias coincidentes; 441 valores (7 moedas × 63 datas) verificados sem qualquer divergência numérica.**
- A data 07/08 saiu da janela móvel e 05/11 entrou.
- **21/21** valores transcritos anteriormente para 02, 03 e 04/11 coincidiram com os bytes XML da captura recente.
- Os leitores puderam calcular os **28 cruzamentos de referência** para as datas testadas sem autorizar compra ou venda.
- Na auditoria completa do arquivo antigo, as 64 datas continham os sete componentes G8: **1.792 referências cruzadas deriváveis** e **1.764 variações retrospectivas consecutivas**. Isso não são operações, acertos ou preços de execução.
- Referências novas de 05/11: USD 1.1224; GBP 0.83393; JPY 177.85; CHF 0.918; AUD 1.6033; CAD 1.5675; NZD 1.9966, todas como unidades da moeda por 1 EUR. Não são cotações M15 de corretora.

## Teste no Windows e correção preventiva

O AM12 executou 17 cenários no conjunto `test_atlasquant_trader_ecb_xml_manual_capture_lab.py`: **16 passaram, um foi ignorado** por restrição de privilégio para criar symlinks (WinError 1314). O teste específico de *directory junction* foi executado. O módulo passou a recusar também junctions de diretórios como destino de escrita, usando `Path.is_junction()` quando disponível; sem efeitos em import ou execução automática. Os arquivos de código no AM12 foram comparados byte a byte pelo Git blob SHA com os blobs criados para esta revisão.

A suíte do commit anterior no GitHub foi **cancelada**, não aprovada nem reprovada; esta revisão deverá passar pelo próprio CI.

## Limites e próximo foco

O recebimento de uma resposta HTTPS e o SHA-256 fornecem um registro auditável da **coleta local**, não uma testemunha externa da hora exata de publicação de cada taxa, nem prova de qual vintage já estava disponível antes de eventos históricos. Uma janela móvel de 90 dias, dados indicativos do Eurosistema e cotações derivadas não constituem candles M15 com bid/ask, custos, licença comercial verificada ou demonstração de viés ex-ante. Permanecem `D1/W1=AGUARDAR`, `trade_authorized=false`, sem taxa de acerto comprovada.

**Próximo passo:** obter e validar preços M15 de fonte independente/licenciada, comparar as janelas de 17h de Nova York e registrar os vieses D1/W1 **antes** dos movimentos, com timestamp externo verificável, para avaliação fora de amostra.

**LAB/HARD NO-GO:** não realizar merge/deploy, operações, cobrança, Worker, Scheduler ou alterações na PR #1816 da interface.
