# AtlasQuant — configuração segura de acesso

O AtlasQuant possui perfis separados **USER**, **SALES** e **ADMIN**. A camada de login é independente do motor de trading: autenticar um usuário não habilita broker, ordens reais, promoção automática, alteração automática de pesos ou gates.

## 1. Criar o primeiro administrador

Execute localmente:

```bash
python atlasquant_user_bootstrap.py --username admin.01 --role ADMIN
```

A senha é solicitada sem eco no terminal. O resultado contém somente um hash PBKDF2-SHA256. A senha em texto puro não é gravada pelo utilitário.

## 2. Configurar os Secrets

Adicione o JSON gerado ao secret:

- `ATLASQUANT_USERS_JSON`
- `ATLASQUANT_AUTH_REQUIRED=true`

Para uma implantação declarada como produção, use também:

- `ATLASQUANT_ENV=PRODUCTION`

Quando `ATLASQUANT_ENV=PRODUCTION`, o login é obrigatório mesmo que `ATLASQUANT_AUTH_REQUIRED` tenha sido configurado incorretamente como falso.

## 3. Perfis

- **USER**: leitura do aplicativo.
- **SALES**: leitura do aplicativo + área comercial.
- **ADMIN**: área comercial + administração de contas.

Nenhum perfil recebe permissão para ativar trading real.

## 4. Criar outras contas

Depois de entrar como ADMIN, abra a aba **Conta**. O portal gera um registro JSON seguro para uma nova conta e permite baixar esse registro. Ele não altera os Secrets automaticamente.

Ao mesclar registros em `ATLASQUANT_USERS_JSON`, mantenha um único bloco `users` e não duplique nomes. Nomes que colidem após normalização são rejeitados por segurança.

## 5. Revogar uma sessão

Para revogar uma conta, altere uma destas propriedades no secret e reinicie/reimplante o app:

- `active=false`;
- perfil/role;
- hash da senha;
- remoção do usuário.

Sessões antigas deixam de ser aceitas quando o registro atual não corresponde à credencial usada no login.

## 6. Proteções atuais

- senhas em texto puro são rejeitadas pelo registro;
- PBKDF2-SHA256 com salt;
- comparação segura do hash;
- limite de tamanho do cadastro;
- colisões de usuário rejeitadas;
- sessão vinculada à credencial atual;
- bloqueio temporário por repetidas tentativas inválidas na mesma sessão;
- produção explícita exige autenticação;

- sessão autenticada expira por inatividade e por idade máxima;
- hashes de contas não são exibidos inline no portal ADMIN; o registro completo é somente para download administrativo;
- falha da camada de login com autenticação obrigatória bloqueia o app.

O bloqueio por tentativas é uma proteção local de sessão e não substitui rate limiting/WAF da plataforma quando o serviço estiver exposto publicamente.

## 7. Trading real

A configuração de usuários não altera os contratos de segurança do AtlasQuant. Continuam separados e desativados por padrão:

- `real_orders=false`;
- `broker_connection=false`;
- `automatic_gate_change=false`;
- `automatic_promotion=false`.
