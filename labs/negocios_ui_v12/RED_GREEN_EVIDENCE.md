# RED → GREEN | CRM UI V1.2 | 16/10/2026

**Âmbito:** laboratório HTML autocontido em Chromium Linux. Nenhuma ação real.

| Conjunto | Base V1.1 (antes) | V1.2 corrigido |
|---|---|---|
| 8 regressões adversariais novas | **8 FAIL** / 8 executados | **8 PASS** / 8 executados |
| 4 regressões complementares | Não pertenciam ao RED original | **4 PASS** / 4 executados |
| Smoke V1.1: desktop/mobile | previamente 19 + 15 grupos | **19 + 15 grupos PASS** |
| Sete larguras × 5 telas | Não nesta rodada antes da correção | **35 combinações PASS** |

As mesmas oito asserções adversariais iniciais foram mantidas RED→GREEN. Arquivos de log preservados no pacote. Nenhuma alegação de segurança de produção ou de comportamento do backend do AtlasQuant.

## Pendente

A validação real de prova de pagamento, estoque e privacidade depende de fontes independentes, autenticação RBAC, controle de tenant, guardas produtivos e testes físicos. O simulador **não envia**, não armazena dados reais e não deve ser associado a cliente.
