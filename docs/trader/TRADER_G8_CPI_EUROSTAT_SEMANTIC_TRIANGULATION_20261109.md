# AtlasQuant Trader — Eurostat CPI, leitura documental em LAB (09/11/2026, Cuiabá)

## Escopo

Após a captura oficial Eurostat feita no AM12 e a verificação de SHA-256 no
arquivo local, acrescentamos um leitor **somente de leitura** para avaliar a
coerência de três referências presentes no **mesmo HTML**:

1. Etiqueta da publicação: `Flash estimate - October 2026`;
2. Manchete: `Euro area annual inflation up to 4.0%`;
3. Descrição OG e linha `All-items HICP` da tabela, distinguindo taxa anual
   do último campo, que é a variação **mensal**.

O parser exige período, etapa FLASH, colunas anuais esperadas, valor numérico
e concordância. Captura a alegação de data `article:published_time`, mas **não
confunde** esse campo editorial com carimbo de primeira divulgação atestado.
Não calcula viés, não acessa MT5, não consulta preço, não faz HTTP e não cria
arquivos novos. Em qualquer divergência, devolve bloqueio e `AGUARDAR`.

O caminho de arquivo aceito na verificação é restrito ao manifesto EUR FLASH
2026-10 da publicação oficial `2-04112026-ap`; o verificador anterior reabre
os bytes, compara comprimento e SHA-256 e rejeita corrupção. A confirmação
de conteúdo entre partes **de uma única página** não constitui comprovação
independente do dado econômico.

## Validação registrada

- Testes locais isolados do novo leitor: **11/11 OK**.
- Conjunto `python -m unittest discover -q -p 'test_atlasquant*.py'`:
  **152/152 OK**.
- Casos adversariais: diferença manchete/OG/tabela, valor sem marca `e`,
  mês ou etapa errados, cabeçalho de tabela manipulado, duplicidade,
  metadados temporais inválidos, HTML não UTF-8, corpo adulterado,
  manifesto de outra origem e conferência de nenhuma escrita.
- **Pendente:** execução integral do novo leitor no HTML real AM12. O
  terminal remoto aparece conectado, mas as últimas chamadas de processo
  esgotaram o timeout. Não marcar esta etapa como validada até obter saída
  e conferência do hash exato do script no dispositivo.

## Limites explícitos

- O arquivo anterior AM12 continua preservado; não subir HTML bruto ao PR.
- `4.0%` é um resultado **documental atribuído à página**, não evidência de
  previsão correta, snapshot de vintage P-I-T, acerto de direção ou gatilho
  de compra/venda.
- `issuer_first_release_authenticated=False` e
  `historical_point_in_time_eligible=False` permanecem invariáveis.
- Sem alteração de produção, main, merge, publicação, Render, jobs, cobrança
  ou ordens no Pepperstone/MT5.

## Próxima trava

Quando AM12 responder: comparar SHA-256 do leitor local e remoto, executar
`python atlasquant_trader_g8_cpi_eurostat_semantics_lab.py <manifesto>` e
registrar o resultado observado ou corrigir parser para o HTML real. Só
depois avaliar extrações semelhantes para outras moedas, sempre sem inventar
vintage ou viés.
