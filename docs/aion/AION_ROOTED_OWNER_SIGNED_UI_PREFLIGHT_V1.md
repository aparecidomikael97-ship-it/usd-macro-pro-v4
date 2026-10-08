# AION — Rooted Owner UI Signed Preflight V1

**08/10/2026: Draft, CI sintético, NÃO é autenticação real nem integração com PC/celular.**

## Objetivo

Conectar a #1083 (registro de chaves e revogação assinado pela raiz), #1082 (assinatura de intenção e comando exato), #1081 (prova de sessão) e #1078 (roteador interno). Não aceitar que chave pública enviada junto à solicitação constitua autorização HUMAN_OWNER.

## Ordem de validação

1. Um FUTURO host autenticado e confiável deverá construir HostEvidence com: raiz pública e fingerprint pinados por canal separado, ID de registro, subject, issuer, audience, dispositivo cadastrado, digest da sessão REAL, relógio e mínimo epoch protegido contra rollback. Esta PR **não fornece esse host**.
2. #1083 valida assinatura do registro, raiz pinada, epoch mínimo, período, chave ativa e dispositivo não revogado.
3. Somente a partir do registro **assinado** a aplicação deriva o pin da chave ativa do proprietário. Nunca derivar autoridade do pin apresentado pelo cliente.
4. #1079 verifica que a prova do proprietário corresponde ao subject, issuer, audience, fingerprint da chave, sessão e dispositivo esperados.
5. #1082 exige assinatura distinta sobre o texto **exato** do comando e seu escopo restrito, nonce, prova, digests e timestamps.
6. A navegação de #1078 pode apenas SOLICITAR abrir as áreas internas: AtlasQuant, Trader, Negócios, Investimentos e AION. O modo saudação apenas prepara texto.

## Bloqueios esperados

- Raiz falsificada, alteração em documento assinado, troca de chave, assinatura de pessoa não autorizada.
- Dispositivo não cadastrado, revogado, device binding divergente.
- Dono anterior após rotação de chave e revogação, snapshot com epoch inferior ao mínimo.
- Sessão divergente, subject ou issuer diferente, ADMIN delegado, assinatura de intenção forjada.
- Troca do comando original, replay, assinatura expirada, comando de greeting usado em navegação.
- Apps externos, comandos compostos, execução de trade, pagamentos, deploy, acesso OS: bloqueados.

## Lacunas graves que continuam sem resolução de produção

- HostEvidence é só um contêiner. Um atacante que escolher seus parâmetros pode forjar a âncora raiz. O navegador NÃO pode passar valores host-side.
- Não existem inscrição de chave real, custódia de raiz, Windows Hello/FIDO2, assinatura com presença humana, identificação física robusta do dispositivo ou sessão autenticada real neste módulo.
- Minimum epoch não é contador antirrollback: restaurar simultaneamente snapshot e mínimo antigos contornaria revogação. Não há dispositivo local, armazenamento protegido ou sincronização PC/celular.
- A proteção SQLite contra replay precisa de ACL, backup, antirrollback e recuperação; não foi instalado ou ativado banco no computador do usuário.
- O digest de sessão continua dependente da origem do host. Não é comprovado por este código.
- O retorno INTERNAL_NAVIGATION_REQUESTED não comprova navegação realmente aberta. Sem wakeword, áudio, câmera ou automação Windows.
- Não conectar métodos antigos diretamente à UI ignorando esta cadeia; auditar o wiring real para evitar bypass.
- Um erro interno no roteador pode mutar session_state antes de falhar; esta etapa não implementa transação de estado nem rollback.

## CI e próximos gates

36 testes adversariais independentes e subtestes Windows/Linux com chaves de raiz, dono e dispositivos temporários, banco nonce em diretório temporário do runner. Dependências de cryptography e streamlit instaladas SOMENTE no runner GitHub. CI verde não certifica host real.

Draft encadeada em #1083. Sem merge, deploy, Render, Worker, instalação no computador, gasto novo, alteração do Core V1 ou main. Teto provisório de R$200/mês intacto. Integração real requer revisão de segurança e autorização explícita.
