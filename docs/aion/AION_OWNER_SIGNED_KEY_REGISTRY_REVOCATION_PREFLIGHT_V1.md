# AION Owner Signed Key Registry and Revocation Preflight V1

**08/10/2026 — offline CI / Draft / chaves sintéticas. Não é enrollment real ou autenticação de produção.**

## Objetivo

As PRs #1079, #1081 e #1082 validam prova assinada, sessão/dispositivo e intenção exata do comando. A confiança real depende de obter a chave pública do proprietário e seus dispositivos por fonte **independente do próprio pedido**. Esta etapa propõe verificação criptográfica de um registro assinado pela raiz que modela inscrição, troca e revogação de chaves/dispositivos, sem realizar inscrições no PC.

## Protocolo

- Snapshot JSON estrito até 16 KiB, campos fechados, sem chaves duplicadas, identidades de registry/subject/issuer e epoch inteiro positivo.
- Histórico sequencial de chaves públicas Ed25519 com identificador, epoch de entrada, revogação e vínculo ao predecessor. No máximo uma chave do proprietário ativa.
- Lista de dispositivos identificados por ID e SHA-256 de binding. Rejeitar duplicação, dispositivos não inscritos ou revogados.
- Assinatura destacada Ed25519 de raiz sobre JSON canônico com domínio próprio e validade limitada a 90 dias.
- A **chave pública raiz e seu fingerprint esperado** devem ser cadastrados e recuperados **por canal confiável separado**, nunca fornecidos pelo navegador como fonte de autoridade.
- O **epoch mínimo confiável** deve vir de um contador monotônico protegido externo ao módulo. Se o host aceitar um mínimo controlado pelo atacante, não haverá proteção verdadeira contra rollback.
- O tempo, registro esperado, subject, issuer, device ID e device digest também devem ser derivados pelo host autenticado, nunca da solicitação do browser.

O estado positivo SIGNED_REGISTRY_VERIFIED_FOR_HOST_REVIEW é apenas pré-verificação técnica. A chave pública ativa retornada é **exclusivamente host-internal** e não pode ser tratada como autoridade por um cliente. Flags de autenticação real e de execução/compra/deploy permanecem falsas.

## Limites técnicos

1. **Sem enrollment ou revogação real**: os casos de troca, revogação e perda de dispositivo são snapshots artificiais assinados por chaves efêmeras do runner CI.
2. **Sem raiz de confiança real**: a raiz dos testes também é fictícia. Um atacante capaz de mudar simultaneamente pin e chave não é bloqueado por esta camada.
3. **Sem antirrollback real**: passar um epoch mínimo não equivale a um contador monotônico seguro. Restaurar snapshot e epoch mínimo antigos contorna a propriedade; armazenamento antifraude, isolamento, backup e recuperação precisam ser projetados.
4. **Sem ligação a host de produção**: o módulo não comprova sessão autenticada, Windows Hello/FIDO2, assinatura pelo dono, proteção de arquivo e ACL, CSRF/XSS ou continuidade PC/celular.
5. Não liberar métodos anteriores de #1079/#1081/#1082 como endpoint público que burle a cadeia de verificação da raiz. Integração e verificação E2E permanecem bloqueadas.

## Critérios de aceitação deste bloco

36 testes adversariais independentes mais subtestes em Windows/Linux: raiz falsa, pin divergente, assinatura adulterada, chave pública trocada, histórico de rotação inválido, duas chaves ativas, chaves repetidas, dispositivo revogado, epoch antigo, snapshot expirado/futuro, campos desconhecidos, JSON duplicado, entradas enormes, Base64 inválido e tipos errados. Nenhum segredo real ou arquivos do usuário.

**Revisão futura necessária:** cadastro da chave real, custódia de raiz, armazenamento durável/antirrollback, revogação distribuída, proteção de sessões e ligação obrigatória ao guard #1082 no host real. Todas as PRs seguem Draft, sem merge, deploy, Worker, Render, alteração do PC ou novos gastos. Limite provisório R$200/mês preservado.
