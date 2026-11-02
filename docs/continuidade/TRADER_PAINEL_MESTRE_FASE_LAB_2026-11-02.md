# AtlasQuant Trader — Painel Mestre, continuação LAB (02/11/2026)

**Status:** IMPLEMENTADO / EM VALIDAÇÃO, sem merge e sem deploy desta revisão.  
**Base:** interface aprovada e publicada no commit `f030bf2e`; PR LAB #1803.  
**Governança:** Checkpoint Mestre 22/09, reconciliação 29/09, inventário Trader T01–T58 da PR #1473. Havendo conflito, decisão aprovada mais recente prevalece. Nenhum novo store do núcleo AION.

## Missão
O Painel Mestre explica **por que** um mercado pode mover-se, mas não fornece ordem, previsão infalível ou autorização de entrada. Ele separa evento e contexto macro, confirmação técnica e guardião de risco. O resultado legítimo inclui "aguardar" e "sem dados".

## O que já foi implementado nesta etapa LAB

- Contrato diário e dos próximos **seis dias** a partir de uma **única consulta controlada** `economic-events` EODHD por cache-hora (somente ao abrir a área, caso a credencial existente tenha direito). Sem alterações de plano, cobranças autorizadas ou cron.
- A normalização reconhece país/moeda, data UTC convertida para Brasília, período, base (MoM/YoY/QoQ), consenso, anterior, real, surpresa (real − consenso), identificação e horário da fonte. Campos ausentes não são inventados.
- Resultados futuros nunca podem aparecer como divulgados. Um consenso inserido manualmente exige perfil ADMIN, autor, fonte e data anterior ao release. O automático prevalece. Essa inclusão ainda é **temporária na sessão**, não durável.
- **Briefing macro:** número de divulgações recebidas, eventos por vir, resultados com consenso, possíveis surpresas e janelas de atenção antes/depois dos eventos **com prioridade editorial**. Esta prioridade não é previsão de volatilidade nem sinal de compra/venda.
- **Agenda da semana:** linhas expansíveis com dia, hora BRT, país, indicador, consenso e anterior, mais cenários condicionais acima/abaixo. Quando o teto de apresentação reduz a lista, ela é rotulada **parcial**; isso não invalida os eventos de hoje que tenham sido recebidos integralmente.
- Os quatro cards superiores mantêm a identidade visual aprovada: **Cenário macro** (quantidade de eventos, não tendência), **Bancos centrais** (contagem de eventos, não decisão verificada), **Geopolítica** e **Notícias** (sem feed verificado, não forçam leitura).
- Preservado catálogo de indicadores por EUA/Brasil/Europa/Ásia/G8. Catálogo é planejamento: não representa feed ativo em cada país.
- Surpresa numérica exibe diferença **na unidade do indicador**, não retorno financeiro nem "percentual de reação"; revisões não são declaradas confirmadas sem evidência específica.

## Critérios de falha segura

1. Sem fonte/horário, resposta velha ou de dia incorreto em Brasília: **INDISPONÍVEL**.
2. Resposta da API no limite de 1.000 eventos: bloqueia afirmação de cobertura completa.
3. Lista diária truncada: resumo diário bloqueado. Lista **semanal** truncada: diariamente válido permanece visível, semanal rotulado parcial.
4. Contagens contraditórias, item com hora inválida ou fora do intervalo: resumo rejeitado.
5. Sem consenso: surpresa não calculada. Notícias/geopolítica sem feed continuam sem leitura.
6. **Nenhuma execução de ordem, Worker AION, recomendação de entrada ou compra de feed**.

## Testes

- Laboratório AM12: **47/47 testes locais PASS**, incluindo contratos anteriores do Trader, calendário e 12 novos cenários do Painel Mestre. O teste visual sintetizou eventos com selo explícito `EXEMPLO FICTÍCIO · LAB`, sem apresentar dados sintéticos como reais.
- GitHub Actions da PR #1803: verificar estado final de Quality/Browser/Security antes de qualquer aprovação de promoção.

## Dependências para operação integral e definição de "concluído"

- Confirmar **entitlement e franquia disponíveis** na EODHD para o endpoint Economic Events, sem expor token e sem assumir dados universais ou tempo real.
- Verificar amostras reais de CPI/PCE/NFP/BCB, países e escalas, horários oficiais, atrasos, eventos revisados e comportamento no vencimento do cache.
- Habilitar — apenas depois de aprovação e estudo de custo — um agendador **independente do Worker do AION** caso a necessidade seja atualizar mesmo com o site fechado. No estado atual, a coleta é feita sob demanda e limitada por cache.
- Escolher armazenamento durável, com RBAC e trilha de auditoria, para consenso manual compartilhado, caso o proprietário aprove. O atual `session_state` é explicitamente provisório.
- Fontes e metodologias de microeconomia, geopolítica e notícias precisam de contratos próprios antes de deixar o estado `SEM FEED VERIFICADO`.
- Validar produção autenticada, desempenho no Render de 512 MiB, teste móvel e aceite humano antes de merge/deploy.

**Não declarar a integração externa pronta apenas porque os testes com fixtures passaram.**
