# AtlasQuant Trader — URL revisada não é comprovação de origem

Data: 04/11/2026 · LAB / HARD NO-GO · PR #1815.

## Problema

A verificação antiga aceitava qualquer URL HTTPS que tivesse o mesmo
hostname de um portal oficial listado. Isso permitia indicar um endereço
não revisado, ainda que dentro do domínio correto, como documento cuja
origem cadastral teria passado pelo controle de catálogo.

## Comportamento novo

A auditoria OFFLINE exige a URL **exata** registrada em
`SOURCES[source_id]["documentation_url"]`. Caminhos diferentes,
consultas, âncoras, grafias codificadas e portas extras não são aceitos.
Uma URL nova de divulgação oficial precisará entrar num catálogo
revisado antes de ser admitida no fluxo experimental.

A saída da verificação inclui:
- `url_matches_curated_documentation_lead_only=true`
- `page_content_or_release_authenticated=false`

Isso não estabelece que o site foi visitado, que uma publicação
existia na data alegada, que o texto foi recuperado da fonte, que
houve redirecionamento seguro, nem que há licença de uso. Os 16
endereços são **referências documentais**, não APIs verificadas,
fontes históricas point-in-time ou certificados do conteúdo.

## Testes

Três novos cenários protegem caminho não revisado no mesmo hostname,
variantes com consulta/encoding e aceitação estrutural apenas dos
16 URLs explicitamente cadastrados, sem autenticação.

A intenção não é impedir no futuro páginas específicas de
divulgação: é exigir registro, revisão e prova de custódia antes de
promover qualquer informação a fonte verificável.

Sem HTTP, Render, Worker, cron, ordens, merge, deploy ou novos custos.
Todos os vieses D1/W1/MN1 seguem AGUARDAR.
