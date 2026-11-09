# AtlasQuant Trader — comparação pareada do filtro de regime (LAB)

**Checkpoint:** 08/11/2026. **Estado:** metodologia offline implementada e testada com **dados sintéticos**, sem histórico de negociação real reavaliado nesta etapa. **Todos os vieses permanecem `AGUARDAR`.** A PR de desenvolvimento continua em rascunho, sem merge, deploy, custo, tarefas automáticas, aviso ao vivo ou ordens.

## Qual pergunta responde?

> Nos **mesmos** vieses candidatos D1 ou W1, o filtro de regime seleciona uma parcela com maior frequência de direção correta, sem reduzir demais a cobertura?

O comparador em `atlasquant_trader_regime_increment_benchmark_lab.py` recebe uma **lista completa e declarada de oportunidades**, com o viés existente **antes** da adição do regime (`baseline_eligible`), o veto de regime registrado **antes** do candle-alvo (`regime_veto`) e o movimento do candle-alvo observado **depois** de seu fechamento. Não cria nem calcula previsões, não interpreta notícias e não produz alertas.

1. Exige o mesmo ativo e horizonte em todo o lote, separando os 28 pares Forex e D1/W1. Índices WIN/WDO/NAS100/US500/US30 **não** são misturados; precisam de metodologia própria.
2. Exige **três ou mais janelas cronológicas declaradas**, sem sobreposição; `decisão < abertura < fechamento <= resultado observado <= data da auditoria` e `observação do regime <= decisão`.
3. Exige que **todos os IDs** esperados estejam presentes; não ignora silenciosamente decisões erradas. Rejeita IDs repetidos e duas tentativas de contar o **mesmo candle-alvo** sob IDs diferentes.
4. Calcula os três denominadores: quantidade inicialmente elegível (**sem o novo filtro**), quantidade **mantida** pelo regime e quantidade **rejeitada** pelo regime. As duas variantes usam **o mesmo desfecho** para a mesma oportunidade.
5. Direção é definida exclusivamente pelo sinal do movimento *abertura → fechamento* da janela-alvo: `ALTA`, `BAIXA`; **preço igual = erro** para ambas. Não modela entrada M15, spread, slippage nem lucro.
6. Para apresentar **taxas agregadas descritivas** na saída, exige pelo menos **100** decisões inicialmente elegíveis, **30** retidas, e pelo menos **20** inicialmente elegíveis e **5** retidas em cada janela. Sem isso, suprime taxas (inclusive as de cada janela) e mantém somente contagens e motivos da abstenção. Esses parâmetros são cautelas de apresentação, **não** calibração estatística nem garantia.
7. Mostra acerto dos aceitos, acerto dos **rejeitados**, cobertura e diferença em pontos percentuais. Se o filtro melhora a porcentagem descartando quase todas as oportunidades, a cobertura denuncia a perda de utilidade.

### Exemplo de teste, absolutamente fictício

Uma massa criada **propositalmente** para verificar a matemática produz 120 oportunidades, 78 acertos sem o filtro, 78 mantidas pelo filtro e 42 rejeitadas; todos os acertos são colocados artificialmente nas 78 mantidas. O resultado documental exibe **65% versus 100%**, ou **+35 pontos percentuais**, com **65% de cobertura**. **Esse exemplo não é uma medição do mercado, não confirma que o filtro agrega qualquer vantagem e jamais deve ser usado como argumento comercial ou meta de viés.** Há também teste com a seleção invertida, mostrando piora.

## Lacunas que impedem qualquer afirmação de assertividade

- `regime_veto`, `baseline_eligible`, horários, preços, janelas, hashes e oportunidades são **informações passadas pelo chamador**, não comprovadas por fonte independente. Um conjunto manipulado pode excluir perdas **antes** mesmo de definir o manifesto. A simples correspondência com um manifesto fornecido simultaneamente **não** prova pré-registro externo nem ausência de *cherry-picking*.
- Os preços da auditoria AM12 do MT5, **84 séries/103.600 velas**, **não foram reabertos neste ambiente**. A lacuna GBP/NZD D1 em 30/09/2025 e a identidade do servidor de preços continuam pendentes; não preencher candles ausentes nem liberar janelas com calendário não verificado.
- As janelas declaradas podem ter sido escolhidas após observar resultados. Não existe autenticação independente da sequência de versões históricas, do horário da previsão e do horário de publicação de um dado macro.
- Observações de D1 e W1 se sobrepõem e podem ser dependentes; não atribuir confiança estatística binomial ingênua nem tratar pares correlacionados como amostras independentes. É necessário avaliar períodos prospectivos sem ajuste de parâmetros no conjunto de teste e controlar múltiplas tentativas.
- Melhoria de **taxa de acerto condicional** não demonstra melhoria de retorno de investimentos, vantagem causal ou capacidade de fazer previsões. O filtro pode simplesmente reduzir cobertura.
- A função devolve `validated_directional_accuracy=None`, `incremental_accuracy_validated=False`, `calibrated_direction_probability=None`, `fx_bias=None`, `operational_bias=AGUARDAR` e `trade_authorized=False` inclusive no melhor cenário sintético.

## Como reproduzir testes deste módulo

```bash
python -m unittest -q test_atlasquant_trader_regime_increment_benchmark_lab
```

**Rodada local:** 31/31 testes sintéticos deste novo comparador, mais 24/24 testes do filtro de regime anterior (55/55 no total), executados com *stubs* locais das dependências de universo Forex e da dataclass `BiasObservation`. **Não é a suíte completa do repositório nem CI.** Testam amostras mínimas, inversão de resultado, empate, direção de venda, não reaproveitamento de candles, bloqueio de futuro, janelas repetidas, 28 pares, W1 separado e ausência de comprovação estatística.

## Próximas etapas P0, quando houver dados auditáveis

1. **Congelar** de forma testemunhada a lista completa de previsões candidatas, a versão do algoritmo e os cortes do regime **antes** dos resultados.
2. Recuperar os arquivos **reais** do MT5 do AM12, auditoria de gaps/calendário do broker, e as *vintages* macro disponíveis em cada decisão. Não usar histórico atual revisado como se estivesse disponível no passado.
3. Construir oportunidades futuras sem escolher períodos ou parâmetros após observar seus resultados, comparando por **par e horizonte**, e só depois compor estatísticas por grupo, considerando dependência e cobertura.
4. Verificar se o filtro gera ganho incremental **fora da amostra** em janelas de tempo diferentes e sob eventos de alta volatilidade; se não houver ganho, **despriorizar** o filtro mesmo que ele pareça sofisticado.

**Regra permanente:** não confundir os 31 testes de código, os exemplos numéricos inventados e a assertividade direcional real de 65–70% almejada. Até prova contrária, **nenhum acerto real foi validado por este comparador.**
