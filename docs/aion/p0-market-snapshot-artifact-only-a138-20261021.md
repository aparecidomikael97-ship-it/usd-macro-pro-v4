# AION P0 A138 — Separação de dados de mercado em artefato offline (LAB)

21/10/2026. PR Draft empilhada na #1421. Sem merge, deploy, worker, restauração real, fornecedor pago nem GitHub Contents PUT do produto.

## Objetivo honesto

Os workflows vigentes na main de Coleta e Autopilot têm agenda e token do repositório com capacidade contents:write. A137 propõe congelá-los somente em LAB, mas tal congelamento também impediria a coleta legítima. Reduzir o token para contents:read, sem refatorar seus gravadores GitHub Contents PUT, não preserva a funcionalidade.

A138 demonstra um caminho ALTERNATIVO de saída: copiar dois JSON de mercado já versionados no repositório para um ZIP com manifesto SHA-256, verificar o ZIP e carregá-lo como artefato temporário do GitHub Actions, usando apenas contents:read. Isso é ensaio de isolamento do DESTINO. Não é aquisição de dados novos. Não ativa FRED, NewsAPI, Twelve Data, Streamlit, Autopilot nem Global Worker.

## Entradas, limites e proveniência

- Arquivos exatos: dados/master_market_map_v102.json e dados/currency_news_current_v107.json.
- Esses snapshots existentes têm registros de setembro de 2026. Não demonstram frescor nem fornecem sinais atuais para negociação em outubro de 2026.
- Manifesto com source_commit (SHA relatado pelo CI, sem autoridade independente), SHA-256 e tamanho exato dos arquivos, provider_fetch_performed=false, runtime_write_authorized=false, worker_executed=false e independent_witness_enrolled=false.
- Lista fechada de dois arquivos. Rejeita Checkpoint Mestre, caminhos adicionais/absolutos/traversal/URL encoded/duplicados, symlinks e escape do checkout.
- Limite 2 MB por arquivo e 4 MB agregados, JSON UTF-8 estrito (nega duplicatas e NaN), mapeamento na raiz e nomes explícitos de chaves de credenciais. Não constitui auditoria formal de dados sensíveis.
- ZIP determinístico, validação cruzada do manifesto/hashes, escrita apenas em runner.temp e recusa de sobrescrita; artefato Actions com retenção de três dias.
- Workflow de teste contents:read, persist-credentials:false, sem segredos de provedor, sem agenda e sem executar programas de mercado/Worker. Não foi feita gravação do checkpoint.

## Evidência e interpretação

22 testes offline de segurança de conteúdo, travessia, symlink, SHA e manifestos por SO + 14 testes offline do contrato de CI por SO. O exportador também empacota os dois arquivos reais presentes no checkout e os inspeciona, sem chamadas externas. Testes reproduzidos em Ubuntu e Windows. A Quality/Security canônicas permanecem separadas e não podem ser dispensadas.

O SHA-256 interno é consistência de bytes, NÃO autenticação externa, witness de HEAD monotônico, custódia de chave, consentimento HUMAN_OWNER ou recibo de efeito de fornecedor. Snapshot histórico não comprova atualização de mercado.

## Próximos gates, não implementados

1. Extrair aquisição de mercado de persistência GitHub em interfaces distintas, permitindo executar só leitura do provedor para runner.temp sob orçamento FinOps e com testes de mocks antes de chamadas reais.
2. Definir segregação das permissões por serviço e destino de mercado; contents:write de um repositório não impõe controle por arquivo ao token, exigindo gateway ou repositório/serviço separado.
3. Validar privacidade, contratos/licenças de redistribuição e retenção de dados antes de publicar snapshots frescos em artefatos.
4. Auditar permissões administrativas reais (token default, PATs/GitHub Apps, proteção de branches e execuções) com acesso autorizado. A presente conexão não comprovou tais fatos.
5. Preservar o bloqueio A134/A135 e a operação legítima até haver arquitetura aprovada. Não integrar o congelamento A137 ou liberar Worker por conveniência.

**HARD NO-GO · 0/6 P0 homologados · Worker OFF · ZERO_AUTO_RESEND.**