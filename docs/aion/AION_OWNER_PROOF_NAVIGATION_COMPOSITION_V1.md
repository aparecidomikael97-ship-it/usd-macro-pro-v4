# AION — Composição segura: assinatura do proprietário → navegação interna (V1)

Data: 08/10/2026. **Implementação isolada em branch Draft. Sem deploy, merge nem ligação com a interface real.**

## Objetivo

Compor a prova criptográfica da PR #1079 com a ponte de navegação interna da PR #1078, reutilizando a identidade e a sessão da #1015. A função de saudação produz somente texto; a função de navegação apenas solicita ao roteador interno existente um destino permitido: AtlasQuant, Trader, Negócios, Investimentos ou AION. **Não confirma tela aberta, não liga microfone e não abre aplicações externas.**

### Fluxo seguro (host autenticado, nunca navegador isolado)

1. O host autentica o ADMIN por mecanismo já existente e recupera sessão, dispositivo e chave pública HUMAN_OWNER **independentemente do payload do cliente**. Não derivar pin, digest de sessão, identificador de dispositivo, issuer/audience ou permissões de campos controlados pelo usuário.
2. O host cria `TrustedOwnerHostPolicy` com chave pública previamente inscrita e protegida, digest da sessão autenticada, dispositivo conhecido, issuer/audience fixados e registro SQLite de nonces durável com ACL revisada.
3. Recebe uma prova assinada Ed25519 com nonce novo (máximo 120 s) e chama **somente** `plan_verified_owner_greeting` ou `request_verified_owner_navigation` usando os objetos mantidos pelo host.
4. O verificador valida assinatura, pin, sessão, dispositivo, issuer/audience, validade temporal e consome o nonce atomicamente **antes** de produzir asserção efêmera. O wrapper passa esta asserção internamente à ponte. O retorno não contém a asserção como autorização reutilizável.
5. **Uma prova vale uma única chamada**: usar a prova de saudação novamente para navegação falha. Toda chamada seguinte exige prova nova; não há pairing, lembrança persistente de login nem biometria implementados.
6. Navegação é **solicitação**, não prova de execução. O host real futuramente deverá observar transição da UI e, quando apropriado, aplicar proteção contra CSRF, replay HTTP, e ações do cliente não confiáveis.

## Limites e bloqueios

- `TrustedOwnerHostPolicy` é **apenas um contêiner**. Como qualquer chamada Python, pode ser falsificado por quem já controla o próprio processo Python; segurança real exige hospedar este código do lado de um componente com confiança independente. Não usar este wrapper direto em Streamlit a partir de widgets sem middleware confiável.
- A prova deve ser emitida e apresentada por um emissor autenticado com lifecycle de chaves, revogação/rotação, FIDO2/Windows Hello quando habilitados e procedimentos de recuperação. Nada disso existe nesta etapa.
- O digest de sessão assinado **só é tão forte quanto sua origem**. Nunca aceitar o mesmo digest do cliente como valor esperado. A sessão real deve ser verificada pelo host.
- Proteção local de SQLite, permissão de diretório, rollback/backup, sincronização entre dispositivos e separação das credenciais ainda precisam ser auditadas com o PC disponível.
- Comandos compostos, “abre WhatsApp/ChatGPT/Spotify”, pagamentos, deploy, scripts, trading e ações destrutivas falham por desenho. Não executar por interface de texto.
- Prova inválida, vencida, chave errada, ausência de sessão ADMIN autenticada, replay ou store indisponível = **BLOCKED sem qualquer navegação**.
- O wrapper depende da atomicidade do registro de nonce em #1079, não cria novo banco por padrão, não grava fora do registry explicitamente fornecido.

## Validação planejada

- Testes offline em Linux e Windows, sem credenciais reais: chave gerada em memória, DB exclusivamente em diretório temporário do runner, casos positivos de saudação e navegação, replay, assinatura forjada, sessão/device/issuer divergentes, expiração, admin delegado, comando composto, apps externos, estado inalterado em bloqueios e ausência de flag de proprietário controlável na API pública.
- Inspeção estática de imports perigosos para o módulo de composição.
- Reavaliar os resultados do GitHub Actions antes de classificar qualquer conjunto de testes como aprovado.
- Teste manual no PC e celular fica **para depois**, mediante autorização expressa. Sem Render, Worker, PostgreSQL persistente, agente Windows, hotword, câmera, compra ou gasto. Teto provisório total R$200/mês permanece inalterado.

## Caminho de integração posterior

1. Resolver qualquer conflito de branches stacked (#1015 → #1078 → #1079 → esta PR) e exigir CI verde.
2. Vincular chave real e sessão real em um host confiável: ameaça de XSS/CSRF, rotação/revogação e rollback de nonce precisam de revisão independente.
3. Integrar interface apenas após análise de segurança e testes E2E no computador e celular do proprietário.
4. Qualquer merge ou deploy requer autorização explícita do HUMAN_OWNER.
