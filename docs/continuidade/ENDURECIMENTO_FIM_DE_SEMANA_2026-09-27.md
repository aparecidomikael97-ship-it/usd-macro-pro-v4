# Endurecimento de fim de semana — 2026-09-27

Branch `cursor/weekend-hardening-5f03`, empilhada sobre a Draft PR #244
(`cursor/premium-ui-foundation-5f03`). Nada foi mesclado, publicado ou
alterado em produção, Render, secrets ou autenticação.

## Auditoria de interface (`tools/interface_audit.py`)

Crawler Playwright somente leitura. Faz login com uma conta local de teste,
percorre as áreas do Iniciante e todas as opções de "Área avançada" em desktop
(1440×1000) e celular (390×844), e registra por área: tempo, exceções
(`stException`), alertas de erro, falhas de contraste WCAG, overflow horizontal
e número de botões. A senha é lida de variável de ambiente e nunca impressa.

```
AQ_AUDIT_PASSWORD=... python3 tools/interface_audit.py --user <conta> --out /tmp/aq-audit
```

No Streamlit 1.64 o seletor é um combobox React Aria com lista virtualizada;
o crawler percorre as opções pelo teclado.

Resultado local em modo PRODUCTION, com snapshot real de `atlasquant-runtime` e
sem chaves de API: 29 áreas × 2 viewports, 0 exceções, 0 falhas de contraste
depois da correção abaixo, 0 overflow. Os "alertas de erro" contados são
intencionais: bloqueio do Safety Core, sinais de VENDA em vermelho, persistência
do scanner não configurada e bloqueios de setups não congelados.

## Correções

- Tags de multiselect: texto branco sobre `primaryColor #4fa3ff` (2,62:1) em
  Backtest e Aprender. Agora `#f8fbff` sobre `#1d4e89`.
- Proveniência após a atualização em segundo plano: os loaders gravam
  `STATUS_FONTE` nos globais da execução que iniciou o job. Depois da troca, a
  linha "Fontes/estado" ficava vazia e o banner dizia apenas "Fontes
  atualizadas", mesmo com EUA em valores de segurança. O job agora guarda o
  estado das fontes junto do pacote, e o banner lista as fontes em fallback.
  Esta correção também foi aplicada na #244.
- Cabeçalho do AION: lia `access["username"]`, mas em produção o usuário fica em
  `access["session"]`; sem `AION_ADMIN_DISPLAY_NAME` aparecia "Administrador".
- Ordenação do Radar por sessão não quebra mais com prioridade não numérica.

## AION Central (`atlasquant_aion_workspaces.py`)

As áreas do console já existiam. O módulo novo define seis personas sobre elas:

| Persona | Área do console |
| --- | --- |
| AION Trader | 📈 Trading |
| AION Administrador | 🗂️ Secretaria |
| AION Desenvolvedor | 🛠️ Desenvolvimento |
| AION Vídeo | 🎬 Studio |
| AION Negócios | 💼 Negócios |
| AION Laboratório | 🧪 Laboratório |

Cada persona tem chave de contexto própria (`aion_ctx::<persona>::<chave>`) e
um escopo de ações. O escopo é verificado antes do Guardian e só restringe:
ordens reais, merge, deploy e leitura/escrita de secrets são negados a partir de
qualquer persona, mesmo com aprovação e feature flag.

AION Administrador mostra saudação pelo horário de Brasília ("Bom dia", "Boa
tarde", "Boa noite") com o nome de `AION_ADMIN_DISPLAY_NAME` ou, se ausente, o
usuário da sessão, e um resumo montado apenas com valores do Pulso Executivo.
Contagem ausente aparece como "não confirmado".

AION Desenvolvedor exibe a política de confiança: níveis 0 (leitura) e 1
(rascunho) são autônomos; nível 2 (branch) e 3 (Draft PR) exigem pessoa.
`auto_merge`, `auto_deploy` e autoelevação são sempre falsos. Rollback por
`git revert`, nunca reset ou force push.

## Laboratório (`atlasquant_lab_matrix.py`)

Matriz timeframe × estilo × setup, reaproveitando `atlasquant_timeframe_profiles`
(M15 e M30 intraday, H1 day trade, H4 e D1 swing, W1 position/semanal) e o
catálogo de `atlasquant_setup_validation`. Toda célula começa em
`SEM_EVIDENCIA`; só muda com um registro de evidência daquela combinação.
Registro parcial fica `EVIDENCIA_INCOMPLETA` com os campos ausentes vazios.
Nenhum backtest é executado ou simulado. Preparado, ainda não exibido na
interface.

PPR entrou no catálogo como "definição pendente": não há regra objetiva
documentada no projeto, então fica bloqueado para qualquer atribuição.

## Medições locais (processo novo, sem chaves de API)

| Etapa | Desktop | Celular |
| --- | --- | --- |
| Formulário de login | 1,9 s | 1,4 s |
| Login até o shell | 1,0 s | 1,4 s |
| Primeira abertura do Avançado (cache) | 1,7 s | 1,6 s |
| Troca de área (mediana) | 0,74 s | 0,72 s |
| Abrir AION | 0,74 s | 0,79 s |

São medições em máquina local; a latência do Render não está incluída.
