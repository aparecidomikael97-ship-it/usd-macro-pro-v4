# A183 — bloco de evidência dos seis P0, exclusivamente LAB

**22/10/2026 (America/Cuiaba). 0/6 P0 homologados. HARD NO-GO. ZERO_AUTO_RESEND.**
Nenhuma autoridade, chave, conta, cliente, serviço, Worker ou operação real utilizada. Sem merge/deploy/push na main, contratação, provisionamento, gasto autorizado ou mudança de política.

## Ponto de partida e preservação
PR Draft A182 #1472 inspecionada: aberta, não merged, base A181 #1471; head `c9cd24c92d6b92a8c25dc7af636b73b6a5aa6365`, código anteriormente testado `169105f1c83896b61d6dd331c128b604de37de93`. Relatório A182, matriz, oito logs resumidos em ci-verified.json e cadeia A176–A181 conferidos. A176 #1466 → A177 #1467 → A178 #1468 → A179 #1469 → A180 #1470 → A181 #1471 → A182 #1472 é uma cadeia LAB empilhada; presença em main não foi presumida.

Novo ramo: `lab/aion-six-p0-evidence-a183-20261022`, criado no head A182. Checkout existente /workspace/usd-macro-pro-v4 preservado em work/`5744b2b`. Git fetch segue bloqueado por proxy. Trabalho local em cópia separada /workspace/work/a183-source; **140 blobs herdados presentes, exceto staged_store modificado, conferidos sem divergência contra árvore A182**. É cópia parcial, não checkout completo. Publicação por Git Data API sobre árvore A182, com lease de SHA no ramo novo, sem sobrescrever trabalhos alheios.

## P0-5/6 — RED antes de correção e investigação nativa
`test_atlasquant_aion_native_path_a183_lab.NativeDeclaredPathTests` começou com dois testes: desvio da fábrica para conexão SQLite real em outro arquivo, um para leitura, outro para escrita. Antes do controle: **2 FAIL, 0 ERROR**; a operação não era negada. Ver `evidence/a183/sqlite-before-red.log`. A injeção da fábrica é sintética; a conexão e os arquivos são SQLite reais temporários.

O descritor separado da fachada continuava apontando ao arquivo esperado; a conexão nativa consultava outro. Logo fstat(anchor) não prova identidade do fd SQLite. Python 3.12 local/SQLite 3.53.1 oferece deserialize, mas não Connection.fileno. Não se leu layout privado CPython nem se presumiu que um pathname seja um handle.

Controle adicionado em staged_store: compara PRAGMA database_list da conexão real com caminho principal esperado antes/depois do método; nega outros bancos anexados. Corrige **somente conexão declaradamente desviada para caminho distinto**, não vínculo atômico ao inode/VFS. Inicialização de SQLiteChatStore ainda ocorre antes desse diagnóstico e pode executar PRAGMAs/schema; não se afirma ausência de qualquer escrita de inicialização. Desvio observado depois do método vira **NATIVE_DATABASE_PATH_POST_OPERATION_OUTCOME_UNKNOWN**, latched, sem repetir a escrita.

### Contraexemplo mais forte preservado
No Linux, o teste troca o arquivo no mesmo pathname, abre SQLite, move o arquivo aberto e restaura o original antes das comparações:
- PRAGMA database_list ainda declara o pathname original;
- descritor separado e lstat veem o original;
- leitura nativa retorna conteúdo do arquivo destacado: **A183_NATIVE_SAME_NAME_ABA=WRONG_FILE_READ_PATH_CHECK_PASSED**.
Isso demonstra que a correção de pathname **não resolve P0-5**.
- No teste de escrita equivalente, SQLite local rejeitou com **SQLITE_READONLY_DBMOVED**, antes de inserir. É uma proteção nativa observada nesse VFS/versão, não conclusão cross-platform nem garantia contra rollback sob mesmo inode.
- Windows pode negar rename do arquivo nativo aberto; os testes registram OS_OR_FACADE_DENIED/OS_DENIED quando isso ocorre. Não se conta ausência de capacidade de criar symlink como prova de cobertura.
- O teste pós-commit troca a conexão após gravar uma vez; fachada sinaliza UNKNOWN e impede repetição. Estado gravado conferido por conexão independente de teste.

## Leitura alternativa defensável: artefato offline pinado
`aion_chat/pinned_snapshot_a183_lab.py`:
1. Exige SHA-256 retido explicitamente pelo chamador, não aprende hash do arquivo candidato. Inspeciona cadeia de pais e aliases, abre fd de leitura com flags suportadas, fstat regular/dev/inode, tamanho limitado a 16 MiB.
2. Captura bytes pelo mesmo fd; verifica metadados/cadeia antes/depois, ausência de -wal/-shm/-journal, hash completo e cabeçalho SQLite em formato rollback/offline.
3. Deserializa **esses bytes** em uma conexão SQLite :memory: e verifica database_list vazio para main e quick_check. Cada consulta usa conexão nativa em memória nova, no thread chamador.
4. Autorizer/query_only negam DML, DDL, ATTACH, PRAGMA e funções fora da pequena lista. Persistência e backup_to falham com NATIVE_PERSISTENCE_UNATTESTED_ZERO_AUTO_RESEND; não criam destino nem alteram origem.
5. Testes: restauração sob mesmo inode com hash atual retido, mudança durante captura, rename/deleção depois da captura, threads, novo processo, WAL/sidecars, SQL hostil e fechamento.

**Não é substituição do store de chat vivo, backup/restauração autenticados ou solução de escrita VFS.** Um hash fornecido pelo mesmo operador não prova proveniência externa; restaurar o hash junto ao artefato admite estado antigo. A leitura retorna precisamente o snapshot retido, sem promessa de atualidade. Nenhuma persistência experimental foi implementada sem contrato nativo defensável.

## P0-1/2 — cerimônia existente e verificações locais
Inspecionados:
- `atlasquant_aion_owner_signature_ceremony.py`: V2.24, HUMAN_OWNER/atlasquant-owner, Ed25519 externo, finalidade OWNER_IDENTITY_AND_STATE_ACKNOWLEDGEMENT, ceremony_id, nonce, key ID/versão, fingerprint, SHA alvo, desafio/estado V2.23 de persistência, janela máxima 180 s. verify_owner_signature reconstrói material, valida raiz/janela/assinatura e registro de nonce. Assinatura/acknowledgement não substituem decisão explícita do proprietário ou freeze.
- `atlasquant_aion_trust_root.py`: registro de raiz Ed25519 e estados ACTIVE/RETIRED/REVOKED. Um registro local não autentica sua própria gênese ou resiste a rollback.
- `atlasquant_aion_owner_decision_persistence_attestation.py`: V2.26, decisão V2.25 e nonce durável, recibo externo de persistência, target SHA/runtime sha/path/branch, janela observada até 300 s; prepara/verifica evidência, não autoriza escrita real neste LAB.

Faltam: associação comprovada da chave a uma pessoa/proprietário legítimo; cerimônia independente de emissão e guarda; origem/rotação/revogação de raízes fora do controle do host; prova de controle atual e recuperação após perda; atestação externa da persistência/efeito e disponibilidade de consulta. Nenhuma identidade biométrica, documento, assinatura ou consentimento real foi coletado.

## P0-3/4 e interface de autoridade externa
`aion_chat/external_authority_a183_lab.py` define contrato estrito e sem transporte:
- IDENTIDADE: owner + identity_authority; RESERVA: owner + witness; RECIBO: provider + witness.
- Conjunto exato de campos e signatários; chaves distintas por papel; desafio novo; evento/escopo/original_sha256; epoch e sequence acima do piso retido; root_snapshot_sha256; prazo até 60 s; issuer/key ID; Ed25519 sob domínio separado; revogação.
- Snapshot de pins copiado; alteração unilateral de raiz, assinante revogado, epoch/piso antigo, desafio/escopo/vínculo falsos, booleano, timeout e assinatura inválida negados.
- Resultado válido é **lab_verified**, e sempre **permits_send=False, permits_retry=False, external_homologation=False**. Não foi conectado ao Outbox/Worker como autoridade.
- Dois signatários/chaves distintos no mesmo teste não são dois domínios independentes. Identidade, bootstrap e monotonicidade continuam fixtures do chamador. Reiniciar/restaurar pins/piso permite repetir evidência; teste de risco permanece verde por caracterização.

A182 permanece intacto: rollback custódia+checkpoint, substituição de inscrição original e raiz+fingerprint continuam abertos. ZERO_AUTO_RESEND/UNCERTAIN herdados não foram relaxados. O trecho que depende de serviço externo/decisão de proprietário foi parado; apenas contrato e mocks foram acrescentados.

## Execução reproduzível e escopo local
```sh
python -B scripts/run_a183_lab.py specific
python -B scripts/run_a183_lab.py regression
python -B scripts/run_a183_lab.py sqlite
python -B scripts/run_a183_lab.py external-red
```
- Específicos: **28/28** = cinco native-path (incluindo caracterizações), 13 artefato, dez autoridade (incluindo caracterização de reset).
- A176–A182/Outbox/Saga: **132/132**, herdados.
- SQLite histórico: **93 executados, 92 PASS + 1 ERROR**, requests ausente; histórico já observado em A182 e proxy continua impedindo instalação local. Não removido nem chamado de verde.
- Local cryptography 50.0.0; CI fixa 50.0.2 e requests 2.34.2.
- external-red: **5 FAIL, 0 ERROR**, sem skip/expectedFailure/continue-on-error: três requisitos A182 + leitura e escrita após restore sob mesmo inode no store vivo. São requisitos de aceite não satisfeitos, não corrigidos por snapshot offline.
- Mocks de socket valem para processo de teste, não são firewall e não se propagam automaticamente a subprocessos. Todos os efeitos dos testes específicos ficam em diretórios temporários; nenhum serviço externo foi provisionado.

## CI e comparação canônica prevista
Workflow A183 roda specific/regression/sqlite/external-red em Ubuntu e Windows. external-red deve falhar sem mascaramento. Jobs Ubuntu separados comparam **a mesma base A182 e o candidato**, usando os seletores extraídos dos workflows canônicos sem alterar módulos:
- Quality: 525 módulos da etapa Run quality suite.
- Security: 27 módulos unittest + 34 arquivos pytest.
- Security audit: pip-audit -r requirements.txt e bandit -q -lll com a lista canônica.
Instala dependências fixadas, compila fontes e executa com guard LAB de rede para unittest/pytest. pip-audit consulta fontes públicas de vulnerabilidades, sem conta/chave/API paga. Não se executam etapas de deploy, Worker, browser com produção ou SBOM/upload; portanto não chamar isso de execução integral de todos os passos dos workflows canônicos.

Runs, SHAs, contagens e diferenças base/candidato serão registrados somente após leitura dos logs. Erros históricos iguais nos dois SHAs não serão atribuídos ao patch; erros novos não serão apagados. Quality/Security não foram executadas no checkout parcial local.

## Matriz de aceite por P0
| P0 | Causa / controle / contraexemplo | Evidência atual | Status e bloqueio | Próximo gate mínimo |
|---|---|---|---|---|
| 1 | chave/owner autoafirmados; contrato de dois papéis nega formatos/chaves inválidos, não identifica pessoa | testes autoridade + inspeção cerimônia V2.24 | ABERTO; vínculo independente HUMAN_OWNER | cerimônia externa, recuperação e revogação auditadas |
| 2 | recibo local não prova efeito; contrato vincula assinaturas a desafio/efeito/raiz, mas origem continua fixture | A178–A183, testes de assinatura/revogação/epoch | ABERTO; provedor e raiz autenticados | recibos reais verificáveis em ambiente autorizado, sem execução nesta missão |
| 3 | ID/inscrição nova e memória restaurada reabrem efeito; negação local e contrato estrito não fornecem unicidade autêntica global | 132 herdados + reset/rollback RED | ABERTO; identidade original e reserva durável externas | autoridade de evento autêntico, reserva linearizável antes de envio |
| 4 | checkpoint+custódia restauráveis; piso/epoch locais detectam só rollback relativo ao snapshot retido | A182 RED + A183 contratos | ABERTO; custódia monotônica e H0 reais | perda total/partição/rebootstrap entre domínios independentes com prova |
| 5 | anchor próprio/pathname não é fd SQLite; novo diagnóstico bloqueia caminho diferente; mesmo nome ABA ainda lê errado; snapshot pinado evita arquivo vivo | 2 RED→GREEN; ABA real Linux; 13 testes snapshot | ABERTO; VFS/handle atômico e snapshot vivo não provados | VFS/API nativa auditada ou arquitetura de artefato imutável homologada |
| 6 | escrita/backup podem ter resultado incerto; postcheck latches UNKNOWN, SQLite observado rejeita DBMOVED; novo snapshot não persiste | pós-commit UNKNOWN + DBMOVED + restore live RED | ABERTO; atomicidade, sidecars, backup/restore e durabilidade reais | protocolo de commit e fd/VFS, falhas de processo/SO e readback independente |

## Custos e revisão humana
Custo contratado/autorizado adicional: **ZERO**. Nenhuma contratação, conta, credencial, domínio ou runner pago criado. Ensaios usam CI hospedada do repositório público; não foi feita auditoria financeira da plataforma. Estimativas futuras, sem contratação: revisão de VFS/ABI e matriz de falhas = esforço de engenharia; custódia/quórum/HSM/identidade/H0 = possível serviço e operação recorrentes, **valor não cotado**. Qualquer despesa exige consentimento futuro explícito.

Solicitada revisão humana do contrato externo, cerimônia de proprietário, autoridade de gênese/recovery e plano de VFS/backup. Isso não é solicitação de ativação ou deploy. **0/6 P0 homologados; HARD NO-GO; ZERO_AUTO_RESEND.**

