# AION — Observador independente de loopback e classificação de falhas V1

**08/10/2026 — Draft empilhado na #1087 → #1049. SOMENTE teste CI de `127.0.0.1`. Sem executar no computador do proprietário.**

## Motivo do bloco

O ensaio físico anterior criou/excluiu corretamente um perfil AppContainer e confirmou um filho com `TokenIsAppContainer = TRUE` e zero capacidades explícitas de rede. O `cmd.exe` de prova saiu com 37 conforme solicitado. Entretanto, o PowerShell isolado que tentaria TCP em `127.0.0.1` ficou aguardando até o prazo de 8 segundos. Isso **não prova negação de rede**: pode ser inicialização, ambiente, biblioteca, autorização ou TCP. A tentativa posterior de executar outro cliente de rede no PC foi barrada pelo mecanismo de segurança da ferramenta **antes de iniciar**; não deve ser contornada. No fechamento, o perfil criado retornou HRESULT 0 para exclusão, sua pasta sumiu e BFE/Firewall/Defender permaneceram ativos.

### O que foi implementado agora

Dois módulos independentes, sem dependências externas:
- `atlasquant_aion_windows_loopback_ci_collector_v1.py`: executado exclusivamente em runners CI. Abre um servidor TCP efêmero vinculado somente a **127.0.0.1**. Primeiro observa, por leitura real no servidor, uma conexão de controle normal. Em seguida lança Python `-I -B -S` como **processo normal de CI, NÃO AppContainer**, com shell desativado, ambiente mínimo, prazo de 6 segundos, diretório descartável e nonce aleatório de 128 bits. O filho tenta TCP na mesma porta e envia o nonce. O servidor registra, independentemente do texto que o filho imprimiu, se recebeu o nonce. Depois fecha o socket e apaga o diretório temporário.
- `atlasquant_aion_windows_loopback_observer_classifier_v1.py`: módulo **puro**, sem rede e sem poder sobre Windows, que confere campos estritos, origem funcional esperada `NORMAL_CI_CHILD_NOT_APPCONTAINER`, controle positivo, resposta ao desafio, código de saída, erro do socket e recepção observada. Um status de negação enviado pelo filho é **CONTRADITÓRIO** se o servidor recebeu o nonce. `timeout`, erro de inicialização `0xC0000022`, erro de rede que não seja acesso negado ou controle positivo indisponível são **INCONCLUSIVOS**, nunca certificados de bloqueio.

Mesmo uma observação sintética sem pacote recebido + erro `WSAEACCES 10013` (ou `EACCES 13`) pode ser classificada, **no máximo**, como `UNTRUSTED_DENIAL_CANDIDATE`. Não há comprovação independente da origem do registro, assinatura do coletor, attestation de `TokenIsAppContainer` ou ligação a perfil do usuário real. Não é prova de nenhuma das 16 superfícies da PR #1087.

### O que os testes conseguem comprovar

CI Windows e Linux testam funcionalmente que um filho **normal** alcança a mesma porta local que o coletor controla; ou seja, o verificador é capaz de observar `NETWORK_ACCESS_OBSERVED` em condições conhecidas. 32 testes adversariais também cobrem falhas, respostas conflitantes, erro 10013 forjado, ausência de nonce e campos manipulados. Isso calibra os instrumentos e demonstra **rejeição de falso positivo**, não isolamento de rede.

### Próxima evolução exigida antes do instalador

Somente sob futura autorização específica e após revisão de código, desenvolver um coletor Windows **separado e assinado**, com identificação real do processo filho antes de soltá-lo de `CREATE_SUSPENDED`, comparação de token/AppContainer, perfil temporário e rollback garantido, servidor localhost testemunha e códigos de erro de Winsock. Um erro 10013 não basta: é obrigatório associá-lo ao processo certo, ao endpoint realmente alcançável e à política aplicada. Avaliar limitações AppContainer para IPv6, DNS, UDP, proxy, pipes e capacidades herdadas. Os 12 requisitos físicos da #1049 e as 16 superfícies da #1087 permanecem pendentes de atestação independente.

### Segurança e governança

Esta PR não chama `CreateAppContainerProfile`, `CreateProcessAsUserW`, WFP, WinDefend, Firewall, ACL, Rede externa, DNS, API paga ou serviços do usuário. Nenhuma chave humana ou segredo real. Não instala software, não muda configurações no computador e não usa o Desktop Commander para executar o novo coletor. Workflow apenas no GitHub sob pull_request, em runners temporários, sem secrets e sem privilégios adicionais. Nenhum método retorna `physical_network_denial_verified`, `all_network_surfaces_verified`, `appcontainer_token_verified`, `installer_authorized`, `build_authorized` ou `deployment_authorized` como true.

Não autoriza merge, deploy, Worker, Render, reativação de persistência ou novos gastos. Teto temporário R$200/mês intacto.
