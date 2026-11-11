# AtlasQuant Trader — ligação PPI realizado × reação de 7 pares USD, LAB (11/11/2026)

**Estado:** código preparado **antes** do PPI de outubro/2026, agendado pelo BLS para sexta, **13/11/2026 às 08h30 ET / 13h30 UTC / 09h30 MT**. Não há PPI realizado de outubro nem velas de 13/11 autenticados neste checkpoint. PR #1851 continua rascunho; sem merge, deploy, Worker, negociação, novas fontes pagas ou uso de MT5.

## Lacuna e implementação

Havia dois leitores independentes:

1. `atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab.py` — primeira impressão documental do BLS para headline `FD/4` e núcleo sem alimentos/energia `FD/49104`, comparada com TD Economics e Trading Economics congeladas antes da divulgação.
2. `atlasquant_trader_ppi_usd_fx_forward_reaction_lab.py` — 17 velas fechadas M15 de cada um dos **sete** pares que contêm USD, para janelas +15 min, +1 h e +4 h.

Novo `atlasquant_trader_ppi_one_event_study_join_lab.py` exige **ambos** antes de produzir um estudo completo. Ele reexecuta os validadores originais sobre os bytes dos documentos e CSVs: não aceita um simples dicionário externo alegando `PASS`. Os hashes TD/TE devem ser os dois já registrados no checkpoint pré-evento. O HTML BLS precisa ser obtido e validado **depois** de 13h30 UTC. O preço precisa estar fechado até **17h30 UTC**, e os sete arquivos devem estar presentes e com hash íntegro.

### Comportamento obrigatório

| Situação | Estado |
| --- | --- |
| Antes de 13h30 UTC de 13/11 | `LAB_WAIT_PPI_OFFICIAL_RELEASE` |
| Entre 13h30 e 17h30 UTC | `LAB_WAIT_FX_FOUR_HOUR_WINDOW` |
| Falta qualquer uma das fontes ou hashes, métrica ou preço são inválidos | `LAB_PPI_STUDY_BLOCKED` |
| Todas as etapas documentais passam, ainda sem atestação externa | `LAB_PPI_ONE_EVENT_SEVEN_FX_DOCUMENTARY_NO_GO` |

No último estado, o relatório mostra somente **surpresa PPI em pontos percentuais**, retornos matemáticos USD-normalizados em **bps** e hashes de identificação. Não mostra taxa de acerto, causalidade ou sinal. **Sete pares no mesmo PPI são um grupo de evento econômico, não sete amostras estatisticamente independentes**. O preço de fechamento da vela pré-evento não é uma cotação bid/ask executável e não autoriza simulação de lucro após custos.

## Prova de código e limites

- `test_atlasquant_trader_ppi_one_event_study_join_lab.py`: testes sintéticos de espera, fonte ausente, HTTP 403, série de núcleo incorreta, adulteração de bytes, janela não encerrada, arquivo de par ausente, captura de preço prematura e agrupamento um evento/sete pares.
- Para exercitar o caminho positivo sem falsificar os hashes reais, **os dois validadores pré-evento são simulados apenas em um teste de integração**. Os leitores TD/TE possuem testes próprios, e outro teste confirma que HTML sintético sem o hash congelado é rejeitado. O leitor BLS e as sete séries sintéticas de preço são reexecutados no caminho positivo.
- A suíte offline de Python 3.11/3.12 do laboratório inclui o novo módulo. Passar nos testes **não equivale** a observar resultado econômico, verificar fonte independente, estimar efeito causal, validar 80–90% de acerto ou garantir lucro.
- Os HTMLs originais e os candles reais permanecem sob a custódia local do AM12; nenhum dado de conta, credencial, arquivo bruto pago ou feed real foi enviado ao código.

## Próximo passo real (sem antecipar o evento)

1. Manter os dois agendamentos já existentes para consenso 12/11 e resultado 13/11; não duplicar.
2. Após divulgação, registrar bytes e SHA do BLS com as definições das métricas, sem inventar valor se houver bloqueio 403 ou mudança na Tabela 1.
3. **Após 17h30 UTC**, obter em modo read-only as 17 velas M15 para cada par, verificando relógio do servidor, sessões, origem e integridade; não supor acesso ao AM12/MT5.
4. Executar o estudo documental e adicionar observações prospectivas ao longo de muitos eventos com denominador e baseline congelados. Calibração de probabilidade e execução real continuam **NO-GO**.
