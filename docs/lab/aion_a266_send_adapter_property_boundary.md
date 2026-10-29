# A266 — Não acessar adapter.send antes da reserva de primeira tentativa

**Apenas laboratório · HARD NO-GO · 0/6 P0 homologadas · sem merge, Worker, deploy, efeitos externos ou custos novos.**

## Vulnerabilidade concreta após A265

A265 removeu callbacks de reconciliação do `ExecutionOutbox` normal, mas a rotina `dispatch_claimed` continha `send = getattr(adapter, "send", None)` **antes** de gravar o marcador de tentativa potencialmente ambígua, antes da reserva de primeira tentativa e antes da revalidação CAS do lease.

Em Python, um atributo fornecido pelo chamador pode ser uma propriedade `@property` ou um `__getattribute__` malicioso. Assim, **apenas verificar se `send` existe** pode executar código do host, abrir conexão, consultar serviço ou produzir outros efeitos, embora `_reserved_first_attempt` do Outbox normal sempre retorne `False`. Marcar `UNCERTAIN` e impedir `send()` depois não protege desse acesso prematuro.

## Correção aplicada

- O `getattr(adapter, "send", None)`, sua checagem `callable` e a chamada real `send(...)` foram movidos para **depois** da gravação durável de `UNCERTAIN`, da tentativa de reserva e do CAS subsequente de lease. Tudo fica no mesmo bloco `try` que trata erro de callback como resultado ambíguo e nunca reenvia automaticamente.
- Se não existir reserva independente (caso normal), o método **retorna antes de consultar qualquer atributo do `adapter`**. Uma propriedade perigosa não é acessada. A ausência de `adapter.send` no ramo sintético permitido passa a conservar `UNCERTAIN` como posição segura, não relançar uma exceção após tocar na fronteira potencial.
- O simulador LAB `SyntheticFirstAttemptOutboxLab` continua permitindo uma reserva `True` propositalmente insegura **somente para testes offline**, não para produção. A propriedade `send` só será acessada depois das barreiras locais.
- O parâmetro `authorize` e o callback opcional `cumulative_authority_guard` ainda são invocados **antes** da reserva. **A266 não demonstra isolamento de todo callback host-controlled**; isso é assunto separado que deve ser tratado em LAB e com protocolo de autorização confiável.

## Testes específicos

`labs/test_a266_send_adapter_property_boundary.py`: 11 testes com contadores sintéticos e zero rede: propriedade `send` comum e que lança exceção, `__getattribute__` hostil, objeto sem `send`, segunda tentativa impedida, fixture LAB com um único acesso pós-CAS, getter LAB que falha e conserva ambiguidade, método ausente conservador, posição estática do `getattr`, reinício sem consulta e XFAIL de subclasse LAB importável por host não confiável.

A CI Ubuntu/Windows executa A266, A265, A260, A259, A258, A257–A243, A202–A206, A213, Outbox, Saga e Chaos. Os números devem vir dos logs; CI verde não homologa P0s.

**Permanecem:** falta raiz de confiança independente, custódia de chaves fora do host, identificação autêntica de eventos, testemunha monotônica, vinculação FD/VFS SQLite e recibos do provedor; configuração da `main` proposta na A264 ainda não foi aplicada e Render não exige A260–A262. A correção reduz a superfície do Outbox NORMAL, mas host com execução arbitrária continua podendo alterar código.

**UNCERTAIN=ZERO_AUTO_RESEND. Trader prioritário, Investimentos preparado, Negócios congelada.**
