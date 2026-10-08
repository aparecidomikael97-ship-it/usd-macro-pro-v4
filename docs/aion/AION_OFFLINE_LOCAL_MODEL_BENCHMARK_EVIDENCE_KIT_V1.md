# AION — Kit offline para medir modelos locais (V1)

**Data:** 08/10/2026  
**Base:** PR #1074, que usa a leitura agregada da #1073.  
**Estado:** IMPLEMENTATION SAFE, Draft e CI. Nenhum computador do proprietário foi examinado ou alterado.

## Por que isto muda o processo

Nosso objetivo é reduzir mensalidades do AION sem sacrificar qualidade, tempo de
resposta, segurança e privacidade. Não basta avaliar uma IA por tamanho,
marketing ou um único teste rápido. Precisamos de um **protocolo repetível**
para comparar modelos executados localmente, quando houver hardware e software
efetivamente disponíveis no computador autorizado.

Esta implementação não baixa nem carrega modelos. Ela oferece uma **lista
pública de perguntas fictícias, um formato único de coleta e um avaliador de
registros de desempenho e notas humanas** que podem ser preenchidos
manualmente no futuro.

## Estrutura da campanha

São quatro áreas e quatro cenários em cada área:

| Área | O que precisamos observar |
| --- | --- |
| GENERAL_TEXT | explicação objetiva, resumo, proteção de senhas, reconhecimento de limitações |
| B2B_DOCUMENT_DRAFT | follow-up, cláusula ambígua, diagnóstico comercial, pedido relacionado à LGPD |
| MACRO_EDUCATION | CPI/Core CPI, NFP e incerteza, recusa de cotação inventada, juros e dólar |
| VOICE_INTENT_TEXT_ONLY | reconhecer pedido de navegação, pedir autorização para gasto, reconhecer ambiguidade, recusar modificação insegura |

**Não há comando de trading real, microfone, WhatsApp, aplicativo, conta
financeira, navegador ou execução de ação.** Os cenários são educativos e
fictícios. Usar o mesmo conjunto de testes publicamente conhecido permite
regressões repetíveis, mas não constitui uma avaliação cega e pode sofrer
overfitting. Provas adicionais e revisão humana independente serão necessárias.

Cada área possui **2 warmups**, descartados na análise, e cada um dos quatro
cenários recebe **5 medições válidas**: 8 aquecimentos + 80 medições = **88
linhas**. As métricas esperadas são latência em milissegundos, tokens de
entrada/saída, pico estimado de RAM, VRAM dedicada (nulo se desconhecida)
e avaliação humana em `PASS`, `FAIL` ou `UNREVIEWED`.

A latência p95 usa o método *nearest-rank*: para 20 observações, a 19ª
observação em ordem crescente. Isso é apenas uma estatística sobre dados
declarados: a captura do instante de início/fim, a carga do sistema e a
reprodutibilidade ainda precisam ser comprovadas num benchmark real.

## Como utilizar futuramente — apenas após conferência e consentimento

O utilitário `scripts/aion_offline_model_benchmark_review_v1.py` é
compatível com Python 3.12 e usa apenas a biblioteca padrão.

- `python scripts/aion_offline_model_benchmark_review_v1.py --manifest`:
  exibe 16 cenários públicos em português.
- `python scripts/aion_offline_model_benchmark_review_v1.py --template`:
  exibe em tela um JSON-modelo **intencionalmente incompleto**, com
  valores de tempo e tokens `null`. Ele **não simula uma execução bem
  sucedida**. O usuário poderá optar por copiar a saída para um arquivo,
  mas o script em si não o grava.
- Após medição e preenchimento manuais, `--review` permite indicar um
  arquivo JSON específico e três hashes esperados: challenge, bytes do
  arquivo de modelo e relatório de hardware. Os hashes devem ser obtidos
  de um processo independente confiável; **copiar o mesmo valor informado
  pelo arquivo não cria verificação externa**.

Exemplo ilustrativo de comando, **não executado**:

```powershell
python scripts/aion_offline_model_benchmark_review_v1.py --review C:\caminho\resultados.json --challenge-sha256 <hash-de-desafio> --model-artifact-sha256 <hash-do-modelo> --hardware-report-digest <hash-do-relatorio>
```

A leitura é local, limitada a 256 KiB, sem chamadas de rede e sem modificar o
arquivo. A saída contém apenas contagens, métricas agregadas e avisos — **não
exporta textos de prompts, respostas, nome de usuário, número de série,
chaves, tokens, credenciais nem caminho do arquivo**.

Os campos `no_network_claimed` e `no_paid_api_claimed` são afirmações de
quem preparou os resultados; não há monitoramento de rede nem comprovação
forense. Não use dados de clientes reais nesse protocolo inicial.

## Como interpretar a revisão

A CI valida formato, exatidão do conjunto de 88 amostras, duplicação, limites
numéricos e vinculação de digests contra valores **declarados externamente**.
Ela calcula estatísticas para quatro áreas. Um cenário não revisado não é
aprovado automaticamente. Um rótulo humano de qualidade ou segurança também
não é certificado por IA e não deve ser tratado como prova de aptidão.

Mesmo que as médias e p95 pareçam excelentes, o estado máximo do avaliador é
`CI_OR_MANUAL_MEASUREMENTS_UNVERIFIED_HUMAN_REVIEW_REQUIRED`.

Os limiares de latência por tarefa herdados do planejamento são **valores
provisórios de regressão**, não contratos de serviço, nem benchmarks aferidos
do AION. Conclusões sobre 7B, 14B, quantização, qualidade B2B, multimodal,
voz ou vídeo exigem ensaios concretos e escopo específico.

## Próximas evidências necessárias antes da operação real

1. Confirmar hardware do proprietário mediante a leitura local explícita
   da #1073 (RAM/CPU/disco e, em etapa adicional, VRAM real).
2. Revisar licença, procedência e integridade do modelo local e seu motor
   de inferência, sem download automático, antes de instalar qualquer coisa.
3. Medir tempo, consumo de energia, RAM/VRAM sob carga, throughput,
   disponibilidade e qualidade por tarefa sob condições reprodutíveis.
4. Distinguir revisão humana da validação objetiva de respostas e resistência
   a instruções adversariais. Testar privacidade entre empresas/tenants.
5. Comparar custo operacional real local (incluindo eletricidade e hardware
   depreciado) com preço autenticado de APIs; conectar limites reais de
   fornecedores antes de permitir qualquer fallback.
6. Integrar ao AION somente depois de aprovação específica, com modo seguro
   de degradação e autorização por gasto. O teto inicial de R$ 200 continua
   sendo **meta**, não despesa provada.

**Sem execução de modelo, download, modelo em produção, consumo de APIs,
cobrança, merge, deploy, Worker, instalação ou acesso ao computador do
proprietário nesta PR.**
