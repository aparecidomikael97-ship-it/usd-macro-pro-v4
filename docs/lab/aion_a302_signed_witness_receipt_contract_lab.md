# A302 — Comprovantes assinados de testemunhas para recuperação (LAB)

**HARD NO-GO · ZERO_AUTO_RESEND · 0/6 P0 homologadas · nenhum custo novo.**

## Escopo

Experimento isolado, sobre A301, com Ed25519 em Python. Não altera o AION operacional, não restaura bancos, não usa credenciais reais, não chama provider/Worker, não faz deploy e não envia ordens ou mensagens. As duas chaves privadas de teste são geradas **no próprio processo de CI** e não são identidade independente.

## Avanço demonstrado

O verificador compara:
- Um manifesto compatível com a estrutura A301 (conteúdo do banco, histórico, intenções, geração, pendências);
- Duas testemunhas com identificadores distintos e chaves públicas fixadas pela aplicação experimental;
- Assinaturas Ed25519 sobre mensagem canônica com separador de domínio;
- Mesmo hash de manifesto, nonce de desafio e sequência esperada;
- Hash do comprovante anterior, conforme cabeçalhos anteriores fornecidos pelo chamador;
- Avaliação A301 que reconheça somente coerência local, **nunca** retomada.

Recusa assinatura falsa, testemunha sem chave reconhecida, chave repetida, recibo ausente, manifesto alterado, nonce incompatível, sequência anterior, histórico A301 inconsistente e campos inesperados. Não expõe chave privada em arquivos de projeto.

## Contraprova fundamental

É possível produzir duas assinaturas Ed25519 **criptograficamente válidas** para um manifesto antigo se o invasor controlar também as chaves e os cabeçalhos de sequência. Portanto o verificador informa `cryptographic_receipts_verified=True` em fixtures coerentes, mas mantém:

- `independent_authority_authenticated=False`;
- `independent_custody_verified=False`;
- `trusted_heads_off_host_verified=False`;
- `can_resume=False`;
- `can_authorize_real_effect=False`;
- `hard_no_go=True`.

**Duas assinaturas não são duas autoridades independentes.** Uma futura homologação precisará testar provisionamento das chaves e âncoras fora do host, custódia imutável, revogação, recuperação e reabertura de incidentes. Um campo `verified: true` vindo do mesmo computador não serve.

## Limitações

O A302 verifica apenas contratos e assinaturas de dados sintéticos. Ele não comprova que uma chave seja do proprietário, que a fonte seja externa, que o registro seja durável, que um provedor executou uma intenção, que o hash de um snapshot contenha o WAL ou que exista identidade FD/VFS confiável. O parâmetro `a301_assessment` é um **resultado fornecido pelo chamador**; neste ensaio não há raiz de confiança independente capaz de autenticá-lo. Nenhuma P0 é homologada.

## Testes

`python -m unittest -v labs.test_a302_witness_receipt_contract_lab`

18 testes específicos, mais as regressões A301–A300–A299–A293–A292 em Ubuntu e Windows. A dependência Python `cryptography` é software aberto de teste, sem nova assinatura ou serviço pago. **CI verde = LAB somente.**
