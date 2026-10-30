# A321 — Reconciliação de cabeças assinadas e detecção de histórico divergente (LAB)

**HARD NO-GO · ZERO_AUTO_RESEND · P0 homologadas 0/6 · nenhum merge, Worker operacional, deploy, provedor, ordem ou gasto novo.**

## Por que precisamos da A321

A320 validou 316 testes por plataforma no Ubuntu e no Windows, incluindo a consistência de dois comprovantes sintéticos de custodiantes, sempre sem atestar a origem externa. Ficou demonstrado que até duas chaves distintas podem ser criadas no mesmo host e apresentadas como se fossem duas autoridades. A A321 adiciona uma checagem importante: **comparar históricos de high-water ao longo de múltiplos passos e detectar documentos assinados que entram em contradição entre si**.

Ela não liga para nenhum serviço externo. Chaves, certificados, recibos, cabeça inicial, desafios e relógio dos testes continuam todos na mesma execução sintética.

## Contrato do LAB

Arquivo `labs/a321_signed_high_water_fork_detection_lab.py`:

- Recebe um **dossiê A320** completo e reexecuta o verificador A320 (que, por sua vez, reexecuta a A319), nunca confia em um `"PASS"` enviado pelo chamador.
- Exige referência inicial com geração, época de incidente, sequência e hash iguais aos registrados no precommit A320 — ainda **não autenticado externamente**.
- Recebe de 1 a 4 etapas sequenciais, cada uma com **dois relatórios Ed25519 reais** de custodiantes diferentes, conforme as duas chaves declaradas no dossiê A320.
- Cada relatório vincula geração, época, sequência, sequência anterior, SHA-256 da cabeça anterior, novo hash, digest da intenção, nonce, validade e `decision=HOLD_ONLY`.
- Os dois signatários precisam concordar exatamente quanto ao histórico daquela etapa, e cada etapa deve avançar uma unidade a partir da cabeça anterior, com nonce diferente por etapa.
- Uma declaração adicional assinada por um custodiante, com **mesma sequência e outra cabeça**, é identificada como `SIGNED_HIGH_WATER_EQUIVOCATION`; cópia extra idêntica é recusada como replay não solicitado.
- Recusa assinatura falsa, raiz desconhecida, mesma identidade duas vezes, geração/época reaberta, rollback/skip, cabeça anterior incompatível, relógio expirado, nonce reutilizado, campos de GO injetados ou custodiante declarado revogado.
- Há limite rígido no número de etapas e de relatórios extras, sem loops ilimitados, banco operacional ou reenvio.

Saídas:

- `LAB_CONSISTENT_SIGNED_HISTORY_NO_EXTERNAL_CUSTODY`: duas assinaturas por etapa e cadeia local matematicamente coerentes. **Não é autorização.**
- `LAB_HIGH_WATER_VETO`: incompatibilidade, assinatura falsa, fork ou replay detectados. **Não é autorização.**

Ambos sempre reportam `off_host_high_water_authentic=False`, `actual_custodians_independently_identified=False`, `external_pin_independently_authenticated=False`, `immutable_custody_proven=False`, `provider_ack_verified=False`, `can_resume=False`, `can_resend=False`, `can_auto_retry=False`, `hard_no_go=True`, `zero_auto_resend=True`, `p0_homologated=0`.

## Contraprova principal: reescrever tudo

Se o operador do mesmo computador controlar o banco, o dossiê A320, os dois pares de chaves e os registros de high-water, ele pode reconstruir **uma cadeia inteira aparentemente coerente**, inclusive após reduzir sua sequência inicial. Os testes exigem que essa falsificação passe *somente nas verificações matemáticas* e continue reportando ausência de custódia independente. Esse é o risco central que impede a homologação das P0-3/P0-4.

A A321 **não** prova que dois custodiante(s) existem, que as assinaturas chegaram por canais separados, que houve testemunha externa anterior ao ataque ou que a cabeça declarada foi guardada fora do host. Uma divergência só pode ser detectada se **ambos os relatos conflitantes estiverem disponíveis**; um atacante que consiga suprimir todos os relatos externos continua fora do alcance deste laboratório.

## Uso futuro e restrição financeira

A verificação real exigiria, no mínimo, fontes independentes previamente autenticadas para chaves públicas, nonce e high-water; uma maneira de consultar essas referências antes de qualquer efeito, proteção contra a supressão das provas conflitantes, reconciliação de ACK do provedor e política explícita de congelamento diante de disputa. Nenhuma fonte, hardware ou serviço novo foi escolhido, contratado ou conectado.

Até existir uma decisão sobre como custodiar a primeira raiz fora do computador, podemos continuar testando o contrato, mas não homologar nenhuma P0.

## Validação

```sh
python -m unittest -v labs.test_a321_signed_high_water_fork_detection_lab
```

GitHub Actions Ubuntu e Windows (Python 3.12, `cryptography==46.0.4` no runner): 36 testes A321 e regressões A320–A299, incluindo a prova de UID Unix no Ubuntu. Nenhuma alteração ao `aion_chat/store.py`. PR rascunho empilhada sobre A320.
