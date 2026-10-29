# A257 — Expiração por tempo decorrido e assinatura de origem antes do desafio (LAB)

**Estado: HARD NO-GO · 0/6 P0 homologadas · sem Worker/deploy/merge/serviços/custos/efeitos reais.**

## Falhas confirmadas no código A256

1. Quando `review(observed_at=None)`, a A256 usava `self._start` como horário observado. O desafio poderia continuar sendo tratado como dentro do TTL apesar de o tempo real decorrer.
2. `begin` só validava a forma e os campos da origem, sem verificar a assinatura Ed25519 **antes de consumir a identidade local**. Um envelope forjado com os campos corretos poderia reservar/desgastar o evento e criar uma falha de disponibilidade.

## Mudanças A257 (restritas ao ambiente LAB)

- Emissão e consumo observam o **relógio monotônico do processo** `time.monotonic()`, com injeção determinística em testes. Guardam `issued_tick` por desafio; review mede o intervalo real, com `observed_at` opcional apenas como **filtro adicional de recusa**. O horário opcional do chamador nunca substitui nem retrocede o tempo medido.
- `_tick_locked` rejeita valores negativos, não numéricos, NaN, infinito e retrocesso. Após regressão/falha do relógio, mantém falha sticky nesta instância; o desafio é consumido **antes** do cheque de relógio e não é reutilizado.
- `_verify_origin_before_issue` confere assinatura A254 Ed25519, chave/issuer fixados na instância, intervalo assinado e limite de duração antes de gerar ou reservar o desafio. Evento inválido não entra em `_events_seen`; evento válido e distinto pode prosseguir normalmente. Assinatura válida **não** comprova a proveniência independente das chaves.
- Tempo de referência dos LABs: instante UTC injetado + diferença monotônica observada desde o primeiro tick. Uma testemunha cujo intervalo assinado já expirou é recusada antes da revisão A255. Isto ainda é um relógio controlado pelo host, NÃO prova física de tempo externo.
- Sem mudar o contrato do Outbox: todos os resultados `authorizes_send=False`. `UNCERTAIN=ZERO_AUTO_RESEND` continua.

## Ensaios

15 testes A257: TTL vencido sem `observed_at`; resposta válida dentro do intervalo; recibo da testemunha vencido; tentativa de esconder TTL usando um horário antigo; assinatura de origem forjada antes de emitir; issuer/key-ID errados; evento assinado vencido/futuro; retrocesso de relógio e falha sticky; relógio inválido ou NaN; expiração na segunda emissão de evento; timestamp informado retrocedendo; dois eventos legítimos; integração Outbox com **0 envio**.

**XFAIL A257:** um host adversário que congela completamente o relógio de monotonicidade consegue simular ausência de tempo decorrido. Não existem medições independentes. Herdados: XFAIL A256 restart e repinagem de ambas chaves; XFAIL A255/A254/A243 testemunha sob host; XFAIL SQLite que depende do próprio host.

## Limites de confiança

Este patch não cria origem de evento autêntica, chaves verificáveis fora do host, testemunha externa monotônica, reserva durável independente, atestado do SQLite VFS/FD ou recibo de provedor. **P0 0/6** permanece. Um relógio monotônico do computador **não é uma fonte externa confiável**. Nenhuma ação operacional é liberada.

**HARD NO-GO.** Trader primeiro, Investimentos preparado e Negócios congelada/preservada. Sem novos serviços ou custo.
