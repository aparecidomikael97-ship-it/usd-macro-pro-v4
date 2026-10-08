# AION — Executável pinado, intenção Ed25519 e processo suspenso V1

**08/10/2026 — Apenas testes negativos GitHub CI; não instala nem executa AION no computador do proprietário. PR empilhada sobre #1090 → #1089 → #1088 → #1087 → #1049.**

## Problema concreto: arquivo autorizado ≠ processo executado

Mesmo depois de verificar `TokenIsAppContainer` e de demonstrar, em CI, que um processo comum suspenso pode ser encerrado sem executar código, falta ligar autorização, **bytes exatos do programa**, caminho real da imagem e o handle do processo que foi criado. A lacuna clássica é a substituição entre inspeção e execução (*time-of-check/time-of-use*).

## Implementado neste bloco

**Contrato criptográfico negativo** (`atlasquant_aion_windows_signed_binary_ci_negative_intent_v1.py`):
- Intenção canônica JSON assinada com Ed25519, contendo esquema, ação exclusivamente `QUARANTINE_NORMAL_CHILD_NEVER_RESUME`, nonce de 128 bits, caminho absoluto normalizado Windows, SHA-256 minúsculo de 64 dígitos, início/fim de validade com janela máxima 120s e decisão esperada `TOKEN_NOT_APPCONTAINER`.
- Confere assinatura, integridade de campos, nonce, idade, SHA-256 de bytes observados e caminho da imagem reportado pelo Windows. Reprova assinatura corrompida, prazo expirado, comando de instalação/retomada ou processo/imagem divergentes.
- **A chave de assinatura é uma chave de teste gerada temporariamente no GitHub.** Não é a chave Ed25519 do proprietário nem um root of trust custodiado. Mesmo a assinatura correta retorna `SIGNED_CI_NEGATIVE_BINARY_CANDIDATE_UNTRUSTED`; `safe_to_resume`, `installer_authorized`, `build_authorized`, `deploy_authorized`, `network_deny_verified` e `trusted_root_verified` são permanentemente falsos.

**Coletor nativo Windows NEGATIVO** (`atlasquant_aion_windows_pinned_suspended_ci_negative_v1.py`):
- Só habilitado em `GITHUB_ACTIONS=true`, evento `pull_request` e runner Windows. Essa condição não equivale à atestação criptográfica de runner confiável.
- Resolve a imagem de Python **do próprio runner**, mantendo um `CreateFileW` de leitura **sem compartilhar WRITE ou DELETE** durante o ensaio; usa `GetFileInformationByHandle` para comparar identificador de volume/índice, tamanho e marca de alteração; usa `ReadFile` e SHA-256 antes/depois. Não abre a instalação Python do proprietário.
- Cria Job Object `KILL_ON_JOB_CLOSE` e um filho Python mínimo em `CREATE_SUSPENDED` com `bInheritHandles=false`, sem `ResumeThread`, ambiente scrubbed e escrita sintética em diretório temporário apenas se indevidamente retomado.
- Consulta `QueryFullProcessImageNameW` **no handle real do processo suspenso**, compara a imagem efetiva com a intenção assinada e inspeciona token com o leitor da PR #1089. Processo comum **não é AppContainer**, portanto é sempre rejeitado e encerrado.
- Fecha todos os handles e apaga scratch. O arquivo-sentinela deve permanecer ausente. Falta em qualquer gate → processo não é retomado, CI falha.

**Testes:** casos adversariais de substituição de caminho, SHA, troca de chave, assinatura adulterada, prazo, manifesto e flags. Teste nativo real do caminho negativo exclusivamente em runner Windows; Linux cobre contrato puro. Dependência Ed25519 `cryptography==50.0.2` instalada somente no runner do GitHub, sem custo adicional registrado ou instalação no computador.

## Delimitação de segurança: esta PR NÃO prova TOCTOU resolvido para produção

- `CreateFileW(FILE_SHARE_READ)` impede **novas aberturas incompatíveis** de escrita/exclusão enquanto o handle permanece aberto, mas **não revoga handles escritores preexistentes**, não atesta caminho contra reparse points, hardlinks, cache/section file identity ou semântica de executáveis no kernel.
- Comparar `QueryFullProcessImageNameW` ao nome esperado + SHA do handle aberto não prova, em todo cenário adversarial, que o objeto de arquivo do executável esteja criptograficamente vinculado à seção que o loader mapeou. Em produção exigir prova física independente de imagem, controles contra reparse/hardlinks, binário assinado/pinado, verificação de identidade do arquivo, proteção de handles/ACLs e custódia do manifesto.
- Como a chave efêmera **assina aquilo que o mesmo runner acabou de observar**, assinatura válida só comprova consistência de um fixture; não autoriza um fornecedor nem a identidade do HUMAN_OWNER. Ainda faltam chave pública raiz pré-configurada do proprietário, cadeia de confiança, assinaturas reais, ledger de nonce persistente e vinculação de sessão.
- **Nenhum caminho de retomada positiva está implementado.** Nenhum AppContainer real é lançado neste bloco, nenhum bloqueio de rede, TCP/UDP/loopback/DNS/proxy/IPv6 foi demonstrado no computador do proprietário.
- Continuam pendentes os 16 testes de rede (#1087) e os 12 requisitos de validação física independente (#1049). Não transformar CI verde em licença de instalar.

## Governança

Nenhuma execução física no PC do usuário, instalação AION, alteração de política do Windows/Firewall/WFP, AppContainer novo, rede externa, senha/chave humana, merge, deploy, Worker, Render, persistência produtiva, gasto adicional ou aprovação implícita. PR Draft; orçamento provisório até R$200/mês preservado. Qualquer passo físico exige revisão do procedimento e autorização específica.

## Referências técnicas

- [CreateFileW — dwShareMode](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)
- [GetFileInformationByHandle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfileinformationbyhandle)
- [QueryFullProcessImageNameW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-queryfullprocessimagenamew)
- [CreateProcessW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw)
