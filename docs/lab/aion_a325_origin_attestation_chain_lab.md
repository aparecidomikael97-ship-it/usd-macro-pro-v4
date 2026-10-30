# A325 — Origem de comprovantes: assinatura de entrega + declaração assinada de identidade (LAB)

**HARD NO-GO · ZERO_AUTO_RESEND · 0/6 P0 homologadas · sem merge, Worker, deploy, execução, efeito de provedor ou novos serviços pagos.**

## Avanço concreto sobre A324

A324 (#1776) concluiu a bateria no Ubuntu/Windows com **516 testes por plataforma sem falhas inesperadas**. O recibo de transporte incluía apenas digest SHA-256 e identidade declarada; faltava comprovação criptográfica de que o custodiante que assinou o checkpoint também assinou o recibo de entrega, e de que alguma autoridade endossou a associação entre identidade e chave pública.

A325 acrescenta duas verificações criptográficas **matemáticas**, sem afirmar origem externa real:

1. Para cada um de **dois custodiantes distintos**, exige uma assinatura Ed25519 pelo signatário A321 do **recibo integral A324**, em domínio exclusivo `ATLASQUANT_AION_A325_DELIVERY_RECEIPT_LAB_V1`.
2. Exige uma **atestado de origem** assinado por um emissor diferente do custodiante, conectando: ID do emissor, ID do custodiante, chave pública A321, digest do checkpoint A321 **incluindo a assinatura**, digest completo do recibo de entrega, geração, época de incidente, nonce e janela temporal. Usa o domínio `ATLASQUANT_AION_A325_ORIGIN_ATTESTATION_LAB_V1`.
3. Exige **dois emissores distintos**, com chaves públicas distintas das duas chaves A321. As raízes emissoras são um mapa de *pins declarado pelo chamador*, **não** obtido de fonte externa independente.
4. Confere assinatura dos dois emissores, assinatura dos dois custodiante(s), identidade/key binding, digest dos documentos, geração/época, nonce e datas; recusa duplicatas, pin repetido, pin igual à chave do custodiante, assinatura alterada, atestado antigo/futuro e campos extras.
5. Após os quatro testes matemáticos, **reexecuta a triagem A324** (que reexecuta A323/A322/A321/A320/A319 e lê SQLite sintético somente leitura). A325 não aceita um campo `"PASS"` fornecido pelo usuário nem autoriza restauração.
6. Um incidente reaberto ou operação diferente de `VERIFY_ONLY` é negado antes de qualquer verificação de provas.

Status possíveis: `LAB_ORIGIN_MISSING_HOLD`, `LAB_ORIGIN_QUORUM_VETO`, `LAB_DOWNSTREAM_EVIDENCE_HOLD`, `LAB_ORIGIN_PROCEDURAL_HOLD` ou `LAB_ORIGIN_SIGNATURES_MATCH_STILL_NOT_INDEPENDENT`.

**Nenhum resultado constitui GO**. Todos declaram `origin_pins_independently_provisioned=False`, `issuer_identity_independently_authenticated=False`, `delivery_channel_independently_authenticated=False`, `off_host_immutable_head_verified=False`, `provider_ack_authenticated=False`, `can_restore=False`, `can_resend=False`, `can_resume=False`, `can_auto_retry=False`, `automatic_retries=0`, `zero_auto_resend=True`, `hard_no_go=True`, `p0_homologated=0`.

## Contraprovas essenciais

- Um recibo cuja assinatura A321 está correta pode ainda ser fraudulento se o **pin de origem for autodeclarado**. Da mesma forma, dois emissores com duas chaves distintas podem ser controlados pelo mesmo administrador.
- Trocar a chave pública pinada de um emissor falha **enquanto o pin antigo permanecer conhecido**. Se o host puder substituir *todas as referências*, refazer atestados e assinaturas, a matemática passará novamente, e seguirá HARD NO-GO.
- É possível reescrever inteiramente o estado SQLite sintético, manifesto, gênese, high-water e recibos de teste e assinar tudo novamente no próprio host; a A325 testa expressamente essa falsificação, sem chamar o resultado de custódia externa.
- Datas e nonce são fornecidos pelo mesmo chamador. Sua consistência não prova relógio confiável nem desafio originado fora do host.
- **Assinaturas do custodiante e de um emissor não equivalem a ACK do provedor**, não resolvem COMMIT incerto e não autorizam um reenvio real.

## Validação e isolamento

`python -m unittest -v labs.test_a325_origin_attestation_chain_lab`

São **35 testes A325** com chaves Ed25519 sintéticas, mais as regressões A324/A323/A322/A321/A320/A319/A318/A317/A316/A315/A314/A313/A312/A311/A310/A309/A246/A247/A292/A293/A299 nos runners Ubuntu e Windows. Apenas fixtures SQLite descartáveis e leitura. Não há alteração no `aion_chat/store.py` nem no Worker.

**Para fechar P0-3/P0-4, ainda serão necessárias** fontes de pins de emissor pré-autenticadas fora do host, identidade e custódia independentes, revogação/rotação antirollback, relógio/desafio externos, cabeças imutáveis obtidas de autoridades independentes, vínculo à intenção e ACK de resultado externo. Nenhum desses requisitos foi homologado nesta etapa.
