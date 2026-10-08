# AION — Intenção criptográfica específica por comando V1

**08/10/2026. Implementação isolada em branch Draft. Sem merge, deploy, host real, microfone, Windows ou apps externos.**

## Lacuna de confiança fechada nesta etapa

Uma assinatura que comprova apenas "esta sessão pertence ao HUMAN_OWNER" (#1079) não autoriza, por si só, um comando específico. O adaptador experimental #1081 exigia assinatura de sessão e nonce novo, mas **não vinculava criptograficamente os bytes do comando**. Até revisão de toda esta cadeia, **não conectar a API de #1081 à entrada pública de nenhuma interface real.**

## Protocolo de duas assinaturas, dois domínios

1. Prova de sessão #1079: Ed25519, sessão, dispositivo, emissor, público-alvo, nonce e expiração de até 120 s.
2. Assinatura adicional da intenção, com domínio AION:OWNER_UI_SIGNED_INTENT:V1, para escopo exclusivo NAVIGATE_INTERNAL ou DISPLAY_GREETING.
3. JSON exato e canônico da intenção deve registrar: texto de comando **idêntico aos bytes assinados**, digest SHA-256 da mensagem completa da prova de sessão, nonce, timestamps, sessão, dispositivo, issuer e audience fixados pelo host confiável.
4. O guard valida formato, pin, contexto, assinatura e janela de tempo **antes de consumir o nonce**. Comandos alterados, escopos trocados, tokens emprestados, assinaturas inválidas ou chaves não inscritas são bloqueados sem mutação de navegação.
5. A navegação chega somente à ponte de destinos internos permitidos, com uma instrução única. Apps externos, instruções compostas e execução do SO são bloqueados.
6. O retorno confirma apenas **solicitação** de navegação. Não atesta abertura de tela, voz, microfone nem autorização de execução.

## Segurança que esta PR NÃO comprova

- Chaves usadas são descartáveis e geradas nos testes. Nenhuma inscrição, recuperação, custódia, revogação, rotação ou vínculo de chave real do proprietário foi feita.
- O host real deve obter sessão, cadastro de chave, pin de chave, dispositivo, emissor e público-alvo de fontes **independentes de qualquer campo controlável pelo cliente**. A dataclass de política não torna o código confiável sozinha.
- Falta canal de assinatura confiável com aprovação humana exata do comando; Windows Hello/FIDO2, biometria, ACL Windows, proteção de banco SQLite contra rollback, sincronização PC/celular, CSRF/XSS e E2E de UI são trabalho futuro.
- A assinatura autentica bytes em relação à chave pública fornecida, não demonstra intenção humana nem prova sessão real no servidor.
- Métodos antigos de #1081 ficam restritos a implementação interna; não podem virar endpoints acessíveis que contornem esta proteção.
- Não há permissão de instalar agente, processar pagamentos, gerar autorização comercial, executar ordens de trade, alterar Render/Worker ou ativar produção.

## Validação

Suíte de 28 testes independentes e subtestes para adulteração de texto, case, assinatura, pin, nonce, sessão, dispositivo, público-alvo, emissor, escopo greeting/navigation, replay, expiração, admin delegado, comandos externos/compostos e preservação do estado em caso de bloqueio.

GitHub Actions Windows + Linux; criptography 50.0.2 e streamlit 1.64.0 instalados **somente nos runners descartáveis de CI**, não no computador do proprietário. O relatório de CI precisa concluir antes de qualquer alegação de aprovação.

## Cadeia e próximos gates

#1015 → #1078 → #1079 → #1081 → esta PR. Todas devem permanecer Draft até revisão de segurança, confirmação dos checks e resolução dos branches empilhados. Integração com host autenticado, chave real, confirmação do comando, testes E2E no PC/celular e qualquer merge/deploy exigirão autorização explícita. O Core V1 congelado e a main permanecem fora deste escopo.
