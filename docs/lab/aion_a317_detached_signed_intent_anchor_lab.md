# A317 — compromisso de intenção assinado e destacado do SQLite (LAB)

**HARD NO-GO · ZERO_AUTO_RESEND · 0/6 P0 homologadas · nenhum custo novo ou serviço ativo.**

## O que já foi comprovado

A316 encerrou **29 de 29 workflows com sucesso** no GitHub. O `SQLiteChatStore` sintético já registra recibo e mensagem em um único COMMIT, compara dois vestígios internos da intenção e nega reenvio quando somente um deles foi apagado. O contraexemplo remanescente da A316 é importante: quem controla o computador consegue apagar ou adulterar **ambos os vestígios**.

## Objetivo da A317

Testar a comparação com um **compromisso matematicamente assinado, destacado da consulta atual**. A A317 não produz recibos externos autênticos e **não usa nenhuma autoridade ou serviço fora do GitHub**; as chaves Ed25519 dos testes são geradas no mesmo runner, propositalmente sem independência operacional.

O arquivo `labs/a317_detached_signed_intent_anchor_lab.py` implementa duas operações de pesquisa:

- `read_fixture_snapshot(db_path, scope, intent_id)`: consulta por `mode=ro` um banco SQLite *somente sintético* num diretório marcado `a315-lab-*`. Exige recibo e mensagem vinculados ao mesmo `intent_id`, escopo, mensagem, sequência e metadados A316. Calcula SHA-256 canônico do recibo e dos bytes JSON da mensagem. Nenhuma operação DML, exclusão ou recuperação.
- `assess_detached_intent_anchor(...)`: valida estrutura estrita, assinatura Ed25519, propósito específico dos bytes assinados, chave pública informada, `intent_id`, escopo, `incident_epoch`, desafio `nonce`, sequência e cabeça anterior da cadeia, janela de tempo e igualdade do snapshot com o compromisso assinado.

O contrato retorna uma destas categorias:

- `LAB_SNAPSHOT_MATCH_NO_EXTERNAL_AUTHORITY`: assinatura e snapshot local conferem matematicamente, **mas não existe autenticação externa**. Sempre HARD NO-GO.
- `LAB_LOCAL_DIVERGENCE_VETO`: recibo removido, mensagem removida, rastros inconsistentes ou snapshot diferente. Nenhum replay autorizado.
- `LAB_WITNESS_INVALID_VETO`: estrutura, chave, assinatura, nonce, época, tempo ou sequência/cabeça incompatível. Nenhuma recuperação ou reenvio autorizado.

Todos os resultados informam, incondicionalmente:
`independently_pinned_witness_identity=False`,
`off_host_head_authenticated=False`,
`external_custody_proven=False`, `trusted_clock_proven=False`,
`provider_effect_verified=False`,
`semantic_exactly_once_proven=False`,
`can_resume=False`, `can_resend=False`, `can_auto_retry=False`,
`can_authorize_real_effect=False`, `automatic_retries=0`,
`hard_no_go=True`, `zero_auto_resend=True`, `p0_homologated=0`.

## Cenários adversariais

A suíte A317 inclui verificação válida sem promoção operacional, eliminação do recibo, eliminação conjunta de mensagem e recibo, adulteração do conteúdo, troca do digest local, assinatura alterada, chave errada, escopo/tenant diferente, nonce reutilizado, tempo expirado/futuro, época alterada, sequência/cabeça anterior incompatível, campos indevidos, estruturas inválidas e caminho fora do LAB.

A contraprova mais importante recria uma **nova chave Ed25519 dentro do mesmo host**, altera o conteúdo local e assina um novo compromisso; passando a nova chave como se fosse a fonte confiável, o verificador encontra consistência matemática. Isso **não** equivale a custódia independente e confirma a necessidade de pinagem/autenticidade externa **real**, com cabeça antirollback durável e emitente independente.

## Não alegar segurança inexistente

Uma chave gerada no GitHub ou no próprio AION **não é uma testemunha externa independente**. A cadeia de hashes, a cabeça anterior, o relógio e o desafio são valores fornecidos ao verificador; sem outra raiz de confiança, todos podem ser substituídos juntamente com a base SQLite. O A317 tampouco produz ou autentica um ACK de efeito de provedor.

Não houve solicitação de credenciais, banco de cliente, contrato de serviço, deploy, Worker, restauração, ordem, efeito externo ou cobrança. A PR permanece em rascunho, empilhada sobre a A316, sem merge.

## Testes

```sh
python -m unittest -v labs.test_a317_detached_signed_intent_anchor_lab
```

CI Ubuntu e Windows Python 3.12 e biblioteca `cryptography==46.0.4` (dependência de testes já usada na A308), mais regressões A316/A315/A314/A313/A312/A311/A310/A309/A246/A247/A292/A293/A299. Na matriz Linux exigir a prova real de UID/socket A313/A314; Windows não recebe falsa atestação POSIX.

**Próxima etapa real da P0-3:** comprovar existência, revogação e custódia independente de uma testemunha de intenção *fora do controle do host*, pinning de raiz de confiança com atualização autorizada, relógio/nonce/cabeça antirollback próprios e vínculo de resultado externo. Nenhum desses requisitos foi homologado aqui.
