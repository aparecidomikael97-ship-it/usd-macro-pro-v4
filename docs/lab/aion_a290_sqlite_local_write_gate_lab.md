# A290 — Cache-safe local SQLite write gate (research LAB)

**HARD NO-GO / 0 de 6 P0 homologadas / ZERO_AUTO_RESEND.**
Somente arquivos SQLite temporários sintéticos. Não importa nada no
Worker, Outbox, ordens, comunicação externa, deploy ou aba Negócios.

## Decisão de engenharia

A289 confirmou em SQLite nativo que revogar apenas um booleano Python
não reprova um UPDATE já compilado e cacheado. Por isso A290 testa uma
camada de escrita de uso *cooperativo*:

- o objeto público oferece somente read_value() e trusted_increment();
- uma autorização interna curta cobre a execução e o COMMIT local;
- fora dela, um authorizer SQLite tenta negar INSERT/UPDATE/DELETE,
  alterações de schema e ATTACH/DETACH;
- o modo uncached abre a conexão com cached_statements=0;
- o modo cached_rearmed reinstala o callback ao terminar o lease,
  forçando revalidação de statements cacheados;
- o modo cached_unrearmed é uma contraprova **deliberadamente insegura**:
  ao retirar somente o booleano, o mesmo UPDATE pode passar.

Todos os caminhos acima são de laboratório. Uma camada desse tipo não
pode ser considerada política de autorização de um host adversarial.

## Resultados esperados

| Modo | Escrita controlada | UPDATE direto igual, após revogar grant |
|---|---|---|
| uncached | Aceita | Bloqueia |
| cached_rearmed | Aceita | Bloqueia |
| cached_unrearmed | Aceita | Permite (contraprova) |

A290 também comprova que quem segura a conexão Python bruta pode
chamar set_authorizer(None), removendo o guard e gravando novamente.
Portanto a propriedade privada _db não é um limite contra código com
acesso ao mesmo processo. A interface reduz erro acidental, não
autoriza a falar em segurança independente.

## Limites absolutos

1. A autorização SQLite age na preparação do SQL e deve permanecer
   válida durante recompilação. Não substitui contratos transacionais
   nem o marcador de COMMIT incerto.
2. O objeto e o handle ficam no mesmo processo Python; introspecção,
   código hostil com execução local e administradores podem contornar
   os controles.
3. data_version continua cego a escritas da própria conexão.
4. quick_check=ok, inode e callback não provam FD/VFS ou rollback
   monotônico fora do host.
5. Sem testemunha externa ou recibo autenticado do provedor, P0-5 e
   P0-6 permanecem NÃO HOMOLOGADAS.
6. O teste não mede performance real de desativar o cache; qualquer
   integração futura deve avaliar custo de CPU/latência e concorrência.

## Bateria

18 testes A290 + regressão A285–A289 em Ubuntu e Windows Python 3.12,
usando executores padrão gratuitos do repositório público. Sem pacote
terceiro, sem contratos novos, sem alterações em aion_chat/store.py.

Documentação primária:
- https://www.sqlite.org/c3ref/set_authorizer.html
- https://docs.python.org/3.12/library/sqlite3.html

**Próximo passo proposto:** selecionar somente um contrato de escrita
cooperativa e testar compatibilidade com marcadores de COMMIT incerto no
store real, sempre opt-in LAB e sem promoção P0.
