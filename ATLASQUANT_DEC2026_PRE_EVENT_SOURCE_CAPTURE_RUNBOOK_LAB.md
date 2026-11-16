# Motor A — runbook de captura pré-evento CPI/PPI nov/2026 (LAB)

**Estado:** RASCUNHO / LAB / AGUARDAR / HARD NO-GO. Sem viés, previsão, robô, custo, ordem ou alteração na campanha FX28 #1884. Este runbook e a PR não ativam um serviço nem agendamento.

## 1. Janelas estritamente futuras e verificáveis

O BLS agenda, sujeito a mudanças:

| Evento | Relatório referente a | Release UTC | Cuiabá (UTC−4) | Início da coleta (UTC) | Fim imutável (UTC) |
|---|---|---|---|---|---|
| `US_CPI_NOV2026` | CPI nov/2026 | 2026-12-10 13:30 | 10/dez 09:30 | 03/dez 13:30 | 10/dez 12:30 |
| `US_PPI_NOV2026` | PPI nov/2026 | 2026-12-15 13:30 | 15/dez 09:30 | 08/dez 13:30 | 15/dez 12:30 |

Fonte do calendário: https://www.bls.gov/schedule/2026/12_sched_list.htm (rever antes de cada execução). Os horários válidos para pesquisa são o instante **real de captura**, não a publicação histórica alegada pelo provedor. Uma consulta entre o início e o fim da janela ainda exige conteúdo e recibo válidos; não pressupor disponibilidade de consenso numérico.

## 2. Antes de capturar qualquer coisa

1. Confirmar novamente na fonte oficial BLS se a data e hora do evento continuam iguais e se a referência mensal é novembro de 2026. Se alteradas: **não usar este coletor inalterado**; novo PR, revisão do contrato, novas provas.
2. Verificar se o fornecedor permite consulta e retenção local conforme seus termos. Dados TD/Trading Economics não devem ser publicados ou distribuídos em PR pública.
3. Confirmar que o computador tem UTC correto, rede, pasta privada LAB existente, acesso apenas de leitura às páginas do fornecedor e espaço suficiente.
4. Identificar previamente o documento real TD Economics `upcoming.htm` da **edição daquela semana**, sem inventar URL. Não transferir um arquivo antigo para a nova janela.
5. Executar uma fonte por vez, com opção explícita. Se houver 403, redirecionamento, HTML insuficiente, relógio fora da janela ou falta de `Date`, parar com NO-GO, sem retry automático.

## 3. Comando exemplo — somente dentro da janela

```powershell
$root = Join-Path $env:LOCALAPPDATA 'AtlasQuant\LAB\dec2026_consensus_originals'
New-Item -ItemType Directory -Force -Path $root | Out-Null

# Exemplo do provedor Trading Economics, CPI. Só é seguro executar
# entre 03/dez/2026 13:30Z e 10/dez/2026 12:30Z, após conferir BLS.
python -m atlasquant_trader_us_dec2026_consensus_original_one_get_lab --capture-official --confirm-bls-schedule-reviewed --event-root US_CPI_NOV2026 --provider TRADING_ECONOMICS --source-url https://tradingeconomics.com/united-states/calendar --output-root $root
```

Para o PPI, alterar o evento para `US_PPI_NOV2026` e usar sua janela. Para TD Economics, usar o `upcoming.htm` específico comprovado na semana e `--provider TD_ECONOMICS`.

O programa **faz uma única GET**, sem tentativa de repetição nem provedor alternativo; salva `original.html` e `receipt.json` em subdiretório único, verifica SHA-256 dos bytes gravados e reexecuta o validador PIT. Só depois de receber sucesso desse replay existe cópia documental local. O resultado **não é consenso semântico validado**.

## 4. Como interpretar o resultado

- **PASSOU (documental):** bytes/HTTP/URL/horários/digest consistentes, guardados localmente; `numeric_consensus_semantics_authenticated=False`, `original_source_first_seen_independently_authenticated=False`, `trade_authorized=False`.
- **FALHOU:** não preencher nenhum campo futuro com valores encontrados via pesquisa. Não contar como ausência de surpresa nem como acerto. Se precisar de nova tentativa, exige revisão explícita; a ferramenta jamais repete automaticamente.
- **Pendências obrigatórias:** parser semântico de CPI/PPI novembro que diferencie consenso, anterior e previsão própria, evidência de horário independente, previsão direcional pré-comprometida e avaliação OOS/execução bid-ask. Dois documentos de fornecedores para o mesmo CPI/PPI são um evento econômico, não duas oportunidades independentes.

**Observação:** fontes privadas só devem ser retidas em armazenamento controlado e permitido; os históricos oficiais BLS set/out 2026 já foram salvos separadamente no Drive, sem autorizar o envio de snapshots de provedores terceiros à nuvem pública.
