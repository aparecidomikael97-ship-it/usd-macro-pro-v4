# AtlasQuant Trader — Contrato de duas testemunhas Ed25519 (LAB)

**Checkpoint 04/11/2026 — P1/P2 do Trader:** fonte, hora e mudança do
calendário devem ser rastreáveis antes de explicar força/fraqueza das
moedas USD/EUR/GBP/JPY/CHF/AUD/CAD/NZD e seus 28 pares.

## Escopo efetivamente implementado

O arquivo `atlasquant_trader_calendar_witness_signatures_lab.py` valida,
**offline**, duas assinaturas Ed25519 matemáticas sobre um mesmo pacote
canônico contendo:

- A cadeia SHA-256 recalculada dos bytes documentais fornecidos.
- Número de documentos e mudanças documentais declaradas no calendário.
- Número de janelas de captura **alegadas**, não comprovadas.
- Um desafio de 128 bits em hexadecimal e o instante UTC da emissão.
- A data UTC da avaliação, vinculando a prova a uma execução específica.

São exigidos **dois identificadores, papéis e chaves públicas distintos**:
observador da captura e revisor independente declarado. A assinatura é
verificada pela biblioteca `cryptography` (dependência existente no projeto),
sem implementar criptografia própria. O desafio expira em até 15 minutos.

O contrato rejeita chave duplicada, assinatura alterada, troca de conteúdo,
troca de nonce, desafio vencido, papéis incompatíveis, ausência de documentos,
relógio incompatível e campos extras tentando declarar uma aprovação.

## Limite essencial — nunca confundir matemática com identidade

As chaves públicas são fornecidas ao verificador por configuração externa.
O LAB **não conhece uma autoridade independente de confiança** e, portanto,
**não** comprova quem realmente controla cada chave. Não há serviço de
coleta, assinatura, registro de nonce consumido ou registro de terceiros.
Mesmo quando a checagem matemática passa:

- `signature_math_verified = true`;
- `independent_signer_identities_verified = false`;
- `official_publisher_origin_verified = false`;
- `tls_custody_verified = false`;
- `witnessed_external_timestamp_verified = false`;
- `replay_prevention_operational = false`;
- `source_data_real_time_verified = false`;
- `three_daily_updates_verified = false`;
- `publishable = false` e `trade_authorized = false`.

Uma assinatura válida de duas chaves inventadas pelo mesmo chamador **não
é custódia independente**. O módulo recusa qualquer promoção automática do
resultado a notícia em tempo real ou a viés do Forex. Tampouco foi
alterada a função de verificação do núcleo AION.

## Verificação e política de custos

```bash
python -m unittest discover -s . -p 'test_atlasquant_trader_*lab.py' -q
```

**233 testes locais aprovados, zero FAIL/ERROR**, incluindo 13 novos que
utilizam exclusivamente chaves geradas em memória. Essas chaves sintéticas
não são credenciais de produção e não foram persistidas.

Nenhum job 3×/dia foi ativado; sem HTTP, Worker, Render, cobrança, ordem,
merge, deploy ou alteração da aplicação publicada. PR #1803 segue em DRAFT
com conflito em relação à main; testes remotos ainda não confirmados.

**Próximo bloqueio a resolver, futuramente e com autorização própria:**
identificação independente dos observadores, chaves públicas aprovadas
fora do payload, provas originais do transporte TLS/órgão oficial,
custódia externa imutável e prevenção persistente de replay. Só então se
pode começar a avaliar a prova de origem e o efeito real sobre o câmbio.

Referência técnica do algoritmo:
https://cryptography.io/en/stable/hazmat/primitives/asymmetric/ed25519/
