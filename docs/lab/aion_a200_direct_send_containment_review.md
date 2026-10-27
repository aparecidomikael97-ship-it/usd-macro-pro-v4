# AION A200 — bloqueio de SEND direto de modelos e TTS na base A199 (LAB)

**27/10/2026 · DRAFT · 0/6 P0 homologadas · HARD NO-GO.**

## Proveniência e limites

A base da branch A200 é o SHA `4c52c25e673fa4311d34824828486c0bf9647992` da [PR Draft #1649](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1649), contendo os testes integrados de A193–A199. Portamos as três mudanças produzidas/validadas pelo Codex no desktop `am12` no checkout isolado `.audit-current-a199-fresh`; os dois arquivos de regressão `labs/test_a200_direct_send_containment.py` e `labs/test_a200_direct_send_ui.py` vieram desse checkout. **Nenhum merge nem deploy** foi realizado.

Esta PR modifica apenas três arquivos operacionais:
- `atlasquant_aion_provider.execute_openai_answer`: depois de preflights de privacidade, flag, configuração, aprovação, preço, orçamento e modelo, retorna `state=BLOCKED_SEND_CUSTODY,called=False`; não constrói cliente nem faz POST externo.
- `atlasquant_neural_tts.generate_neural_speech`: preserva validação de modelo, endpoint, transcript e chave, mas recusa qualquer POST externo com `BLOCKED_SEND_CUSTODY` antes do transporte.
- `atlasquant_neural_voice_ui.render_neural_voice_player`: distingue `BLOCKED_SEND_CUSTODY` de erro genérico. Não armazena áudio novo nem ativa fala do browser/aparelho. Texto e áudio válido já em cache permanecem locais.

O código histórico de payload, envio e resposta permanece **inacessível após return/raise incondicional no mesmo método** apenas para permitir revisão; isso não deve ser tomado como implementação de autorização futura. Não existe flag, token ou bool controlável pelo usuário capaz de burlar o bloqueio. Nenhum envio real foi autorizado ou realizado.

### Razão do bloqueio

O campo `request_approved`, a chave API, a presença de quota e o estado `EXTERNAL_READY` **não comprovam custódia externa do primeiro efeito**. Em especial, o ACK pode se perder depois de um envio irreversível; um segundo envio com a mesma intenção pode cobrar ou duplicar efeito. Sem testemunho durável independente do host, a única contenção local demonstrável é *zero SEND*.

## Evidências Codex e CI

Na execução local original do Codex (Windows, Python 3.12), 11/11 testes atuais passaram. Os testes cobrem: chamadas repetidas, 32 chamadas concorrentes por rota, subprocesso encerrado depois da negação e reabertura, duas rotas de texto, UI do player e reprodução local do áudio previamente cacheado. A simulação de interrupção ocorre **após a negação**, não após um envio autorizado; ela não prova receipt H0.

A suíte local ampliada original teve **97 testes: 67 PASS, 2 FAIL, 28 ERROR**. Não escondemos nem transformamos isso em homologação. Os resultados incluíam três expectativas antigas de sucesso em SEND incompatíveis com a contenção, e falhas de ambiente: 14 testes SQLite sem permissão para bancos temporários, 10 agendamentos sem ZoneInfo UTC, 3 módulos sem Streamlit. No primeiro HEAD desta PR os testes legados ainda continham as expectativas anteriores, produzindo três falhas comprovadas no Quality; essas expectativas foram depois migradas explicitamente, preservadas em Git e documentadas na seção abaixo. O dado local é histórico, não resultado desta PR.

**Obrigatório conferir na PR**: workflow dedicado A200 em Ubuntu e Windows; Quality geral, navegador, Security Gate/pip-audit, Core Certification e Release Readiness. Em caso de falha de contrato legado, registrar a expectativa original e sua substituição verificável antes de qualquer revisão. Não falsificar sucesso removendo, `skip` ou `xfail` sem justificativa.

## Regressões de Quality no primeiro HEAD da PR #1650 e migração explícita

[Quality #40600296344](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40600296344) executou **6.117 testes: 2 FAIL e 1 ERROR**, exclusivamente os três casos já vistos pelo Codex local:
1. `test_atlasquant_aion_provider.test_successful_response_is_unverified_model_output_and_no_action` esperava `ANSWER_READY,called=True` mesmo que não houvesse testemunho independente.
2. `test_atlasquant_voice_profile.test_generation_uses_fixed_neural_model_voice_and_ptbr_instructions` esperava áudio `MP3DATA` a partir de um POST falso.
3. `test_atlasquant_voice_profile.test_provider_error_is_sanitized` esperava um erro HTTP 401 *após* atingir o provedor falso.

**Tratamento:** esses três testes de contrato foram **reescritos explicitamente e renomeados**, mantendo o mesmo número total de verificações, para exigir `BLOCKED_SEND_CUSTODY`, ausência de `session.calls`/`requests.post`, ausência de cobrança/answer e ausência de vazamento de chave. Nenhum `skip`, `xfail` nem supressão por ambiente foi aplicado. As expectativas e o código anteriores são verificáveis diretamente no commit pai `dfcb15ca5d4ba1b566be6d38da80cc9984bfe487` e nos diffs desta PR. O transporte e tratamento de erros antigos ainda existem como código **inacessível** para revisão, não como contrato operacional. Validar novamente **todos os testes** no HEAD atualizado antes de afirmar compatibilidade.

## Outros caminhos externos não cobertos

A contenção é **somente dos dois métodos diretos de OpenAI**. A revisão estática de Codex identificou superfícies independentes:
- `ExecutionOutbox.dispatch_claimed`, com adapter `send` fornecido externamente: não prova primeira reserva por autoridade externa independente.
- `atlasquant_aion_global_worker_activation.py` com mutações HTTP `POST/PATCH` de configuração no GitHub; módulos de worker/memória também possuem outros `PUT`.
- `GET` externos de notícias, calendário, mercado, FRED, TwelveData etc., potencialmente sujeitos a quota/custos.
- Plugins, subprocessos, comandos locais e infraestrutura ainda requerem auditoria separada.

**RED fundamentais:** autoridade HUMAN_OWNER original independente, intenção semântica imutável, monotonicidade externa contra rollback conjunto, receipt causal do provedor/NO_EFFECT_FENCED, e segurança SQLite native/inode continuam sem aceitação externa. `UNCERTAIN=ZERO_AUTO_RESEND`; 0/6 P0 homologadas. A200 não autoriza Worker, provider SEND, voz paga, ordens, operações financeiras, cadastro de chave, AWS/KMS ou deploy.

**Governança:** Negócios congelado. Não contrair novos gastos/serviços até 05/11; depois de 06/11, qualquer custo só com autorização expressa. Nenhum gasto foi autorizado por esta PR.
