# AtlasQuant Negócios V1.1 — laboratório de contrato

**PROTÓTIPO OFFLINE / NÃO HOMOLOGADO / NÃO É O CRM PRODUTIVO.**

Este pacote contém especificação do fluxo, campos, telas e regras de operação do complemento didático V1.1 e **45 testes sintéticos** de um oráculo Python puro. Nenhum módulo produtivo é importado, nenhum dado real é utilizado e não há rede, banco, email, WhatsApp, fornecedor, cobrança, reserva de estoque, credenciais, Worker ou ativação do AION.

## Arquivos

- `ESPECIFICACAO_TECNICA_V1_1.md`: contrato de produto, regras, telas, limitações e critérios de aceite.
- `contract.py`: avaliador de regras/alertas de fichas fictícias; ações externas sempre recusadas. **Não contém autenticação ou API**, não deve ser ligado ao produto.
- `test_contract.py`: 45 testes unitários sintéticos independentes.

## Rodar os testes

Da raiz do repositório:

```bash
python -m unittest discover -s labs/negocios_operational_v11 -p 'test_*.py' -v
```

Se estiver em um diretório independente, use `python -m unittest discover -s . -p 'test_*.py' -v` de dentro da pasta do laboratório.

**HARD NO-GO:** resultado verde valida apenas comportamento local de funções sob premissas fictícias. Não confundir com conformidade LGPD, prova bancária, saldo de estoque, isolamento real de tenants, segurança de produção ou homologação do Núcleo. O conteúdo foi criado sem modificar a `main`, sem PR produtiva e sem alterar o manual original.
