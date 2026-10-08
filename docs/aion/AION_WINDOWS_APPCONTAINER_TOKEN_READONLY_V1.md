# AION — Identidade nativa do processo AppContainer V1

**08/10/2026 · GitHub Draft · Somente consulta de token e testes em runner Windows descartável. NÃO executar no computador do proprietário nesta fase.**

## Problema real que faltava solucionar

A criação de um AppContainer e o relato do processo filho não estabelecem sozinhos que **o processo exato** esteja na identidade do AppContainer temporário autorizado. A inspeção anterior em Windows comprovou `TokenIsAppContainer`, mas ainda não comparou o **SID do token do filho** com o **SID derivado do nome do perfil autorizado** e não inspecionou a lista de capacidades efetivas do token. Além disso, a tentativa anterior de conexão local sob PowerShell isolado terminou em timeout; não é prova de bloqueio de rede. Não repetir a tentativa bloqueada por segurança da ferramenta.

## Implementação de código

`atlasquant_aion_windows_appcontainer_token_readonly_v1.py` fornece:

1. `inspect_windows_process_handle(process_handle, expected_profile_name)`: exige **handle de processo já aberto**, sem aceitar PID, credenciais, endpoint ou comando arbitrário.
2. Recusa nomes que não correspondam exatamente à nomenclatura descartável `AtlasQuantAIONProbe` + 12 caracteres hexadecimais minúsculos.
3. `OpenProcessToken(TOKEN_QUERY)` obtém token de processo sem modificação.
4. `GetTokenInformation(TokenIsAppContainer=29)` exige token marcado como AppContainer.
5. `GetTokenInformation(TokenCapabilities=30)` exige contagem real de capacidades igual a **zero**. Qualquer capacidade extra bloqueia.
6. `GetTokenInformation(TokenAppContainerSid=31)` obtém SID do token. `DeriveAppContainerSidFromAppContainerName` deriva SID esperado **sem registrar perfil**; `EqualSid` compara os dois SIDs.
7. Fecha handle de token e libera SID derivado em todas as saídas. Não divulga SID, nome do usuário, identificador do computador, caminhos ou outras informações privadas.
8. Em caso de qualquer falha, ausência de capacidades lidas, SID diferente ou token que não seja AppContainer, **recusa**. Mesmo se tudo conferir, retorna somente `NATIVE_TOKEN_IDENTITY_CANDIDATE_UNTRUSTED`.

## Segurança e limites

- O handle fornecido **ainda não tem origem autenticada**. A biblioteca não prova que pertence à criação recém-autorizada, não impede eventual troca de handle, não prende SID ao nonce/fonte assinado, não prova custódia de identidade física, não comprova integridade do binário/coletor e não autentica `HUMAN_OWNER`.
- Não confundir **zero capabilities** com bloqueio verificado de IPv4/IPv6, loopback, DNS, TCP, UDP, proxies, Windows brokers, pipes, dispositivos de rede ou sockets já abertos. O contrato de 16 superfícies da #1087 continua pendente.
- Não é uma implementação do lançador. Para uso real, um host auditado deverá manter **o handle exato** da criação `CREATE_SUSPENDED`, consultar SID/capacidades **antes** de permitir retomada, comparar perfil/manifesto assinados, instalar barreiras de rede e políticas adequadas, verificar Job Object e rollback, e coletar prova independente vinculada a nonce.
- Não instala AION, não cria AppContainer, não chama `CreateProcessW`, não altera token/ACL/Firewall/WFP, não faz rede e não executa scripts antigos.
- Nos testes Windows do GitHub, o **próprio token do processo CI normal** é inspecionado, devendo retornar `TOKEN_NOT_APPCONTAINER`. Outros testes com entradas adversariais são puros/sem WinAPI. Não há teste real do token de processo AppContainer neste PR.
- Os 12 requisitos físicos da #1049 permanecem sem atestação independente. `installer_authorized`, `build_authorized`, `deploy_authorized`, `physical_attestation_verified`, `network_deny_verified` e `process_handle_origin_verified` estão fixos em **False**, mesmo para resposta candidata.

**Autorizações preservadas:** GitHub PR Draft, sem merge, deploy, Worker/Render, persistência, compra/gasto, alteração do Windows, instalar AION ou usar credenciais reais. Manter teto provisório de infraestrutura R$200/mês.

## Referências técnicas Microsoft

- [TOKEN_INFORMATION_CLASS](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ne-winnt-token_information_class): TokenIsAppContainer, TokenCapabilities, TokenAppContainerSid.
- [TOKEN_APPCONTAINER_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-token_appcontainer_information).
- [GetTokenInformation](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-gettokeninformation).
- [DeriveAppContainerSidFromAppContainerName](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-deriveappcontainersidfromappcontainername).
