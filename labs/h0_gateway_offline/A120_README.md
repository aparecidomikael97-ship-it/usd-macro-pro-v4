# A120 — contraexemplos externos ao contrato do gateway offline A119

A120 **não é um patch** e não altera o código da A119. Inclui 5 cenários que **reproduzem falhas abertas** (um teste `OK` significa que o defeito de laboratório foi observado), preservando a suite anterior de 24 testes. Ver relatório `A120_COUNTEREXAMPLES_AND_EXIT_GATES.md` para as condições de saída; nenhum resultado é homologação de H0/F1/T1.

```bash
python -m unittest discover -s labs/h0_gateway_offline -p 'test_*.py' -v
```

Sem rede, credenciais, conta, SMS, trabalhador, arquivo real de clientes ou deploy. Worker fica OFF. `production_worker_eligible()` sempre devolve `False` no espécime.
