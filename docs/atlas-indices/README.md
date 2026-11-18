# Atlas Índices — documentação do piloto de 8 ativos

**Estado:** DOCUMENTO / LAB / AGUARDAR / HARD NO-GO
**Referência documental:** 16/11/2026. **Versão consolidada:** v0.7.
**Este diretório não é um motor operacional.** Sua finalidade é preservar decisões, requisitos, evidências relatadas e lacunas para revisão.

## Prioridade atual do ecossistema

A prioridade imediata do AtlasQuant Trader é **validar a coleta e o viés macroeconômico D1/W1 em oito ativos**, reduzindo dispersão de trabalho. A arquitetura e o cadastro completo do projeto não são apagados nem substituídos pelo escopo reduzido.

**Cinco pares Forex:** EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD.
**Dois CFDs de índices:** US500, NAS100.
**Ouro:** XAUUSD.

A fonte candidata para preços é a conta **Pepperstone MT5 Demo**, sem depósito e sem operações reais ou simuladas. As observações de símbolos e contratos feitas pelo auditor ainda exigem validação de captura formal.

**Expandir somente depois de validar o piloto e com autorização do proprietário.** A expansão futura poderá incluir grupos sucessivos de Forex (5 → 10 → 28), novos índices e, em momento posterior e mediante escolha expressa, WIN e Ibovespa. Não há liberação antecipada de nenhum deles.

Importante: oito ativos facilitam execução e auditoria, mas **não reduzem automaticamente** o protocolo escolhido de 52 semanas informativas para avaliação estatística. As primeiras quatro semanas só validam o processo.

## Arquivos desta proposta

- [Especificação consolidada v0.7](ATLAS_INDICES_V07.md): escopo, fatores, PIT, avaliação e critérios.
- [Captura MT5 H1/D1/W1](CAPTURA_MT5.md): contrato apenas documental, sem código ou instalação.
- [Decisões e lacunas](DECISOES_PENDENCIAS.md): decisões já comunicadas, três pendências e pontos não verificados.
- [Histórico v0.5 a v0.7](HISTORICO_VERSOES.md): mudanças preservadas e referências às versões textuais anteriores.

## Integridade e alcance

Esses arquivos **consolidam** a documentação produzida nas conversas e comandos anteriores. Não são cópias integrais palavra por palavra dos documentos longos v0.5, v0.6 e v0.7. A versão v0.7 é a especificação de referência consolidada para revisão; a cadeia de alterações está registrada no histórico.

**Não alterar:** main, cadastro oficial FX28, campanha FX28 de 672 oportunidades, protocolos CPI/PPI congelados, workflows, PRs técnicas, Motor A completo, Radar/Painel Mestre ou capacidades de execução. Nenhuma operação ou deploy é autorizado por esta PR.

**Regras de segurança:** não armazenar chaves, logins, números de conta, senhas, tokens, dados de acesso ou evidências brutas sensíveis. Merge apenas por decisão separada do proprietário após auditoria independente.