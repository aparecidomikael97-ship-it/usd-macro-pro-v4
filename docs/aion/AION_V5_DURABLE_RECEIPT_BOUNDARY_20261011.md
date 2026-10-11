# AION P0 V5 — fronteira de admissão durável (referência offline)

**Data:** 11/10/2026. **Base:** PR #1220, `8a143ee40b9f6893845817d61b564ccc47611502`. **Estado:** FIRST INSTALL = HARD NO-GO.

Esta Draft implementa uma **primeira fronteira V5** em SQLite descartável. Ela NÃO cria witness real, matrícula de raiz, confiança externa nem integra o Worker.

## Contratos entregues

- `receipt_admission.py`: emite um nonce com consulta V4 fechada e vínculo ao escopo; exige verificação criptográfica de `verify_fresh_read_reference` sob `BEGIN IMMEDIATE`; consome nonce + registra recibo + avança floor e hash-chain no **mesmo commit**. Readback posterior é `mode=ro`, valida o evento causal e não libera nova admissão.
- `epoch_root_reference.py`: confere assinaturas antigas e novas em domínios distintos, escopo, incremento exato de epoch, incremento de geração, troca efetiva da chave e listas de revogação. O resultado é sempre matemática de fixtures, **não** uma decisão de matrícula ou autorização. Não persiste nem ativa rotação/epoch.
- Testes reais usam SQLite, arquivos descartáveis, concorrência, subprocesso e assinatura Ed25519 de chave somente em memória; o dossiê registra um teste negativo em que restauração total do banco volta a permitir admissão antiga.

## Segurança e limites

- No domínio local íntegro, nonce consumido permanece consumido entre reinícios. Reemissão, recibo duplicado, assinatura inválida, chave revogada, escopo diferente ou schema alterado são bloqueados.
- Uma resposta assinada anterior a uma floor mais nova é rejeitada pela função V4; o floor é armazenado localmente na V5. **Se o operador restaurar também o floor, a proteção deixa de existir.**
- Se um commit ou o readback produz resultado incerto, NÃO há retry automático e a saída não é autorização. ACK isolado não serve como prova externa.
- O ledger V5 é separado do ledger V3 para manter o experimento de admissão de recibos sem introduzir um novo writer no fluxo de autenticação produtiva.
- Cada aprovação simulada de transição raiz/epoch continua `owner_identity_verified=False`, `root_trust_verified=False`, `installer_authorized=False`.
- A V5 não resolve a independência institucional de chaves e nonces, trusted clock, WORM, quorum real, proveniência de revogação externa,跨-domain CAS real, revogação de raiz multiestágio, TPM/FIDO/Windows físico, isolamento B2B, LGPD ou orçamento integral. Eles permanecem para missões autorizadas posteriores.
- Nenhum arquivo de produto, Core V1, Worker, manifesto original, custos ou deploy foi modificado.

## Critérios de saída e próxima decisão

CI específica Windows/Linux, Quality global original Linux, compile e diff; relatar resultados reais na Draft. Não confundir testes de laboratório com avaliação de produção.

**As 20 evidências originais de instalação continuam BLOCKED.** Para continuar além da preparação offline, preparar experimento mínimo em Windows e testemunha externa com custódia independente, ambos com escopo e autorizações separadas.
