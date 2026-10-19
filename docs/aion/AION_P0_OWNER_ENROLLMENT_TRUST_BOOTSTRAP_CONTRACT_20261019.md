# P0 HUMAN_OWNER — contrato de matrícula e raiz de confiança (LAB / proposta)

Data 2026-10-19. Este documento **não matricula pessoa, conta, chave, autenticador ou autoridade**. Não altera guardas de produção nem concede execução. HARD NO-GO mantido.

## Diagnóstico demonstrado
- V2.24 verifica assinatura Ed25519 sobre desafio e registro de chaves públicas fornecido a sua função. A função não prova, isoladamente, que o registro pertence ao proprietário real ou foi cadastrado em custódia independente.
- P0 predecessor: CI #39302729585 (75 casos distintos PASS em cada OS). Teste com chave sintética criada e cadastrada pelo próprio fixture passa autenticação criptográfica; isso NÃO prova matrícula real e nenhum caminho de ativação é autorizado.
- M71 replay de gate continua RED no validador original; M73 apenas diagnóstico de LAB; seis P0 continuam não homologados.

## Princípios obrigatórios da matrícula inicial
1. A matrícula NÃO pode ser autorizada por uma conta, arquivo, chave pública ou papel de usuário recém-fornecido por quem está solicitando cadastro. **Bootstrap de confiança exige confirmação humana fora do fluxo solicitado**.
2. O proprietário é quem controla a matrícula, por confirmação verificável fora de banda; uma sessão `ADMIN`, nome exibido, mensagem de chat, email ou GitHub GET não substituem essa prova.
3. A chave privada nunca pode ser enviada para chat, repositório, Render, pipeline CI, logs ou planilhas. Só a chave pública e seu hash podem integrar o registro autorizado.
4. Registrar identidade da credencial, escopo owner/tenant/workspace, tipo e política, desafio único, RP ID/origem se WebAuthn, contador/backup-state quando aplicável, data, expiração, estado ACTIVE/REVOKED/RECOVERY_PENDING, e identidade do custodiador real. Dados sensíveis mínimos.
5. Versionar políticas e manter histórico monotônico de revogação/rotação em custódia independente da aplicação. Recovery não pode ser executado pelo mesmo canal que perdeu a credencial.
6. Ações críticas exigem decisão por ação com challenge fresco e assinatura ligada à ação, separado da prova de controle de credencial; o fluxo V2.24->V2.25->V2.26 não pode ser pulado.
7. A ausência de qualquer dado de fonte independente, indisponibilidade ou incerteza = recusa. Um recibo de cadastro sem validação não altera o P0.

## Alternativas futuras (NÃO selecionadas nem configuradas)
- **WebAuthn/passkey** usando autenticador de plataforma (Windows Hello / telefone quando suportado), com verificador de origin + RP ID + challenge + assinatura + user verification + credencial previamente matriculada. Não é substituto direto da Ed25519 V2.24; requer camada/adaptador próprio e análise de credenciais sincronizadas versus hardware-bound, recuperação e acesso em dois dispositivos.
- **FIDO2 chave física** com política de atestação/custódia: compra não autorizada, não pressupor compatibilidade, não requerer agora.
- **Ed25519 existente**: continua útil para assinatura de decisões, desde que a chave pública seja matriculada por um canal independente e a chave privada esteja sob custódia controlada.
Não adquirir hardware, contratar assinatura ou conectar provedor sem aprovação específica do proprietário. Não perguntar por segredos/biometria em chat.

## Critérios verificáveis de encerramento do P0 (TODOS)
- [ ] Procedimento de bootstrap independente do solicitante aprovado pelo proprietário com prova objetiva e minimização de dados pessoais.
- [ ] Trust anchor publicamente verificável, com custódia e proteção contra troca por usuário/app/CI; revisão independente.
- [ ] Desafio de cadastro único, TTL, binding com conta/dispositivo/origem, revogação e recuperação segura; evidência independente da assinatura e vinculação.
- [ ] P0 nega autopreenchimento de `owner_identity_verified`, `biometric_verified`, `witness_verified`, `trusted`, etc; software não usa flags do próprio pedido como autoridade.
- [ ] Testes adversariais de troca de chave, cadastro fraudulento, cross-tenant, replay, reset, rollback, recovery, desconexão, revogação, multidevice e corrida.
- [ ] Ensaios físicos/ambiente real e Quality/Security integrais; nenhuma regressão de ZERO_AUTO_RESEND nem de travas do Worker.

## Escopo do laboratório seguinte
Criar um verificador **somente diagnóstico** de envelopes de matrícula com restrições estritas de formato e correspondência. Deve sempre produzir `BLOCKED` para matrícula operacional, inclusive se o envelope aparentar prova completa ou campos `verified=true`. O relatório diferencia falhas de formato de `INDEPENDENT_OWNER_CUSTODY_NOT_ESTABLISHED`. Nenhuma chave real, origem externa, rede, arquivo persistente ou assinatura é gerada pelo laboratório. Um resultado sintaticamente coerente não significa identificação do proprietário.

HARD NO-GO; 0/6 P0 homologados; Worker OFF, sem merge/deploy/gastos.
