# AION A199 — produção e autenticação não podem ser desativadas por conflito de configuração

**27/10/2026; LAB Draft. 0/6 P0 homologadas, HARD NO-GO.**

## Falha de código observada após consolidação A198

`atlasquant_access_panel.access_required()` consultava
`_setting("ATLASQUANT_ENV")`, que escolhe Streamlit secrets antes de
`os.environ`. Se o sistema realmente tinha
`ATLASQUANT_ENV=PRODUCTION` como variável de ambiente, mas o secrets
informava `ATLASQUANT_ENV=LOCAL`, `access_required()` podia retornar
`False` quando `ATLASQUANT_AUTH_REQUIRED=false`. A aplicação principal
podia assim considerar o login opcional, apesar de outro canal de
configuração indicar produção.

A própria correção A194 tratou esse conflito no caminho de **falha de
importação**, porém ainda não no caminho normal do login. Encontramos
também o problema equivalente: `ATLASQUANT_AUTH_REQUIRED=true` no
processo, e um `false` em secrets, podia ser rebaixado.

## Correção REAL proposta, não integrada

- `atlasquant_access_panel.access_required`: PRODUCTION em *qualquer uma*
  das duas fontes exige login; `AUTH_REQUIRED=true` em qualquer fonte
  também exige login. `False` em uma fonte nunca anula um `True` ou
  `PRODUCTION` na outra.
- `usd_macro_pro_v4_cloud.py`, fallback quando import do login falha:
  usa a mesma semântica OR para `AUTH_REQUIRED` nas duas fontes, mantendo
  `st.stop()` obrigatório se não conseguir importar o login com qualquer
  indicador de exigência de autenticação.
- Modo não produção, ambas fontes explicitamente desligadas, continua
  oferecendo OPEN **somente quando permitido**. OPEN não é autenticado.
- A correção só ativa a exigência de login e o bloqueio seguro; **não cria
  senha, login falso ou permissões de admin**.

## Testes

`python -B -m unittest -v labs.test_a199_auth_configuration_monotonic_lab`

A suíte executa via AST as funções **originais** de
`atlasquant_access_panel.py` e o bloco de fallback **original** de
`usd_macro_pro_v4_cloud.py`, substituindo apenas Streamlit e o ambiente
por valores sintéticos. Os testes cobrem:

- Produção declarada por secrets, env, ambas ou com caixa/espaços
  diferentes; ambas direções de conflito.
- Flags AUTH_REQUIRED contraditórias, sinônimos true e indisponibilidade
  de Streamlit secrets.
- Matriz de **144 combinações distintas** de
  `ATLASQUANT_ENV` x `ATLASQUANT_AUTH_REQUIRED` nas duas fontes.
- Mesma decisão fail-closed no login principal e fallback de importação.
- Ordem do login antes da construção de host chat.

Executar Windows/Ubuntu com Python stdlib, sem provider, rede, credencial
real, Streamlit importado no teste ou operação financeira. CI canônico
A193–A197, Quality e browser também devem passar antes de revisão.

## Limites e governança

`access_required=True` **não é** `authenticated=True`: login não
homologa identidade original do HUMAN_OWNER, cadastros independentes,
custódia monotônica/antirrollback, CAS da intenção econômica, provider
receipt H0 ou atestação SQLite nativa. A190/G122 mantém cinco condições
externas RED por SO, seis P0 abertas e HARD NO-GO.

Negócios segue congelado. Nenhuma contratação, assinatura, AWS, Worker,
SEND, trade real, merge ou deploy. Sem novo gasto até 05/11; 06/11
somente reavaliação com autorização individual do proprietário.
