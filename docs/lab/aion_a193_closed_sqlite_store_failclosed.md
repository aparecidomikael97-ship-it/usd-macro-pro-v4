# A193 — SQLiteChatStore fechado deve negar acesso sem erro imprevisto

**27/10/2026 · Draft LAB review only · 0/6 P0 homologadas · HARD NO-GO.**

## Contexto e defeito reproduzido no A192

O código real `aion_chat/store.py` deixa `self.db=None` depois de `close()`.
Algumas entradas de leitura e gravação acessavam o handle fechado diretamente.
No A192, o teste de `get_conversation` fechado produziu `AttributeError:
'NoneType' object has no attribute 'execute'` em ambos os sistemas.
Esse bug gera erro imprevisto em lugar de `StorageUnavailableError`; não demonstra
vazamento de dados, trade, efeito externo nem é prova de P0 real.

## Mudanças propostas (NÃO mescladas)

- `get_conversation()`: verificar primeiro `self._scope(scope)`, que
  chama `_require_open()`, **antes** do acesso a `self.db.execute`.
- `archive_conversation()`, `add_attachment_metadata()`,
  `save_checkpoint()` e `save_context_summary()`: chamar
  `_require_open()` antes de abrir o contexto `with self.db`.
- Sem novos providers, imports externos, flags, APIs, criptografia, IAM, contas,
  armazenamento adicional, migração SQL, Worker ou mudanças de schema.

## Provas locais de escopo estreito

Testar com `python -B -m unittest -v labs.test_a193_sqlite_store_closed_failclosed_lab`:
operações diretas de consulta/listagem/busca, leitura/gravação de mensagem,
arquivamento, anexos, checkpoints, resumos, recuperação, backup, WAL,
saúde do store e reabertura por uma nova instância. Synthetic/tempfile apenas;
Windows e Ubuntu. Entrada fechada deve lançar consistentemente
`StorageUnavailableError`, sem voltar silenciosamente para outro escopo.

## Não mascarar riscos críticos

Há duas demonstrações RED **intencionais**, mesmo com CI da regressão verde:

1. A estrutura `aion_chat.models.Scope` continua forjável por caller Python
   com acesso ao handle SQLite. O STORE NÃO autentica identidade do usuário.
2. `atlasquant_aion_chat_product_bridge.validate_product_binding` classifica
   como 'BOUND' um `access` sintético com flags/role/permissions inventados.
   Por contrato, ele espera uma decisão **já autenticada pelo host**, não
   valida senha/sessão; isso não é uma prova de exploit em uma implantação real,
   mas demonstra a dependência de origem confiável **ainda não verificada**.

**Para resolver isso de verdade:** rastrear o entrypoint, login e sessão
de ponta a ponta; verificação de sessão atual no backend,
RBAC/ABAC, não aceitar campos de cliente, revogação, custódia independente,
acesso ao armazenamento e testes adversariais end-to-end.

## Restrições do proprietário

- Negócios congelado desde 27/10/2026; nenhum desenvolvimento da vertical,
  implementação de piloto, outreach ou serviço pago.
- Até 05/11/2026, **zero contratação ou gasto novo**. A partir de 06/11/2026,
  revisar proposta financeira apenas sob aprovação expressa, sem autorização automática.
- Sem AWS, merges, deploy, Worker, SEND, ordens reais ou alteração no P0 ledger.
- A190/G122 (5 RED externos/nativos em cada OS) não deve ser alterada pelo G143.
