# AION Biblioteca — Ensaio de restauração real de identidade + ACL com testemunha separada (Sandbox)

**Estritamente sandbox, não montado no app.** Complementa [#501](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/issues/501), [#507](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/issues/507), #502. Sem alterações do login V1, ACL V1, workflows protegidos, main, Render ou dados de clientes.

## Escopo exato do ensaio

No CI opt-in com `CI=true`, `AION_LIB_RESTORE_DRILL=1` e DSN igual **exatamente** ao PostgreSQL sintético efêmero já utilizado no workflow atômico, criar três bancos temporários adicionais no mesmo servidor PostgreSQL 16:

- `aion_library_identity_source_ci`: registry de identidades duráveis SANDBOX + ACL V2 SANDBOX, povoado com identidades e concessões inteiramente fictícias.
- `aion_library_identity_restore_ci`: alvo descartável vazio para **`pg_dump -Fc` e `pg_restore` REAIS**, restritos às duas tabelas de identidade+ACL, nunca dados/PDFs de terceiros.
- `aion_library_retirement_witness_ci`: histórico de revisões externo **ao backup das duas tabelas**, consultado somente pela nova porta read-only `SeparateDatabaseWitnessReader`. O novo SQL é DDL documental e só é executado pelas fixtures estritamente sintéticas. As conexões de leitura têm papéis SQL específicos sem privilégios de escrita.

`ExternalRetirementFence`, desenvolvido e testado na #508, exige um head **atual** desse banco lógico separado e piso de revisão monotônico fornecido por **outra fonte**. Nestes testes, a fonte do piso é uma variável independente **em memória**; portanto o CI comprova apenas os comportamentos do contrato, não uma âncora durável independente.

## Casos exigidos

Testes offline em `test_atlasquant_aion_library_acl_postgres.py` verificam seleção ordenada da revisão mais recente, transação read-only, recusa a linhas ausentes, adulteradas, duplicadas, fora de ordem, falhas e scopes inválidos. Os testes PostgreSQL em `test_atlasquant_aion_library_acl_postgres_pg.py` devem executar `pg_dump/pg_restore` real das tabelas de registry+ACL e demonstrar:

1. Dump de A com grant; A é aposentado, B recebe nova geração/regrant e o witness mantém revisão atual B **fora do dump**. A restauração reconstitui A e sua concessão antiga em banco separado; A e B continuam bloqueados pela combinação registry/fence/witness até reconciliação explícita de B e concessão nova.
2. Witness registra aposentadoria de A após o dump: o banco restaurado mostra A ativo, mas a leitura com witness recente nega.
3. Histórico da testemunha perde a revisão nova: o piso separado mais recente impede o head antigo de aprovar A. Se **os dois** forem revertidos juntos, o contrato sozinho não tem como detectar o ataque.
4. Testemunha indisponível: negar sem fallback; arquivo de dump alterado: rejeitar por digest antes do restore (o digest nestes testes é apenas sintético, não atestado externamente).
5. Papel SQL de leitura da testemunha não consegue `DELETE` nem `INSERT`.

## Proteções do próprio ensaio

O código de teste exige o **DSN sintético literal**, habilitadores explícitos de CI e de restore, nomes de banco fixos e lista fechada de comandos/ferramentas; não recebe DSN, banco, arquivos ou credenciais do usuário. `docker run postgres:16` segue o padrão do ensaio de recuperação documental já existente; as senhas do código são exclusivamente fictícias do serviço efêmero, jamais segredos produtivos. O cleanup descarta apenas os três bancos CI exclusivos.

## O que NÃO está comprovado

Os três bancos estão **no mesmo servidor PostgreSQL CI**: separação é **lógica**, não uma segunda região, segundo serviço/operador, WORM, HSM, backup realmente offsite ou domínio de falha independente. O piso é memória efêmera. Não há emissão real de identidades, gravação monotônica irreversível, assinatura/autenticidade/frescor externos, auditoria de plano privilegiado, restauração PITR com revogações pós-backup reais, RPO/RTO produtivos ou garantia criptográfica de custódia do arquivo sintético. A integração entre callback de identidade e login V1 segue bloqueada.

**Próximos gates:** autoridade externa de verdade e trilha imutável/floor persistente (#507), ensaio offsite independente de DR com RPO/RTO auditado (#501), gatilhos PG/E2E main-based (#499), branch protection (#325), direitos/licenças/LGPD/custódia e auditoria independente (#477). Nunca promover o resultado deste laboratório para autorização de merge, migração, deploy, produção, segredos, clientes ou PDFs reais.
