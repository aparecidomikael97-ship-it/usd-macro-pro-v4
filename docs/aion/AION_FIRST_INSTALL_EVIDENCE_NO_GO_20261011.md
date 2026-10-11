# AION — evidência real da primeira instalação (11/10/2026)

**Resultado: HARD NO-GO.** O QA de software (6.348/6.348 PASS na suíte principal da PR #1214) não constitui autorização de primeira instalação. Este documento é uma auditoria local de código e manifesto, não uma verificação física do Windows nem uma certificação externa.

## Constatações reproduzíveis

- O manifesto de evidência em docs/aion/evidence/AION_WITNESS_EXTERNAL_ENROLLMENT_GATE_V1.json contém **20 de 20 requisitos BLOCKED**. Nenhum deles possui URI de evidência, digest de evidência ou verificador independente registrado.
- Todos os indicadores operacionais de confiança, ativação, witness, orçamento aprovado, gasto, deploy e retry automático permanecem falsos no manifesto. **Isso NÃO comprova o valor da flag remota em produção**, que não foi consultada.
- A função real independent_worker_source_preflight retorna BLOCKED e não autoriza source/Worker. O caminho run_global_worker_once chama a validação de origem antes de GET privado, CAS ou executor.
- A verificação de prontidão consulta a origem antes de obter GITHUB_TOKEN_HISTORICO. A etapa operacional do GitHub preserva pipefail para que BLOCKED não seja mascarado por PASS de testes negativos.
- O teste adicional tests/test_aion_first_install_evidence_no_go_1215.py verifica a integridade do manifesto e negação local com dados sintéticos; não usa rede, credenciais, Windows Hello, FIDO2, dados de clientes, chaves ou API paga.

## Ordem das evidências que precisam ser obtidas — somente em trabalho futuro autorizado

| Bloco | Evidência independente exigida | Limite |
|---|---|---|
| Proprietário e tenants | Matrícula real do HUMAN_OWNER e registro revogável de tenant, dispositivo, repositório, branch e recurso | ADMIN, sessão sintética, SHA e PIN declarado não comprovam custódia |
| Origem e witness | Confirmação fora da mesma administração, CAS monotônico, segundo domínio imutável, fork/restore e revogação | Nenhum provedor ou chave real foi matriculado |
| Windows | Host autorizado, manifesto/instalador assinado, assentimento do proprietário, egress/AppContainer, proteção de credenciais | Nenhuma instalação, TPM ou teste físico foi executado |
| Dados, recuperação e LGPD | Crash/UNKNOWN_OUTCOME sem replay, isolamento A→B, autenticação real, residência/retenção e documentos | Não executar GET privado só para tentar passar CI |
| FinOps e liberação | Cotação integral dentro do teto de referência R$ 200/mês; aprovação separada para qualquer gasto, merge, deploy ou ativação | Teste verde não é uma autorização humana |

## Limite deliberado desta Draft

O novo teste está em tests/ (fora da lista de 569 testes raiz), com workflow próprio Windows/Linux. Ele detecta mudanças inadvertidas nos 20 bloqueios e na ordem das barreiras. **Não sabe verificar a procedência real de um comprovante, não gera GO e não altera o Worker ou o Core V1.** Uma cerimônia física futura exigirá escopo e autorização específicos; não pode ser substituída por mudança neste teste.

Nenhum merge, publicação, gasto, matrícula de credencial, Worker, alteração de manifesto, deploy ou instalação foi autorizado ou efetuado por esta etapa.
