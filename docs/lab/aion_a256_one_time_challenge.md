# A256 — Ciclo de vida do desafio de uso único (LAB; P0-3/P0-4)

**HARD NO-GO · 0/6 P0 homologadas · sem merge, Worker, deploy, serviço, credenciais, custos ou efeitos reais.**

## Lacuna de A255
A255 verifica um `expected_challenge` passado pelo chamador. Mesmo com duas assinaturas corretas, A255 não prova que o desafio de 256 bits foi *efetivamente emitido* para uma determinada tentativa nem que foi usado uma única vez. Um chamador hostil pode repetir o mesmo desafio ou inventar sua origem. A256 trabalha **apenas no mecanismo local de emissão/consumo**, sem reivindicar origem independente.

## Contrato estrito da A256
- `SyntheticOneTimeChallengeLab.begin(decision, origin_envelope)` usa `secrets.token_hex(32)` sob mutex e registra o desafio ligado ao hash do envelope A254, ID do evento, escopo, ação, agregado e hash do payload. `intent_ref` técnico não define a identidade do evento.
- `review(..., challenge=...)` exige desafio previamente emitido e **marca-o consumido atomicamente antes de qualquer validação da resposta**. Falha de assinatura, envelope trocado, ACK perdido, expiração, alteração de evento ou retorno duplicado **não reabre nem reemite** o desafio naquela instância.
- Dois eventos distintos com o mesmo payload podem ter desafios diferentes. Repetir o mesmo ID de evento, inclusive mudando `intent_ref`, é vetado localmente. Falha de RNG por colisão não substitui desafio já registrado.
- A expiração padrão é 60 segundos, configurável de 1 a 90. O relógio é **injetado pelo host**; ele não é um relógio confiável externo.
- A verificação criptográfica continua no A254/A255 após o consumo local. `begin` valida estrutura e vínculo declarado, **não autentica a assinatura de origem ao emitir o desafio**; evento forjado pode causar indisponibilidade local (DoS).
- **Todos os caminhos retornam `authorizes_send=False`**, `independent_*_proven=False`, `p0_homologated=0`. Não há adapter real, e o teste de integração exige Outbox `UNCERTAIN` + 0 sends.

## Testes A256
18 casos: emissão e duas assinaturas sintéticas; dois eventos distintos com mesmo conteúdo; repetição com novo request-ID; assinatura errada da testemunha; evento trocado; ACK perdido; resposta atrasada; relógio retrocedendo; nonce colidido; entrada malformada; desafio não emitido; desafio incorreto no recibo; alterações semânticas; 64 entregas concorrentes do mesmo recibo (no máximo um formato aceito); 0 `adapter.send`; replay de desafio consumido. **Duas XFAIL explícitas**: (17) reboot/rollback faz esquecer histórico; (18) host repina as duas chaves de atacante, que passam como formato válido.

Executar A256 com A255/A254/A243 e regressões A253–A233 em Ubuntu e Windows. CI verde de laboratório não autentica a origem nem certifica antirollback.

## Evidências ainda indispensáveis
1. Origem real de eventos com IDs imutáveis e contrato de negócio auditado fora do host do AION.
2. Emissão/reserva monotônica e **durável fora da autoridade do host**, inclusive após perda de ACK, reinício do solicitante e rollback da testemunha.
3. Chaves cuja procedência, rotação e revogação sejam verificáveis independentemente. **Duas chaves locais distintas não são dois controladores independentes.**
4. Identidade HUMAN_OWNER, efeito final/recibo do provedor e VFS/FD nativo SQLite autenticados em processos próprios.

Nenhuma infraestrutura externa foi provisionada; nenhum contrato admite `trusted=true`, novo hash local ou assinatura autogerada como prova independente. **UNCERTAIN=ZERO_AUTO_RESEND.**

Produto: AION completo, Trader prioritário; motor econômico sob demanda com Investimentos em fase posterior; Negócios congelada/preservada.
