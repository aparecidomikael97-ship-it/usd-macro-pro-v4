# USD Macro Pro V11.0.6

## Strength Attribution + Audit Integrity

Objetivos desta versão:

1. corrigir falhas de integridade reproduzidas pela auditoria técnica;
2. impedir `EXECUTÁVEL` quando dados, timestamps, risco, mapa ou gatilho não estão confirmados;
3. invalidar sinais técnicos do lado antigo quando a direção macro muda;
4. tornar a explicação de força entre moedas uma conta auditável;
5. preservar pesos e Score Mestre.

### Nova leitura da força

A interface passa a exibir:

- Macro puro
- efeito Fed
- ajustes do modelo
- força final
- fatores a favor da base
- fatores a favor da cotada
- saldo líquido final

### Segurança operacional

A V11.0.6 é mais conservadora. Na dúvida, dado ausente/antigo/desconhecido bloqueia execução em vez de assumir condição favorável.

### Validação

Foram adicionados:

- `test_audit_integrity_v1106.py`
- `test_strength_attribution_v1106.py`

O workflow `Quality tests` foi atualizado para incluí-los.
