# A124 — testemunha sobrevivente ao restore local (somente simulação)

Este laboratório **NÃO** é serviço de custódia nem solução de segurança homologada. O código usa **RAM do mesmo processo**, locks de threads e HMAC de teste; a matrícula é uma flag fictícia. Ele não realiza nenhuma ação externa nem SMS. O AION produtivo/Outbox/Saga não é modificado.

## Executar

Partindo da raiz do pacote, com Python 3.13 e biblioteca padrão:

```sh
python -W error -m unittest discover -s labs/a124_surviving_witness_offline -p 'test_witness.py' -v
python -W error -m unittest discover -s labs/a123_receipts_offline -p 'test_contract.py' -v
```

**Teste propositalmente RED (esperado exit 1)**, executar separadamente:

```sh
python -W error -m unittest discover -s labs/a124_surviving_witness_offline -p 'red_baseline.py' -v
```

Em GitHub, a branch filha contém o diretório `labs/a123_receipts_offline` do commit A123. O ZIP independente inclui `contract.py` e `test_contract.py` da A123 **sem alterações**. Esta dependência é deliberada para não duplicar o motor legado no repositório.

## Interpretação correta

- A124: **31/31 PASS**, mas #25, #26 e #30 foram escritos para passar **quando reproduzem exploração do laboratório** (co-rollback total, witness falso e bypass do guard).
- A123: **38/38 PASS** local, mas #35 reproduz a falha ao restaurar os dois SQLite.
- RED A124: **1 FAIL esperado**; sem witness sobrevivente, o par A123 aceita a segunda chamada fake.
- Nenhum desses resultados comprova custódia externa, autonomia, assinatura real, F1/T1/H0/F2, hospedagem CI, Windows ou efeitos reais.

Leia `A124_ARCHITECTURE_AND_EXIT_GATES.md` para os 10 critérios de saída ainda ABERTOS.
