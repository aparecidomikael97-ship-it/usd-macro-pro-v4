# A303 — Custódia de chave-raiz e sequência de incidentes (LAB)

**HARD NO-GO / ZERO_AUTO_RESEND / 0 de 6 P0 homologadas / sem custo novo.**

## Mudança em relação à A302

A302 validou duas assinaturas Ed25519 fictícias de testemunhas sobre a mesma intenção, com sequência e hash anterior informados localmente. A303 acrescenta, apenas em pesquisa, uma **terceira assinatura** de um custodiante sintético sobre os vínculos que deveriam ser protegidos fora do host:

- Identificação da chave-raiz previamente conhecida e escopo do proprietário;
- Identificação da fonte, conversa e geração do manifesto A301;
- Hash SHA-256 canônico do manifesto A301;
- Hash das duas chaves públicas das testemunhas (keyset);
- Hash dos dois heads/últimos registros informados ao A302;
- Nonce do desafio, contador da âncora, hash da âncora anterior;
- Geração do incidente e época das chaves (para recusar estados antigos).

**Os 3 segredos são gerados no mesmo runner de teste.** Não há independente homologado. O verificador distingue:
1. `cryptographic_anchor_verified`: assinatura Ed25519 válida;
2. `a302_receipts_verified`: duas assinaturas A302 válidas;
3. `local_package_consistent`: assinaturas, keyset, histórico e contadores coerentes com os parâmetros recebidos;
4. `independent_root_proven=False`, `off_host_monotonic_floor_verified=False`, `can_resume=False` **sempre**.

## Controles negativos de regressão

- Assinatura da âncora adulterada, chave raiz trocada, ID do custodiante não reconhecido;
- Escopo do proprietário incompatível e geração do manifesto alterada;
- Chave pública de testemunha substituída sem nova autorização;
- Head da testemunha alterado, recibo ausente, nonce trocado;
- Contador de âncora antigo ou salto de sequência e hash anterior divergente;
- Reabertura de incidente e rotação de época de chaves que invalidam recibo anterior;
- Chave do custodiante idêntica à de uma testemunha, rejeitada;
- **Contraprova de recuperação da confiança:** se todas as chaves, pins e cabeçalhos forem refeitos pelo próprio host, o conjunto de assinaturas pode voltar a ficar matematicamente consistente, mas a identidade e a sequência REAL continuam não autenticadas. Nenhuma operação liberada.

## O que este LAB NÃO prova

- Que a chave privada foi gerada ou guardada em dispositivo externo, por pessoa ou entidade autônoma;
- Que há registro monotônico durável e imutável fora do host;
- Que uma rotação de chave foi autorizada por titular confiável ou que a revogação foi consultada;
- Que o validador A301 e o hash correspondem a dados obtidos independentemente;
- Que o FD/VFS SQLite é confiável, que o WAL está íntegro, ou que um fornecedor executou um efeito;
- Que `pinned_root_public_key`, `previous_anchor_hash` e os pisos de geração são confiáveis: no LAB são fornecidos pelo próprio chamador.

Até haver verificação dessas propriedades, **nenhuma assinatura local se transforma em autorização**. A302/A303 não fazem backup/restore operacional, Worker, deploy, ordens, reenvio ou chamadas de rede.

## Execução

`python -m unittest -v labs.test_a303_custody_anchor_chain_lab`

21 testes A303 e regressões A302, A301, A300, A299, A293, A292 em Ubuntu e Windows. Python 3.12, biblioteca livre `cryptography` instalada apenas no CI. PR draft empilhada sobre A302, sem merge; verde significa GO-LAB de pesquisa, **não** integração ou homologação P0.

## Próximo critério verificável

Precisamos de um compromisso de confiança fixado fora do computador do AION e de uma prova independente de custódia/monotonicidade, **sem presumir que GitHub, outro processo local ou uma chave gerada na CI constituam autoridade do titular**. Provas reais futuras dependem de autorização e validação separadas; nada é contratado agora.
