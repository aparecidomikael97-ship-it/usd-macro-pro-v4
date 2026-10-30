# A319 — Continuidade de raiz de confiança e instalação externa (somente LAB)

**Status:** HARD NO-GO · ZERO_AUTO_RESEND · 0/6 P0 homologadas · sem Worker, merge, deploy, operações reais ou novas contratações.

## Por que a A319 existe

A318 validou as duas assinaturas Ed25519 matemáticas no Ubuntu e Windows (254 testes executados em cada plataforma, sem falhas inesperadas). Mesmo assim, o próprio computador ainda poderia gerar chaves novas, substituir a lista de chaves confiáveis e assinar provas fraudulentas. **A A319 não repete essa falsa certificação:** distingue a continuidade matemática entre gerações de uma raiz e a **proveniência independente do registro de chaves antigo**.

## Contrato implementado

`labs/a319_offline_root_continuity_lab.py` recebe:

- `previous_manifest`: registro sintético da geração anterior com exatamente duas chaves públicas distintas e revogações acumuladas.
- `pinned_previous_digest`: impressão digital SHA-256 que **deveria ter sido autenticada por um custodiante externo**, mas que no laboratório ainda é fornecida pelo chamador.
- `candidate_manifest`: geração imediatamente seguinte, **duas chaves novas**, nomes diferentes, revogação dos dois IDs antigos e preservação das revogações anteriores; sequência de high-water sem retrocesso, head hash preservado quando sequência não mudou, mesma época do incidente, nonce, validade e `decision=HOLD_ONLY`.
- `old_root_signatures`: **duas assinaturas** Ed25519 das chaves antigas, em domínio exclusivo de autorização de rotação.
- `new_root_signatures`: **duas assinaturas de posse** pelas chaves novas, em outro domínio exclusivo.
- `expected_nonce`, `expected_incident_epoch`, `observed_clock_epoch`: referências **não autenticadas** no LAB.

O verificador exige dois votos antigos e dois novos, exatamente por IDs autorizados, com assinaturas corretas, sem campos extras, geração consecutiva, links/digests, revogação acumulada, challenge e validade. A primeira instalação *sem registro anterior confiável* é sempre negada. Não há rotina para "recuperar" uma raiz perdida por autodeclaração.

**Saídas:** `LAB_MATH_CONTINUITY_VALID_NO_EXTERNAL_PIN` para matemática consistente, mas ainda sem autoridade operacional; `LAB_ROOT_TRANSITION_VETO` para qualquer falha. Ambas seguem `hard_no_go=True`, `zero_auto_resend=True`, `p0_homologated=0`, `can_resume=False`, `can_resend=False`, `can_authorize_real_effect=False`.

## O contraexemplo essencial

Um mesmo host pode criar quatro chaves sintéticas novas, fabricar um `previous_manifest`, calcular seu digest "pinado", assinar um sucessor e informar um relógio e uma cabeça de histórico convenientes. O laboratório demonstra que **todas as verificações criptográficas podem passar**. Isso não torna a raiz independente; o resultado segue explicitamente `out_of_band_reference_independently_authenticated=False`.

A A319 **não cria serviço externo nem testemunha real**. O processo local não consegue saber se a impressão digital da raiz anterior chegou por um canal independente ou foi criada pelo próprio operador.

## Como a raiz independente teria que ser obtida (não executado)

**Instalação inicial:** uma autoridade previamente escolhida pelo proprietário precisaria entregar um hash/manifesto de chaves por um canal independente do host que executa o AION. O AION deveria verificar esse vínculo com evidências que o próprio host não pudesse substituir. Duas chaves armazenadas em pastas diferentes do mesmo notebook não contam como raízes independentes.

**Rotação:** antigas testemunhas independentes aprovam o novo par, os novos custodiante(s) provam posse e ambos registram a nova geração e as revogações. Perda ou comprometimento de um custodiante deve deixar o sistema em HOLD até recuperação autorizada e auditável — não permitir reset unilateral.

**Histórico e ACK:** testemunhas externas também precisam preservar cabeça/seq antirollback, época de incidente, intenção semântica e eventual recibo de efeito do provedor, com verificação offline/online conforme o modelo operacional. Uma assinatura pré-fixada sem histórico independente **não resolve** P0-3 ou P0-4.

**Alternativas sem nova cobrança imediata:** documentação e simulação offline com duas custódias humanas/ambientes realmente distintos podem demonstrar procedimentos de cerimônia, mas **não atendem sozinhas à necessidade de confirmação externa durável e automática no momento de um efeito real**. Um serviço externo/hardware de confiança só pode ser estudado e cotado depois de aprovação explícita; nenhum foi contratado ou integrado aqui.

## Critérios de verificação

A suíte `labs.test_a319_offline_root_continuity_lab` tem 32 testes: 2/2 assinaturas antigas e novas, chaves/IDs repetidos, geração, perda de revogações, high-water, época, nonce, expiração, campo de GO falso, primeiro bootstrap e contraprovas de pin/clock/head remintados pelo chamador.

GitHub Actions Ubuntu e Windows, regressões A318–A299, sem modificação em `aion_chat/store.py` e sem migração de dados.

**O próximo passo operacional requer uma decisão sobre custodiante independente e fonte autenticada do pin — sem isso nenhuma prova local pode fechar a P0-3.**
