# AtlasQuant Trader — ponte temporal BCE ↔ macro (LAB)

Checkpoint de 04/11/2026. Prioridade preservada: explicar as oito moedas,
28 pares e horizontes D1/W1/MN1 com contexto **macro, micro, geopolítica,
notícias e calendário**. FVG/OB fora do escopo imediato.

## Problema corrigido nesta etapa

Uma notícia/estatística pode chegar **depois** do último valor de referência
disponível do BCE. Se o aplicativo juntasse os dois sem comparar datas,
poderia produzir uma história causal que seria cronologicamente impossível:
"o evento de hoje fez o BCE de ontem cair".

`atlasquant_trader_ecb_macro_timing_bridge_lab.py` recebe:

1. XML de referência BCE **fornecido pelo chamador**, processado novamente
   pelo próprio módulo BCE da PR #1811 (não aceita uma matriz adulterada);
2. dossiê de contexto macro no **contrato LAB** definido na PR #1803,
   ainda não integrada nem autenticada.

Para os 28 pares × 3 horizontes, separa eventos econômicos declarados em:

- divulgados **antes** da janela comparada;
- divulgados **entre** as datas de referência (correlação documental, não causa);
- divulgados no **mesmo dia** da taxa inicial/final — ordem intradiária
  impossível de determinar apenas com a data do BCE;
- divulgados **após** a última referência, que não podem explicar
  retrospectivamente a variação encerrada.

O módulo também recusa dossiês com pares ausentes/duplicados, carimbo
temporal incompatível, reivindicação falsa de fontes autenticadas,
publicações futuras ou suposto sinal BUY/SELL. Uma notícia não preenche
histórico cambial faltante. Surpresas "acima/abaixo do consenso" continuam
**sintéticas e não implicam automaticamente força de moeda**.

## Teste de compatibilidade entre as duas PRs

No workspace combinado, um dossiê real *de LAB sintético* produzido por
`build_macro_causal_dossier_lab()` da PR #1803 foi aceito pelo novo contrato
da PR #1811, gerando 28 linhas sem viés negociável. Isso **não significa**
que as branches estejam integradas ou aprovadas para uso real.

## Validação e restrições

Comandos locais:

```bash
python -m unittest -q \
  test_atlasquant_trader_ecb_macro_timing_bridge_lab.py \
  test_atlasquant_trader_ecb_horizon_context_lab.py \
  test_atlasquant_trader_ecb_three_horizon_matrix_lab.py
```

**31 testes locais verdes: 10 novos, mais 21 anteriores**. Atualizar workflow
de qualidade da PR #1811 não é o mesmo que concluir seu CI remoto.

**Limites importantes:** datas BCE sem horário de negociação, XML sem
autenticação de origem no adaptador, notícias/consenso da PR #1803 apenas
testes sintéticos, sem preço FX independente ou relação causa/efeito
estatisticamente validada. As janelas D1/W1/MN1 se sobrepõem; não contam
como confirmações independentes. Todo viés permanece `AGUARDAR`.

Três coletas diárias permanecem **planejadas**, não automáticas. Sem
cron, Worker, Render, custos, deploy, merge ou operação real.
