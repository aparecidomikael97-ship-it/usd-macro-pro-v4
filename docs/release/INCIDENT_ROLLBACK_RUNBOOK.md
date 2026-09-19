# AtlasQuant — Runbook de Incidente e Rollback

Este runbook descreve resposta operacional segura. Rollback continua uma ação humana/revisável.

## Sinais de incidente

Considere incidente quando houver, por exemplo:
- aplicação não inicia;
- health check falha;
- Browser Smoke falha em desktop ou mobile;
- exceção Streamlit não esperada;
- regressão crítica do motor;
- violação de integridade de dados;
- erro persistente acima do limite definido;
- exposição acidental de secret/credencial.

## Primeira resposta

1. Não habilite ordens reais como tentativa de diagnóstico.
2. Preserve logs/evidências do run afetado.
3. Identifique o último commit `main` conhecido como verde.
4. Compare o diff do deploy atual com esse ponto.
5. Classifique se a falha é UI, infraestrutura, dados, autenticação ou motor.
6. Se a integridade não estiver suficiente, mantenha o sistema fail-closed.

## Critérios de rollback

O `atlasquant_release_guard.should_rollback` considera rollback quando:
- app não inicializa;
- health check falha;
- há erro crítico do motor;
- há violação de integridade;
- taxa de erro excede o limite;
- entradas de evidência são inválidas.

## Execução segura do rollback

- usar commit conhecido e validado;
- preservar histórico/auditoria;
- não copiar runtime mutável para a release;
- rodar Quality/compile;
- redeploy;
- executar Production Health;
- executar Browser Smoke desktop/mobile;
- confirmar ausência de exceções e overflow;
- registrar o motivo.

## Incidente de secret

Se um secret for exposto:
1. revogar/rotacionar imediatamente no provedor;
2. remover do ambiente/repositório/log quando aplicável;
3. verificar histórico e artefatos;
4. emitir novo secret pelo canal autorizado;
5. não reutilizar o valor comprometido.

## Encerramento

Um incidente só é encerrado depois de:
- produção saudável;
- causa registrada;
- mitigação aplicada;
- checks verdes;
- revisão humana concluída.

Rollback não muda a regra de segurança: broker/ordens reais permanecem desativados nesta release.
