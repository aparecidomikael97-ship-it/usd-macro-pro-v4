# AION overnight core hardening — 2026-09-30

## Objetivo

Endurecer o núcleo AION em contratos, isolamento, evidência, observabilidade
e recovery, sem ativar runtime, provider, worker, pagamento, publicação ou
trading.

## Base

- SHA da main no início: `ba50e91804c71b0d2ff6a1f52979cc1a687792ff`
- Branch: `cursor/aion-overnight-core-hardening-v2-8499`
- A main não foi editada.
- Suíte local `python3 -m unittest discover`: 3857 testes, OK, sem regressão
  depois do ajuste de timestamp futuro no recall.

## O que este bloco fecha

- Allowlist de scopes por especialista. O grant efetivo é a interseção de
  allowlist, pai, guardião e runtime. Camada ausente não concede scope.
  `*` não significa acesso irrestrito. Os perfis futuros continuam com
  `runtime_capability_available=false` e `NOT_CERTIFIED`.
- Certificação exige eco do verifier para especialista, versão, suíte e
  `evidence_id`, recusa fingerprint de outro especialista ou versão, refs
  acima do teto, verifier que lança ou devolve formato inválido, e mantém
  `REVOKED` / `SUSPENDED`. Revisão humana continua sendo só o booleano `True`.
- Memória: contexto tenant/workspace/actor/task não vaza; timestamp inválido
  ou futuro não entra como fato atual; `CONFIRMED` truncado volta a
  `UNKNOWN`; digest divergente, schema ou versão errados não são íntegros.
- Postura read-only: observabilidade sem inventar `HEALTHY`, flags com bool
  exato e immutable-off, estágios de release que permanecem `DISABLED`,
  plano de rollback que não executa, trilha de auditoria que não autoriza,
  fallback de provider sem chamada e sem dado inventado, envelope de
  contrato fail-closed, teto de retry do executor local já existente.

## Arquivos

Criados:

- `atlasquant_aion_core_posture.py`
- `test_atlasquant_aion_core_posture.py`
- `docs/continuidade/AION_OVERNIGHT_CORE_HARDENING_2026-09-30.md`

Modificados:

- `atlasquant_aion_specialist_router.py`
- `atlasquant_aion_specialist_certification.py`
- `atlasquant_aion_memory_layers.py`
- `test_atlasquant_aion_specialist_certification.py`
- `test_atlasquant_aion_memory_layers.py`
- `.github/workflows/quality-tests.yml`
- `docs/aion/ARCHITECTURE.md`
- `docs/aion/AION_SPECIALIST_CERTIFICATION_V1.md`

## Revisão do diff

Sem chamada de rede, subprocesso, `eval` ou `exec` nos módulos desta missão.
O verifier que lança exceção fica em falha fechada e marca `verifier_error`.
Runtime dos perfis futuros só aceita `available is True`. Listas de autoridade
e refs de evidência ficam com teto. Truncar duplicata de memória não torna o
checkpoint íntegro.

## O que continua pendente

- Runtime de Trader, Business e Investments permanece desligado.
- Nenhum especialista está certificado por este registro.
- Não houve varredura que reescreva todo `bool(value)` histórico do
  repositório. Os contratos novos e o gate de certificação usam bool exato.
- O executor local já limita tentativas; o worker global não foi ligado.
- Rollback pronto no contrato não restaura checkpoint.
- SHA de produção continua não verificado.
- Não há ADR novo. ADR-0001, ADR-0005 e ADR-0010 continuam cobrindo o núcleo,
  a ausência de permissão independente e os quatro fechamentos.
- O Checkpoint Mestre não foi promovido de `IMPLEMENTADO / EM VALIDAÇÃO`
  para `VALIDADO`.

## Fora deste bloco

Estratégia de mercado, Average Daily Range, ATR, American Depositary
Receipts, CRM real, Opportunity Scout real e interface.
