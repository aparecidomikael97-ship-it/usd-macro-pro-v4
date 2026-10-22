# AION P0 A143 — Bootstrap SQLite explícito versus reabertura de histórico existente

21/10/2026 (horário local). Draft LAB empilhada sobre #1426 (A142). Sem merge/deploy, credenciais externas, Worker, RESTORE, chamadas pagas ou alterações na main.

## Defeito demonstrado

A142 corrigiu a abertura SQLite comum para `mode=rw` sem recriação IMPLÍCITA depois da checagem. Porém `SQLiteLabReservationLedger.__init__` continuava usando `_initialize()` e `open('xb')` quando o banco não existia, inclusive ao construir uma NOVA instância após apagamento do histórico. Um reinício poderia então receber saldo zero e admitir novamente um run_id usado.

## Mudança A143 (somente LAB)

- O construtor normal `SQLiteLabReservationLedger(lab_dir, checkout_root, limit)` é agora **open-existing**; se o arquivo estiver ausente, retorna `QuotaLabUnavailable` sem criar arquivo ou política nova.
- Criação inicial exige chamada nomeada `SQLiteLabReservationLedger.bootstrap_synthetic_lab(...)`, destinada apenas a um diretório LAB temporário isolado, contendo sintéticos. Não é credencial, assinatura nem autorização de HUMAN_OWNER.
- `bootstrap_synthetic_lab` recusa arquivo pré-existente, inclusive se corrompido; não repara nem zera uma tabela de reservas existente. A abertura comum não aceita registros não íntegros nem alteração silenciosa de limite; travas e URI `mode=rw` das A140-A142 mantidas.
- Testes antigos A140/A141/A142 foram adaptados apenas para realizar bootstrap sintético EXPLÍCITO na preparação do fixture, mantendo os testes adversariais e as suas asserções funcionais. O teste A142 09 passou a negar abertura normal depois do apagamento do banco, substituindo sua antiga expectativa de reset automático.
- O teste A140 de child process que termina abruptamente agora prepara previamente o banco via bootstrap sintético no processo pai; o processo filho somente abre o histórico existente, reserva e usa os._exit. Isso preserva a finalidade original de crash/reopen.

## RED-first e GREEN

- A143 começou com 18 cenários e foi ampliada para 20 após a revisão Codex: normal-open missing, abertura após bootstrap, negação de bootstrap repetido, perda do DB depois de reserva, reabertura após reinício de instância, symlink, corrupção, limites alterados, diretório no checkout e bloqueio de fonte sintética; mais duas demonstrações NEGATIVAS de risco remanescente.
- RED-first [#39699422084](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39699422084) documenta a ausência do novo contrato: construtor admitia bootstrap de DB ausente e método explícito não existia.
- GREEN dirigido [#39699667752](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39699667752): **18 A143 + 11 A142 + 22 A141 + 45 A140 + 30 A139 + 25 A138 + 14 contratos = 165 PASS Ubuntu e 165 PASS Windows, 330 execuções PASS**, sem skips por correção nem waivers.

## HONESTIDADE SOBRE AUTORIDADE

Dois testes deliberadamente NEGATIVOS A143 16/17 demonstram que:

1. Um agente com poder para apagar o arquivo e invocar o método de bootstrap explicitamente poderá iniciar novo histórico local sem distinguir isto de uma primeira instalação.
2. Mesmo sem apagar o arquivo, uma versão SQLite antiga e válida pode ser restaurada e aceita por NOVA instância. `quick_check`, `st_dev/st_ino`, SHA interno e memória da instância não demonstram monotonicidade externa.

Esses testes passarem comprova que o LAB caracterizou a limitação, NÃO que a resolveu. Em produção, genesis, identidade do arquivo/epoch e avanço da sequência exigirão witness externa independente, política de enrollment, readback e custódia de chaves fora do mesmo repositório/host.

A143 tampouco fecha a janela ABA de path swap ou comprova recibo de efeito/no-effect de fornecedor, autenticação HUMAN_OWNER ou revisão de credenciais. Nenhum P0 é homologado. Nenhum dado fresco de mercado foi coletado.


## Auditoria independente Codex e janela entre criação exclusiva e leitura do destino

O Codex no Windows recebeu somente cópias de código/teste da Draft em TEMP, executou auditoria estática `read-only`, sem modificar arquivos e sem chamar fornecedores. Encontrou que `_initialize()` criava o arquivo com `Path.open('xb')`, fechava o handle e só DEPOIS fixava a identidade pelo pathname. Um segundo banco SQLite válido podia ser colocado no caminho entre esses pontos; a versão antiga aceitava o conteúdo como se fosse instalação nova.

- **RED-first test_19** [#39700248128](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39700248128): a substituição sintética por banco válido preexistente foi aceita pela versão anterior no Ubuntu (`FAIL: QuotaLabUnavailable not raised`). O teste também contém asserção explícita de que a injeção ocorreu.
- **Correção**: capturar `(st_dev,st_ino)` a partir de `os.fstat` do handle da criação exclusiva ANTES de fechá-lo; comparar com o objeto do destino, exigir arquivo ainda vazio antes de inicializar, e exigir `sqlite_master` vazio no bootstrap sintético. Isso reduz a aceitação de um SQLite preexistente durante a janela de inicialização.
- **Portabilidade Windows**: o teste original comparava o caminho de criação com o path lexical de TEMP; em Actions Windows o alias curto (`RUNNER~1`) podia diferir de `Path.resolve()`, fazendo o teste deixar de injetar a troca. O fixture passou a interceptar o `open('xb')` efetivamente executado e `assertTrue(swapped)` antes de validar a negativa. É correção do mecanismo adversarial, não waiver.
- **GREEN com ataque efetivamente injetado**: [#39700845654](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39700845654), A143 ampliado para **20 cenários** (inclui o teste 20 de arquivo parcialmente inicializado recusado). As 6 suites: 20 A143, 11 A142, 22 A141, 45 A140, 30 A139, 25 A138 e 14 de contrato = **167 PASS Ubuntu +167 PASS Windows =334 PASS**.
- Foi reforçado o teste A143 07: agora efetivamente chama `collect_synthetic_market` com quota indisponível e demonstra `BLOCKED_NO_PROVIDER_FETCH`, em vez de apenas verificar lista vazia de chamadas em um mock não invocado.

**Ainda sem garantia atômica de handle:** `stat` e `sqlite3.connect` em pathname podem ser alvo de swap ABA sob host privilegiado; atributos locais não substituem um registro independente de genesis/epoch/sequence. A143 não cria credencial de autoridade: `_explicit_synthetic_bootstrap` é parâmetro convencional Python para LAB e um chamador com acesso ao host pode solicitar bootstrap. O teste 16 mantém a vulnerabilidade visível. A interrupção entre `xb` e primeiro COMMIT pode deixar um banco parcialmente criado, bloqueado conservadoramente até remediação autorizada.

## Estado final

O pacote A143 corrige dois pontos pontuais no LAB: (a) reabertura normal não autoriza nova inicialização e (b) genesis rejeita um SQLite preexistente substituído sob as condições testadas. Não é prova de reabilitação do Global Worker, recuperação contra rollback entre boots ou efeito de fornecedor. Quality e Security canônicas rodam no HEAD definitivo sem alterações na seleção e sem waivers. HARD NO-GO / 0 de 6 P0 homologados.

**HARD NO-GO · 0/6 P0 homologados · Worker OFF · ZERO_AUTO_RESEND.**