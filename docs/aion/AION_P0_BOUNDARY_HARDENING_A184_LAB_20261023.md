# A184 — integridade de recuperação e fronteiras de callbacks, somente LAB

**0/6 P0 homologados. HARD NO-GO. ZERO_AUTO_RESEND.**

A184 parte da A183 Draft #1474, head `172be01c5ae665fbbfddb2c4d5dc02f15b77e953`, sem merge. O código/testes finais A183 foram testados em `dccdd939fa54df641b1def5f9048b237c8d05cbc`; o head seguinte contém apenas documentação. A182 #1472 e a cadeia A176–A181 permanecem antecedentes empilhados, não presumidos presentes em main. Na inspeção, main continuava em `5744b2b7b17c84331e6f27c569064993ff587782`.

Ramo novo: `lab/aion-p0-boundary-hardening-a184-20261023`. O checkout anterior e os ramos de remediação de dependências foram preservados. Não há merge, deploy, Worker ativado, política de confiança alterada, serviço provisionado, conta/chave real, envio a cliente ou efeito externo. As chaves, adaptadores, falhas de timing e autoridades dos testes são **sintéticos**, mesmo quando SQLite e Ed25519 são reais.

## Resultado por P0

| P0 | Causa e controle local A184 | Contraexemplo/evidência | Bloqueio externo e gate mínimo | Estado |
|---|---|---|---|---|
| 1 — HUMAN_OWNER | O callback podia substituir o original referenciado durante a verificação. O contrato agora retém sua própria cópia do evento/configuração e valida contra ela. | `AuthorityBoundaryTests.test_query_cannot_replace_original_binding_through_retained_input`: RED antes, proteção GREEN depois. | Cerimônia que vincule pessoa/organização, papel, escopo e controle da chave a uma fonte independente; bootstrap aprovado e perda/rotação/revogação auditáveis. Chaves locais não comprovam identidade. | ABERTO |
| 2 — Recibos | Papéis distintos podiam verificar mensagens diferentes se o produtor alterasse a resposta compartilhada entre verificações. Resposta capturada e mensagem canônica única para todas as assinaturas; cópias também na fronteira Outbox/verificador. | Teste usa verificação Ed25519 real e um hook sintético que altera a resposta entre assinaturas; duas mensagens válidas distintas deixam de ser admitidas como quórum. | Fonte de recibo e raiz autenticadas fora do chamador, recibo do efeito real com vínculo completo A178, relógio/frescor, rotação e revogação consultáveis. O envelope A183 não substitui sozinho esse recibo. | ABERTO |
| 3 — Primeira tentativa | Cópias rasas permitiam mudar payload após autorização/reserva. Cada callback recebe cópia profunda independente; alteração persistente no argumento invalida o retorno. | Dez regressões de autorização, orçamento, testemunha, send, recibo e reconciliação: 10 FAIL antes, 10 PASS depois. Resposta perdida continua incerta; nenhum caminho novo para RETRY. | Evento de negócio autêntico e inscrição original imutável, reserva global durável antes do efeito e deduplicação do mesmo evento sob IDs manipulados. Chamador privilegiado ainda pode substituir código/raízes/original. | ABERTO |
| 4 — H0 | Isolamento local impede referências retidas de alterar a próxima etapa; não cria monotonicidade. O piso/epoch do contrato continua apenas configuração LAB. | Os três requisitos externos herdados A182 continuam FAIL: rollback conjunto, substituição do original e troca conjunta de raiz/fingerprint. | Custódia monotônica independente, consulta H0 fora do host, ausência/ambiguidade negadas, recuperação após perda total sem nova gênese automática; ensaio real de restauração simultânea. | ABERTO |
| 5 — SQLite leitura | Validação reabria um pathname e aceitava arquivo vazio/SQLite alheio. Recuperação captura bytes uma vez por fd próprio e os valida com SQLite `:memory:`; snapshot rejeita sidecars pendentes e limita consultas. | Vazio/schema errado/substituição após validação eram aceitos; novos testes os bloqueiam ou mantêm exclusivamente os bytes capturados. Os ensaios A183 ainda demonstram ABA no store vivo. | Provar vínculo atômico com o handle/VFS efetivo em host alvo ou homologar outra arquitetura; compatibilidade real Linux/Windows, processos, restore/rollback e SO adversarial. Nosso fd não é o fd nativo de uma conexão SQLite live. | ABERTO |
| 6 — SQLite escrita | Restore/backup podiam publicar B com hash referente a A. Publicação usa apenas os bytes validados, temporário exclusivo, fsync e verificações antes/depois. Falha após tentativa de replace é UNCERTAIN. | Testes de troca de fonte/backup, commit concorrente visível, falha de escrita, replace com ACK perdido e troca pós-publicação. Os dois requisitos live de restore A183 continuam FAIL. | Atomicidade VFS/commit e todos os call sites, exclusão de conexões ativas, WAL/sidecars, recuperação física/power loss, reconciliação e custódia antirollback reais. | ABERTO |

## Invariantes e pontos de leitura/gravação

`ExecutionOutbox.enqueue` persiste decisão e intenção no mesmo SQLite; o caminho analisado é `claim_next → revalidação de autorização/orçamento → UNCERTAIN persistido → reserva de primeira tentativa → send → admissão de recibo/ledger`. A reserva é exigida antes de send. Ausência de callback/prova, exceção ou alteração da reserva nega send e mantém UNCERTAIN. Após cruzar send, perda de resposta ou alteração do argumento não prova ausência de efeito: mantém UNCERTAIN, sem reenvio automático. Rejeição só pode terminar FAILED com verificação de efeito zero; não libera retry. Reconciliação confirma apenas com verificação, e a ausência autoafirmada continua sem autorizar RETRY. Saga mantém reconciliação obrigatória antes de compensar um resultado desconhecido.

`_bound_callback` retém o vínculo canônico dos argumentos privados antes da chamada, compara depois e copia o retorno. Autorizar/orçar com argumentos alterados bloqueia antes do efeito; testemunha alterada bloqueia antes de send; send alterado já pode ter produzido efeito, portanto resultado incerto. A verificação de recibos não compartilha objetos com adaptador ou persistência. Um callback hostil no mesmo processo pode agir fora da interface ou alterar e restaurar valores antes de retornar: **não há isolamento de processo nem prova de autoridade**.

`ExternalAuthorityContractLab.admit` captura evento antes de query, copia resposta e usa uma única sequência de bytes canônicos para todas as assinaturas. Mantém exatamente `permits_send=False`, `permits_retry=False`, `external_homologation=False`. O produtor ainda controla pins/piso originais no LAB; quatro chaves distintas não demonstram quatro operadores independentes. Nada foi conectado ao Worker.

`_validate_database_file` abre somente leitura, sem criação/reabertura SQLite do pathname, verifica a cadeia observável de caminhos e fd, captura no máximo 16 MiB, rejeita ambiguidades e valida os mesmos bytes em SQLite nativo `:memory:`. Requer formato offline DELETE, schema Chat com DDL base conservador, FK e UNIQUE de sequência. Rejeita triggers/views/virtual tables e variações de constraints das três tabelas base; permite tabelas ordinárias adicionais de Outbox/Saga. A revisão encontrou colunas NOT NULL extras e CHECK adicionais que passavam a forma mínima e impediam gravação normal; novos RED preservam essa reprodução e um índice UNIQUE extra, e o gate foi restringido às formas de DDL emitidas pelo próprio store. Não é garantia de compatibilidade funcional com qualquer banco SQLite. O relatório privado retém esses bytes, que são a única entrada de restore/publicação. Um banco vazio já não apaga o destino válido.

`backup_to` usa API SQLite de backup para um temporário, normaliza o artefato para DELETE e valida/captura. `_publish_database_report` escreve bytes capturados em temporário exclusivo, fsync, verifica conteúdo e mudanças observáveis no destino, faz replace e verifica o arquivo publicado. Qualquer falha durante/depois da tentativa de replace produz `RECOVERY_PUBLICATION_UNCERTAIN_ZERO_AUTO_RESEND`. Não há rollback fictício nem repetição automática. Um teste aplica o replace real e depois perde a resposta: o destino já mudou, mas não se informa sucesso verificado.

## Limites e compatibilidade SQLite

- Restore passa a aceitar somente artefato **offline DELETE**, schema Chat compatível e tamanho até **16 MiB**. Isso é uma restrição conservadora deste candidato LAB; bancos maiores, outros schemas, backup WAL e extensões executáveis falham fechados. Não é migração operacional autorizada.
- O destino precisa estar offline/quiescente. Sidecars são negados, mas sua ausência não prova inexistência de conexão DELETE ativa. Comparações por pathname/metadados não impedem ABA coordenado por host privilegiado; uma mudança após a última verificação ainda é possível.
- Captura única elimina a reabertura da origem após validação; não comprova frescor, autoria, completude da história, antirollback ou identidade do VFS de outro handle. Restaurar bytes antigos estruturalmente válidos continua possível sem autoridade monotônica.
- Fsync do arquivo e replace não comprovam durabilidade do diretório em todos os SOs, power loss, hardware ou semântica de backup distribuído. Pós-publicação incerto exige reconciliação e não pode gerar efeitos externos repetidos.
- Snapshot A183 permanece artefato offline fixado em memória. A184 adiciona `lstat` para sidecars inclusive aliases pendentes; consultas têm limites configuráveis somente para restringir os tetos de 1.000.000 callbacks VM, 10.000 linhas e 4 MiB de material retornado. Não trunca; nega toda a consulta excedida. Usa `SQLITE_LIMIT_LENGTH`, consumo incremental e temporários em memória. Não é teto de wall-clock, RSS total ou preparação SQL; não substitui o store vivo.
- Testes de capacidades do SO imprimem quando symlink/rename não é suportado. Esse retorno deve ser distinguido de uma demonstração da proteção; nenhum skip/expectedFailure foi acrescentado para esconder aceite não atendido.

## Reprodução e testes

Dependências do repositório foram mantidas. Python 3.12; `cryptography==50.0.2` e `requests==2.34.2` nos jobs LAB. Para canônicas: requirements existentes, pytest9.1.1, playwright1.63.0, pip-audit2.10.1 e bandit1.9.4. Os comandos abaixo não ativam adapters reais:

```text
python -B scripts/run_a184_lab.py specific
python -B scripts/run_a184_lab.py regression
python -B scripts/run_a184_lab.py sqlite
python -B scripts/run_a184_lab.py external-red
python -B scripts/run_a183_canonical_lab.py quality
python -B scripts/run_a183_canonical_lab.py security-unittest
python -B scripts/run_a183_canonical_lab.py security-pytest
python -B scripts/run_a183_canonical_lab.py security-audit
```

Os três primeiros são testes de proteção/regressão. `external-red` é requisito de aceite **não resolvido**, com cinco FAIL reais e sem ERROR local. Os testes A182/A183 de caracterização de risco podem passar justamente ao reproduzir uma vulnerabilidade; seus nomes/marcadores deixam isso explícito e não são provas de homologação.

O workflow A184 substitui o workflow comparativo A183 mantendo todas as suítes herdadas, adicionando as quatro novas à Quality e comparando a base exata A183. Inclui dois jobs `adversarial BASE RED`: retém os novos testes fora do checkout, volta ao SHA-base e executa 21 casos de interfaces já existentes. Esses jobs devem falhar de verdade antes das correções; não convertem FAIL em sucesso. Os jobs de candidato e requisitos externos são separados em Ubuntu/Windows; canônicas rodam Ubuntu base/candidato. Não há `continue-on-error`, remoção de testes ou alteração dos critérios de Security. Guardas socket são locais ao processo Python; subprocessos não herdam um firewall. SBOM/browser/deploy não são alegados como executados.

Logs locais de RED→GREEN estão em [evidence/a184](evidence/a184/local-manifest.json). Recuperação original: 7 testes/8 falhas por subcasos; baseline ampliado19 com19 falhas/1 erro de capacidade ainda inexistente. Callback:10/10 FAIL; autoridade:3/3 FAIL. Snapshot: quatro falhas observadas de sidecar e erros adicionais da interface de limites inexistente. Os jobs BASE RED evitam depender dessa interface nova. Chaos original:10/3 FAIL; Convergence original falha ao presumir que a base LAB deve ser main. Foram corrigidos os fixtures/oráculos, mantendo negação de produção e adicionando cenários negativos, não afrouxando o Outbox.

Validação local integrada: **76/76 específicos** (28 A183 + 24 recuperação + 11 snapshot + 10 callback + 3 autoridade), **132/132 herdados**, **93/93 SQLite**, **368/368 Security unittest**, **2.825/2.825 Security pytest**. Primeira Quality local: **6.373/6.373 GREEN** antes do ajuste adicional de DDL; a execução final e a CI remota constam do adendo, sem antecipar sucesso. Audit local: primeira tentativa falhou por cache fora da área gravável; repetição com XDG_CACHE_HOME dentro de work expôs os 43 achados herdados, com logs preservados. Os 21 casos selecionados sobre a base exata deram **25 FAIL reais, 0 ERROR** por subcasos em Linux, sem mascarar o retorno1.

## Exigências externas — trabalho interrompido neste limite

1. **Identidade/bootstrap:** registro independente e aprovado de HUMAN_OWNER/papéis/escopo/chave; desafio de posse vinculado à intenção; raiz inicial distribuída fora do chamador; procedimento de perda/comprometimento sem autoinscrição substituta.
2. **Raiz/rotação/revogação:** cadeia autenticada desde a raiz aprovada, epoch/piso retidos fora do host, rotação com predecessor/quórum autorizado, revogação verificável e prazo máximo de frescor, recusa de raiz substituta/estado antigo. Uma configuração local assinada não satisfaz isso.
3. **Evento/reserva:** identidade de negócio demonstrável, associação imutável ao original, reserva linearizável global antes do efeito, consulta por evento independente de request ID e recibo de commit durável. ACK perdido nunca concede uma nova tentativa.
4. **H0/antirollback:** a testemunha deve sobreviver à perda/restauração simultânea do AION e de seus checkpoints; proibir nova gênese sem cerimônia humana independente; provar monotonicidade/recuperação com falhas e disponibilidade fora do domínio de administração do host.
5. **Recibo/efeito:** produtor autenticado e prova vinculada ao efeito, intenção, escopo, nonce, sequência e tempo, com consulta/revogação externa e prova de ausência com contrato próprio. O recebimento de HTTP/booleano não basta.
6. **Aceite do armazenamento:** documentação SO/SQLite/VFS/backup alvo, prova do handle realmente usado ou substituição de arquitetura explicitamente aprovada, falhas de energia/processo/concorrência e reconciliação no ambiente alvo. Teste unitário verde não homologa esse contrato.

Nenhum desses serviços/cerimônias foi executado, contratado ou provisionado. Os trechos dependentes de autoridade/implantação externa estão parados para **revisão humana**; as frentes internas continuam. Custo contratado adicional: **zero**. Custos futuros de custódia, atestação, provedor e infraestrutura são desconhecidos e exigem estimativa, aprovação explícita e contrato antes de qualquer ação.

Remediações de dependências já existentes permanecem trabalhos separados: Drafts #1445/#1448/#1443. As versões vulneráveis herdadas de pypdf/Pillow não foram substituídas silenciosamente nem os achados omitidos; a execução audit canônica deve expô-los. Não se infere aprovação dessas PRs a partir de seus títulos ou corpos.

## Registro final de execução

[PR Draft #1476](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1476), sobre A183 #1474. **Código, testes e workflows testados: `af5739c010ddf5cb28a64fad5b5c386b96ed2b3c`**. Base comparada: `172be01c5ae665fbbfddb2c4d5dc02f15b77e953`. A atualização posterior deste relatório/matriz/manifestos é documental; não muda fontes, testes, seletores ou workflows.

[CI A184 #39902967998](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39902967998): **FAILURE**. [SQLite histórico #39902967941](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39902967941): **SUCCESS**. Foram lidos **20 logs completos**, com checkouts conferidos, IDs/URLs, hashes e excertos registrados em [ci-verified.json](evidence/a184/ci-verified.json) e nos quatro manifestos detalhados referenciados por ele. Não houve rerun para esconder resultados anteriores.

| Suíte real | Base A183 | Candidato A184 |
|---|---|---|
| Contraexemplos BASE RED Ubuntu/Windows | 21 testes / **25 FAIL reais, 0 ERROR por SO**, sobre a base exata | os mesmos cenários estão na específica, protegidos |
| Específica Ubuntu/Windows | novas falhas reproduzidas | **76/76 por SO**, mesmos nomes, sem skips/erros |
| A176–A182 / Outbox / Saga Ubuntu/Windows | regressões herdadas | **132/132 por SO** |
| SQLite Ubuntu/Windows | histórico preservado | **93/93 por SO**, mais 93/93 por SO no workflow histórico |
| Requisitos externos / SQLite live Ubuntu/Windows | riscos herdados | **5 FAIL reais por SO**, sem ERROR |
| Quality Ubuntu | 6.322 testes / **4 FAIL** | **6.378/6.378** |
| Security unittest Ubuntu | 365 / **3 FAIL** | **368/368** |
| Security pytest Ubuntu | **2.825 PASS** | **2.825 PASS** |
| Security audit Ubuntu | **43 achados**, pypdf6.19.0/Pillow12.3.0 | **mesmos 43**, nenhuma tupla pacote/versão/ID/correção nova ou removida |

As quatro falhas Quality da base são exatamente os três casos Chaos com fixture incompatível com a negação A180 e a expectativa de que `GITHUB_BASE_REF` LAB fosse main. A candidata adiciona quatro módulos A184 ao seletor Quality, **sem remover tokens**. Os seletores Security unittest/pytest são idênticos nas duas revisões. Corrigir o fixture não concedeu autoridade a callbacks operacionais: os novos testes negativos verificam ausência de testemunha/prova, perda de resposta, ausência autoafirmada, reinício e compensação de resultado incerto.

Pip check e compilação passaram nos oito jobs canônicos. O audit conserva 8 achados pypdf e 35 Pillow. Bandit canônico executou sem emitir achados; o harness não registra seu código individual, portanto não há conclusão isolada desse código. Um scan **local adicional** dos quatro arquivos de produção alterados (`bandit -q -lll`) terminou com **exit0**, registrado em [bandit-changed-files-local.json](evidence/a184/bandit-changed-files-local.json); isso cobre só o seletor de severidade alta. Quality local final também executou **6.378/6.378**, com log publicado, após o ajuste de DDL.

Ambientes A184 conferidos: Ubuntu Python3.12.15/SQLite3.45.1 e Windows Python3.12.10/SQLite3.49.1, ambos `deserialize=True`, **`native_fileno=False`**. O workflow SQLite histórico não imprime sua versão SQLite, que não foi inferida de outro job. Local: Python3.12.14/SQLite3.53.1.

**Limites materiais dos logs:**

- Windows informa `OS_DENIED` ou `NOT_EXERCISED` em substituição/ABA A169/A171/A173; não se comprovou que esses casos passaram pela proteção da aplicação. Linux continua reproduzindo `WRONG_FILE_READ_PATH_CHECK_PASSED` em A183. Store vivo não está homologado.
- O marcador stdout `A184_DANGLING_SIDECAR=CAPTURE_DENIED` também aparece no BASE RED, porque `subTest` continua até o print. **Somente assertions, traceback, contagem e exit/job determinam a conclusão**, nunca esse marcador isolado.
- Os cinco requisitos ainda RED são: rollback conjunto custódia+checkpoint; substituição da inscrição original; substituição conjunta de raiz+fingerprint; restore sob mesmo inode antes de leitura; restore sob mesmo inode reabrindo escrita. Não foram reclassificados como expectedFailure, skip ou sucesso.
- Testes que passam ao demonstrar replay local/negócio forjado/raiz auto-configurada continuam identificados como **caracterização de risco**, não proteção comprovada. SBOM, browser, infraestrutura alvo, provedor/autoridade reais, energia e homologação externa não foram testados.

O máximo avanço interno desta rodada está publicado e reproduzível. Os seis gates da seção externa permanecem sem prova, com execução externa interrompida para revisão humana. **Todos os seis P0 ABERTOS; 0/6 efetivamente homologados; HARD NO-GO; ZERO_AUTO_RESEND.**
