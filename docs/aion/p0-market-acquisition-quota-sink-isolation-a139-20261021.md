# AION P0 A139 — Isolamento do coletor: orçamento, aquisição e destino (LAB)

21/10/2026 · Stack Draft A138 → A139. Não há merge, deploy, execução de Global Worker, interação com corretora/fornecedor, consumo de créditos de API ou gravação de Checkpoint Mestre.

## Diagnóstico cruzado (Codex local, read-only)

Codex foi executado em modo read-only no Desktop Commander em uma cópia local de projeto SEM .git. O snapshot é histórico e faltava o módulo autopilot_setup_audit_v114.py; não é evidência do HEAD GitHub. Observou que coleta_automatica_v86.py executa o Streamlit inteiro, e o fluxo Autopilot fornece token Github e chaves de mercado no mesmo processo. Twelve Data reserva crédito num GitHubStore e o código antigo grava muitos snapshots via PUT. Saída zero do processo não garante persistência. Essas observações motivam A139, mas não demonstram acidente real.

## A139 é implementação de CONTRATO sintético, não coleta real

Novo atlasquant_market_boundary_a139.py separa:
- SyntheticMarketFeed, único source type aceito em LAB; não faz HTTP, não recebe chaves externas e nunca chama Autopilot/Streamlit;
- MemoryOnlyReservationLedger, quota limitada 1..100, reserva por run_id ANTES de ler, sem expansão automática; duplicidade ou indisponibilidade bloqueiam antes de consultar; timeout mantém unidades reservadas e impede reenvio;
- validação estrita de símbolos EUR/USD, USD/JPY, GBP/USD, bid/ask finitos positivos e bid menor que ask, sem campo extra nem secret;
- sink local com nome derivado somente de run_id validado, diretório existente FORA do checkout, rejeição de symlinks, sobrescrita, caminho dinâmico de GitHub/Checkpoint; escrita de um único JSON via criação exclusiva, flush e fsync;
- JSON/cálculo SHA-256 canônicos da carga; status principal sempre SYNTHETIC_OUTPUT_NOT_LIVE, sem proveniência externa, owner/Worker ou freshness claims.

Driver tools/aion_p0_market_synthetic_capture_demo_a139.py só gera duas cotas simuladas e resultado em runner.temp; workflow A139 usa contents:read, checkout persist-credentials:false, sem secrets, sem cron, sem chamadas de dados, e upload-artifact de três dias. São dados artificiais pré-fixados, sem qualquer utilidade para negociar no mercado.

## Cenários de segurança

30 testes adversariais A139: reserva antes de ler; zero leitura sem crédito; run_id duplicado; timeout/erro sem retry ou refund; formato errado/inversão/NaN/boolean/secret; símbolo fora da allowlist/duplicado; paths absolutos/outside/traversal/symlink/overwrite; SHA e flags de ausência de autoridade; rejeição de objetos de fonte/quota arbitrários; ausência de privilegio mesmo com env flags de owner/witness. Reexecuta também 25 testes A138 de dados e 14 do workflow. Cross-platform Windows + Ubuntu.

## Lacunas deliberadamente em HARD NO-GO

- MemoryOnlyReservationLedger não é durável. Não comprova contabilidade de créditos reais, operação exatamente uma vez, atomicidade distribuída nem reconciliação após crash; não deve receber provedor sem mecanismo externo independente de reservas/recibos.
- Não integra o A139 ao Autopilot, ao Streamlit ou à main. Não coleta novas cotas. A137 permanece Draft congelando jobs apenas em LAB; não é solução de continuidade legítima da coleta.
- A escrita local no diretório temporário não constitui ACL de mercado em produção e não elimina race/symlink em uma máquina hostil; exigir destinação isolada e escopo de serviço separados antes de produção.
- Falta desenho de process-level credential isolation: ambiente, secret store, GitHub App/fine-grained permissions por repositório, quotas reais, lgpd/licenças/retenção, observabilidade e incident recovery.
- Nenhum testemunho externo HEAD monotônico, identidade HUMAN_OWNER, efeito/no-effect do fornecedor ou 6 P0 foram homologados. A139 testa contrato e não remove os HARD NO-GO anteriores.

Quality canônica original (588 módulos / 6.895 testes) e Security A74 original (365) devem rodar no HEAD final, sem alterar baseline de 85 identificadores conhecidos. Registre apenas o que a CI confirmar.

**HARD NO-GO · 0/6 P0 homologados · Worker OFF · ZERO_AUTO_RESEND · sem merge, deploy ou novos gastos.**