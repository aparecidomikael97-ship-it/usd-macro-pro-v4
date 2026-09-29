# AION Core Hardening P0 V1

Data: 2026-09-28
Issue mestre: #325
Branch: `cursor/aion-core-hardening-p0-v1`
Base: `main` @ `2c9dade6a87d6f618f05cbb628eb35cee2f3a8a1`

## Objetivo

Transformar partes já existentes da segurança do AION em gates contínuos e verificáveis antes de qualquer ampliação de autonomia.

Este bloco não libera trading real, publicação, cobrança, deploy, merge automático, escrita de segredo ou expansão automática de permissões.

## O que este bloco adiciona

### Ownership explícito

`.github/CODEOWNERS` define ownership das áreas AION, workflows, dependências, deploy e documentos canônicos.

Importante: CODEOWNERS sozinho não torna revisão obrigatória. A exigência depende do ruleset/branch protection de `main`.

### Atualização de dependências

`.github/dependabot.yml` prepara atualização semanal para:

- dependências Python;
- GitHub Actions.

Minor/patch são agrupados para reduzir ruído. Mudanças maiores permanecem separadas para revisão explícita.

### Security Gate sempre presente em PR para main

`.github/workflows/aion-core-security-gate.yml` não usa filtro de paths, para poder ser configurado como status check obrigatório sem desaparecer em PRs que não toquem Python.

Jobs estáveis:

- `AION adversarial contracts`;
- `Supply-chain audit`.

O gate cobre:

- compilação dos contratos críticos;
- matriz adversarial contra autoridade falsa, prompt/tool instruction de fonte externa, delegação de capacidades sensíveis, cross-workspace e controle direto por IA externa;
- regressões de Fortress, Resilience, Tenant, Vault e Durable Tasks;
- `pip check`;
- `pip-audit` sobre `requirements.txt`;
- Bandit em severidade alta para módulos críticos;
- geração e validação de SBOM CycloneDX a partir do ambiente resolvido.

### Matriz adversarial nova

`test_atlasquant_aion_security_adversarial.py` prova explicitamente que:

- WEB/DOCUMENT/EMAIL/TOOL_OUTPUT/EXTERNAL_AI/UNKNOWN nunca ganham autoridade de comando por flags;
- checkpoint e memória interna são evidência, não autorização;
- instrução em origem não confiável é bloqueada como instrução, embora o conteúdo possa ser lido como contexto;
- aprovação humana não transforma EXTERNAL_AI em autoridade;
- capacidades não delegáveis continuam não delegáveis;
- AION Core não delega capacidade ausente no parent scope;
- delegação fica vinculada ao workspace;
- modelo externo não recebe controle direto de ferramentas;
- resource governor reduz autonomia antes de loop ilimitado;
- exposição de segredo força postura de emergência e bloqueia ferramenta sensível.

## O que depende de configuração administrativa do GitHub

O conector atual não oferece mutação administrativa de branch protection/rulesets. Portanto esta parte precisa ser ativada na configuração do repositório, sem fingir que foi feita por código.

Configuração alvo para `main`:

1. exigir pull request antes de merge;
2. exigir CODEOWNERS review quando aplicável;
3. exigir branches atualizadas antes de merge;
4. exigir resolução de conversas/reviews pendentes;
5. bloquear force-push e deleção da `main`;
6. exigir os checks existentes de qualidade/release relevantes;
7. exigir `AION adversarial contracts`;
8. exigir `Supply-chain audit`;
9. manter merge/deploy sensível fora de automação autônoma do AION.

## CodeQL / code scanning

CodeQL não é ligado automaticamente neste bloco. A disponibilidade/licenciamento de code scanning deve ser confirmada para o tipo de repositório antes de tornar um workflow CodeQL obrigatório. Até essa confirmação, o bloco usa Bandit + pip-audit + testes adversariais como controles executáveis do repositório.

Se CodeQL estiver disponível, ele deve ser adicionado como camada adicional, não como substituto dos gates acima.

## Aceite deste bloco

- Draft PR para `main`.
- Novos jobs agendados e executados na PR.
- Testes adversariais verdes ou falhas documentadas/corrigidas.
- Supply-chain audit verde ou vulnerabilidades tratadas explicitamente.
- Sem merge/deploy automático.
- Branch protection continua marcada como pendência até confirmação administrativa real.

## Próximo P0 após este bloco

1. ativar ruleset de `main` com os checks obrigatórios;
2. fechar Prime + Shadow + Sentinel como gate crítico independente;
3. ampliar adversarial testing para tenant escalation, tool injection e payloads maliciosos reais;
4. provar Guardian + Proof of Safety + approval no caminho de execução sensível, não apenas em contratos puros;
5. preparar recovery/chaos do P1 após os bloqueadores P0.
