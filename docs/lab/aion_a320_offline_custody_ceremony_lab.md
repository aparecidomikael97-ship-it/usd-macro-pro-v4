# A320 — Dossiê de custódia independente: procedimento offline e testes de falsificação (LAB)

**HARD NO-GO · ZERO_AUTO_RESEND · 0/6 P0 homologadas · sem merge, Worker, deploy, ordens, provedor ou custos novos.**

## Contexto

A319 validou a continuidade matemática de rotação das raízes Ed25519 no Ubuntu e no Windows (286 testes em cada ambiente), mas **o hash inicial pinado, o relógio, as revogações e o histórico ainda eram fornecidos pelo chamador**. Se quem controla o host gerar quatro chaves novas e fabricar os recibos, a matemática pode passar. A320 define um formato de **dossiê de cerimônia** e expõe esse risco de forma verificável, sem instalar nenhuma fonte externa.

## Contrato LAB

Arquivo: `labs/a320_offline_custody_ceremony_lab.py`.

A função `verify_offline_custody_ceremony` recebe um `transition_request` completo do A319, um `offline_precommit`, exatamente dois `custodian_packets` e as duas chaves públicas declaradas. **Primeiro reexecuta a A319**, exigindo a rotação válida de 2 chaves antigas e 2 novas; o verificador não aceita um relatório `"PASS"` autoafirmado.

O `offline_precommit` referencia um único `ceremony_id`, SHA-256 dos manifestos anterior e candidato, geração, época de incidente, sequência/cabeça do histórico, nonce e horário **declarado** anterior à emissão da rotação. O dossiê exige dois recibos assinados Ed25519 com o mesmo precommit e um `witnessed_at` entre o precommit e a validade da rotação. Os recibos precisam declarar:

- Identificadores diferentes de custodiante, domínio de custódia, canal de entrega, dispositivo/mídia e digest do documento testemunhado.
- Chaves públicas diferentes e assinaturas válidas; duas cópias do mesmo documento ou a mesma chave sob dois nomes são recusadas.
- `decision=HOLD_ONLY` com assinatura em domínio criptográfico exclusivo A320. Nenhum campo de GO ou autorização pode ser inserido.

Possíveis resultados: `LAB_CUSTODY_CEREMONY_VETO` diante de incongruência; `LAB_TWO_CUSTODY_PACKETS_COHERENT_BUT_UNVERIFIED` quando tudo está **matematicamente coerente**, mas a origem **não foi autenticada por uma autoridade independente**.

Todos os retornos reportam `physical_separation_independently_verified=False`, `independent_custodian_identity_authenticated=False`, `external_precommit_authenticated=False`, `trusted_receipt_delivery_verified=False`, `custodian_keys_independently_pinned=False`, `external_high_water_proven=False`, `can_authorize_real_effect=False`, `can_resume=False`, `can_resend=False`, `automatic_retries=0`, `hard_no_go=True`, `p0_homologated=0`. Isso impede tratar uma simulação como autorização.

## A cerimônia que seria necessária no mundo real (NÃO realizada)

**Preparação.** O proprietário selecionaria pelo menos dois custodiantes com controle verdadeiramente separado das chaves e do histórico. Antes de confiar em alguma assinatura, teria que conferir a identidade de cada custodiante e vincular sua chave pública a um registro **pré-existente**, mediante canal fora do controle do computador/conta do AION. Um endereço de e-mail ou rótulo criado pelo próprio host não basta.

**Precompromisso.** O registro inicial deveria conter hash do manifesto anterior, chaves públicas autenticadas, geração, época de incidente, nonce e cabeça do histórico. Ele teria que ser **retido por uma fonte não regravável pelo host AION**, com origem, data e método de conferência documentados. Prints, PDFs ou dois diretórios no mesmo computador não são prova antirollback.

**Testemunhas.** Cada custodiante verificaria independentemente o documento recebido, a cabeça histórica, o estado da revogação e o desafio da cerimônia; cada um produziria assinatura e recibo pelo canal previamente autenticado. Troca ou perda de um custodiante deixa o AION em HOLD, não autoriza reset local.

**Reconciliação.** Antes de uma futura operação, a execução precisaria conferir a cabeça e os recibos realmente mantidos fora do host, a autoridade vigente, a intenção semântica e o ACK do provedor. A320 não realiza nenhuma dessas leituras externas. Um ritual humano de baixo custo pode ajudar a testar o procedimento, mas não substitui uma fonte independente e durável na hora da execução.

**Custos.** Não foi contratado serviço, hardware de segurança, HSM, storage, API ou conta externa. Pesquisar alternativas gratuitas ou orçar fornecedores será uma decisão posterior, com autorização explícita antes de cobranças.

## Contraprovas importantes

1. Duas assinaturas geradas no **mesmo processo Python** com supostos canais e dispositivos diferentes passam matematicamente. Isso **não comprova dois custodiantes**. O teste registra `...COHERENT_BUT_UNVERIFIED`, nunca GO.
2. O host pode reconstruir a geração inicial, a cabeça e o precommit e assinar novos pacotes. Sem pin confiável anterior, até uma cadeia inteira pode ser trocada.
3. Chaves, documento, hash da rotação, sequência, assinatura e nonce trocados **sem recomputar tudo** são recusados, mas isso não prova a origem das referências originais.
4. O contrato não autentica timestamps, canais externos, identidade de pessoas, recibos de efeito de provedor, VFS/FD do SQLite ou custódia imutável. **As seis P0 seguem abertas.**

## Validação

```sh
python -m unittest -v labs.test_a320_offline_custody_ceremony_lab
```

Trinta testes novos, mais regressões A319/A318/A317/A316/A315/A314/A313/A312/A311/A310/A309/A246/A247/A292/A293/A299 em Ubuntu e Windows. Nenhuma alteração em `aion_chat/store.py`. Os dados e chaves dos testes são inteiramente sintéticos. A PR é rascunho empilhada sobre A319.

**Próximo bloqueio real:** uma decisão independente sobre quem poderá custodiar as raízes, como estabelecer o primeiro pin sem TOFU no mesmo host e como consultar um high-water imutável fora do AION. Só depois disso caberá discutir uma homologação P0-3/P0-4.
