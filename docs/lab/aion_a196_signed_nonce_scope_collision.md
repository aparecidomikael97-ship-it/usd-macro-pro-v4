# AION A196 — colisão de identidades no registro de nonce assinado (LAB)

**27/10/2026. Draft para revisão, sem merge/deploy. 0/6 P0 homologadas; HARD NO-GO.**

## Falha concreta

O verificador real `atlasquant_aion_authority_verifier.py` calcula o
`scope` de proteção de repetição com `"|".join((authority_id,subject_id,
tenant_id,domain,policy_id))`. Antes, um identificador podia conter
`|`, tornando duas tuplas diferentes indistinguíveis. Exemplo:

- `authority_id="a|b", subject_id="c"`
- `authority_id="a", subject_id="b|c"`

Ambas produzem a **mesma string de escopo** e podem disputar um registro de
nonce no SQLite real. Isso permite colisão/negação indevida. **Não é prova
de falsificação de assinatura digital**, nem demonstra uma invasão remota:
depende de aceitar tais valores em statements emitidos/autorizados.

## Correção mínima proposta

Bloquear `|` em cada um dos **cinco** campos que compõem o escopo do
nonce `authority_id, subject_id, tenant_id, domain, policy_id`, antes
de validar assinatura ou gravar nonce. Registrar bloqueio sanitizado
`AUTHORITY_NONCE_SCOPE_DELIMITER_RESERVED:<field>`, com saída fail-closed.

Não reformatear a chave nem limpar/regravar o registro SQLite existente:
migrar silenciosamente para outra codificação poderia **reabrir nonces**
previamente usados. Os statements antigos com campos ambíguos passam a
ser recusados. Em uma futura migração explícita, preservar exclusão
semântica é uma tarefa distinta com testemunho externo.

## Verificação

Usa a implementação real de assinatura **Ed25519** e verificador
`verify_authority_statement` com chaves **100% sintéticas efêmeras** e
`PersistentNonceRegistry` sobre SQLite local temporário. Os testes
reproduzem a colisão na serialização antiga, verificam rejeição de cada
campo ambíguo, assinatura legítima, replay, persistência após reabrir
SQLite, isolamento por escopo, bloqueio de chave desconhecida e negativa
mesmo com `expected_binding` manipulado. Windows + Ubuntu.

`python -B -m unittest -v labs.test_a196_signed_authority_nonce_scope_lab`

## Limite fundamental RED

Assinatura sob chave publicamente fornecida pelo próprio chamador
**não** comprova origem independente HUMAN_OWNER. SQLite local não
assegura irreversibilidade contra rollback nem reserva atômica do
efeito externo. Este ajuste não fecha nenhuma das seis P0, não altera
G122 externa (cinco RED por SO) e não autoriza Worker, trading, ordem,
provider SEND, AWS, registro de chaves, custódia, conta ou cobrança.

Negócios congelado pela decisão do proprietário de 27/10/2026.
Até 05/11/2026 não contratar novos serviços nem assumir novos custos;
a partir de 06/11 só reavaliar após autorização explícita.
