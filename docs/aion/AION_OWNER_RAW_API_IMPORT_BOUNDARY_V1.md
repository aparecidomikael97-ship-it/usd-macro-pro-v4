# AION Owner RAW API — Auditoria de bypass por importações Python V1

**08/10/2026 — somente CI, branch Draft. Não faz merge, deploy ou alteração no PC.**

## Constatação ao revisar a interface

- `atlasquant_central_hub_ui.py` importa métodos de navegação da interface convencional em `atlasquant_navigation_bridge.py`, e essa navegação por cards **não é um comando remoto privilegiado de voz/texto do HUMAN_OWNER**.
- A cadeia criptográfica nova (#1079, #1081, #1082, #1083, #1084) está isolada em branches ainda não integrados na interface real.
- Nada nesta PR altera o login, liga a identidade real nem atesta a navegação funcionando na tela.

## Barreira de regressão implementada

O módulo `atlasquant_aion_owner_raw_api_import_gate_v1.py` contém uma lista fechada de seis módulos de segurança sensíveis:

1. Ponte de navegação do proprietário (#1078).
2. Verificador de assinatura Ed25519 (#1079).
3. Ponte prova de sessão → navegação (#1081).
4. Guard de assinatura de intenção textual (#1082).
5. Registro e revogação de chaves do proprietário (#1083).
6. Composição rooted de identidade + comando (#1084).

Somente arquivos Python internos explicitamente listados poderão **importar** cada módulo sensível. Qualquer tentativa de importar os verificadores sensíveis diretamente de arquivos de interface, novo host não auditado ou entrada de cliente faz a validação CI falhar.

A verificação usa AST do Python, sem executar os arquivos auditados. Cobre `import`, `from ... import`, apelidos de importação, formas relativas conhecidas, e chamadas literais comuns de `__import__`, `importlib.import_module`, `runpy.run_module` e `find_spec`; também detecta formas literais de `runpy.run_path`, `spec_from_file_location` e `exec`/`eval` com referência explícita aos módulos protegidos. O teste CI faz varredura em fontes Python de produção da árvore do repositório, incluindo módulos dentro de subpastas (exceto testes, documentação e bibliotecas vendorizadas). Uma falha de leitura, arquivo symlink de origem de código, ou Python não analisável impede o gate.

A implementação precisa ser atualizada **apenas por revisão explícita** se um futuro host confiável real tiver motivos técnicos válidos para importar a fachada rooted. Por enquanto a lista de importadores permitidos para a fachada #1084 está **vazia** em produção. Testes usam as interfaces diretas para gerar fixtures sintéticas, e ficam de fora da lista de módulos de produção.

## O que esse teste NÃO protege

- Python não é sandbox: chamada reflexiva complexa, `exec`, nomes de módulo construídos em runtime e carregamento por paths indiretos podem escapar da inspeção estática. Testes dinâmicos de integração e auditoria humana permanecem obrigatórios.
- O gate não examina JavaScript/TypeScript, endpoints HTTP, Redis/Celery, plugins de terceiros, runtime instalado no computador ou outros repositórios.
- **Não representa prova de que não existe bypass em produção.** Demonstra apenas política de dependências estáticas para os arquivos examinados num checkout específico.
- A própria implementação da lista de permissões deve receber code review: código malicioso pode tentar alterar gate/workflow e torná-lo inócuo.
- O host real ainda precisa estabelecer asserção autenticada, identidade física do dispositivo, chave raiz de confiança, epoch mínimo antirrollback, chaves FIDO2/Windows Hello, privacidade dos segredos, sessão real e mitigação de XSS/CSRF.
- Os métodos anteriores continuam acessíveis em código Python no mesmo processo. Uma política de imports **não isola privilégios**. Isolamento requer host/serviço separado com fronteira de confiança real.

## Critérios de aceite desta PR

- 41 métodos e subtestes hostis demonstram detecção de importação direta, por alias/dinâmica, módulos não aprovados, testes de sintaxe e varredura de árvore.
- CI é disparado em **toda PR** (sem filtro de caminhos), para que edições futuras em qualquer módulo Python de aplicação também passem pelo gate. CI Linux + Windows utiliza Python 3.12, `unittest`, sem instalar dependências adicionais e sem usar rede, login, APIs pagas, secrets, dispositivos, bibliotecas de IA ou banco real.
- A varredura de checkout deverá informar quantidade de arquivos Python de produção verificados e falhar com uma tabela de violações. **CI só será marcado aprovado depois de ambos os jobs verdes.**
- Integração futura: revisar endpoints reais e fluxo de credenciais (PC + mobile), RBAC, antifraude, instanciamento de HostEvidence e assinatura real. *Nada disso está autorizado nesta PR.*

A `main` e o Core V1 congelado não são modificados. Teto provisório total R$200/mês preservado. Merge/deploy/instalação requerem autorização explícita.
