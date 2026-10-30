# A308-D1 — diagnóstico de regressão lenta em Ubuntu (LAB)

**HARD NO-GO, ZERO_AUTO_RESEND, P0 homologadas 0/6, sem novos serviços.**

O workflow original da A308 [PR #1759](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1759) iniciou no Ubuntu e no Windows. O Windows concluiu 248 testes (247 aprovados, 1 não aplicável); o Ubuntu permaneceu no comando monolítico de regressões **sem resultado final** no momento de abrir este diagnóstico. Não se pode chamar o conjunto de validado até obter seu status completo.

## Ação diagnóstica

Executar as mesmas 12 suites A308–A292 em **subprocessos Python separados**, com limite de **90 s por suite**, e imprimir uma linha `A308-D1 START/ PASS/ FAIL/ TIMEOUT` por módulo. O processo que trava é identificado; qualquer falha/timeout faz o job terminar RED. Testes do próprio watchdog também são executados. Não existe rerun automático nem liberação de P0.

A separação é apenas instrumento de depuração; passar suites isoladas **não demonstra** que suites em conjunto sejam estáveis, e não substitui uma checagem do processo monolítico após localizar e corrigir a causa. Se o runner (e não os testes) estiver indisponível, o diagnóstico pode também ficar bloqueado.

## Segurança

O script só permite uma lista fixa de módulos LAB e não chama rede/provedor, Worker, deploy ou ordens. Nenhum banco real é modificado; os testes anteriores usam dados descartáveis. GitHub Actions do repositório usa os runners existentes, sem contratação nem infraestrutura nova. A PR draft sobre A308 não faz merge.

**Concluir a análise exige evidências dos logs de ambos os sistemas.** O status do AION segue HARD NO-GO, 0/6 P0 homologadas.
