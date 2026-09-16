# AtlasQuant — checklist final externo

Status do código Runtime: **VALIDADO EM CI**

Referências atuais:

- Runtime: `03cf06c1064be5e0a5a9bc92c3709341d48db0ca`
- Quality Runtime: `35115636444`
- Resultado: **653/653 testes OK**
- Compile gate: **verde**

## O que já está fechado

- cinco operacionais técnicos independentes;
- backtest automático e manual;
- comparador dos cinco operacionais;
- estabilidade temporal;
- walk-forward;
- custos/slippage;
- robustez de parâmetros;
- relatório consolidado;
- snapshots reproduzíveis;
- histórico/exportação/restauração de snapshots;
- isolamento de Runtime;
- preservação dos dados operacionais;
- smoke headless da UI;
- zero Twelve Data no boot;
- zero escrita HTTP remota no boot;
- rótulo de ambiente Runtime dinâmico.

## Verificações externas que ainda precisam de ambiente real

### 1. URL de produção

Abrir o endereço real do app e confirmar:

- HTTP/HTTPS responde normalmente;
- app inicia sem tela de erro;
- cabeçalho identifica `RUNTIME`;
- navegação principal abre as telas esperadas.

### 2. Inspeção visual em navegador real

Conferir:

- layout desktop;
- layout mobile;
- tabelas;
- expanders;
- downloads;
- inputs;
- Backtest;
- comparador;
- histórico de snapshots;
- ausência de labels DEV.

### 3. Secrets/configuração hospedada

Confirmar no ambiente hospedado, sem expor os valores:

- `GITHUB_DATA_BRANCH=atlasquant-runtime`;
- `GITHUB_BRANCH_HISTORICO=atlasquant-runtime`;
- chaves externas necessárias presentes;
- tokens/repositório de persistência configurados quando aplicável.

### 4. Pine no TradingView

Compilar manualmente no Pine Editor:

- BOS/CHOCH + Order Block;
- FVG;
- OTE;
- CRT;
- AMD / Power of Three.

CI valida contratos estáticos, mas não substitui a compilação dentro do TradingView.

### 5. Rodada live controlada

Somente após os itens acima:

- executar uma rodada controlada;
- respeitar budget/quota;
- confirmar leitura e escrita na Runtime;
- verificar que a main não recebe dados operacionais;
- revisar logs/erros;
- não tratar uma única rodada como evidência estatística de performance.

## Critério de fechamento

O sistema pode ser marcado como **RUNTIME_EXTERNAL_VALIDATED** somente depois de completar os cinco grupos acima.

Nenhum item deste checklist altera automaticamente Gate, pesos, parâmetros ou regras de execução.
