# AtlasQuant — Handoff das Dependências Externas

Este documento começa exatamente onde a preparação interna termina. Nenhum item abaixo é marcado como concluído apenas porque existe código, checklist ou rascunho no repositório.

## 1. Jurídico e privacidade

**Já preparado internamente**
- rascunho de Termos de Uso;
- rascunho de Política de Privacidade;
- rascunho de Divulgação de Riscos;
- mapa de dados e terceiros a revisar.

**Ação externa necessária**
- definir entidade responsável;
- jurisdição/foro e canais de contato;
- política de cancelamento/reembolso;
- retenção de dados e direitos do titular;
- revisão jurídica/profissional aplicável.

**Evidência de conclusão**
- documentos finais aprovados, versionados e publicados;
- responsável/aprovação registrada.

## 2. Licenciamento comercial de dados

**Já preparado internamente**
- inventário técnico de FRED, BCB/SGS, NewsAPI, EODHD, Twelve Data, Google News RSS, endpoint de tradução, calendários Fed/ISM;
- checklist de uso comercial, cache, redistribuição e retenção.

**Ação externa necessária**
- revisar termos/plano de cada fonte;
- contratar/autorizar tiers comerciais quando exigido;
- registrar limitações de exibição/redistribuição.

**Evidência de conclusão**
- documentação/contrato aplicável para cada fonte usada no produto público.

## 3. Pagamento e assinatura

**Já preparado internamente**
- contrato técnico fail-closed de eventos de billing;
- estados de assinatura;
- regra de não armazenar cartão;
- checklist de webhook, idempotência, cancelamento e reembolso.

**Ação externa necessária**
- escolher provedor;
- criar conta comercial;
- configurar sandbox/produção;
- implementar integração real e webhook assinado;
- validar impostos, preços e política de cancelamento.

**Evidência de conclusão**
- testes sandbox aprovados;
- evento assinado validado;
- fluxo de assinatura/cancelamento/reembolso testado;
- revisão humana antes de ativar produção.

## 4. Assistente de voz

**Já preparado internamente**
- contrato TTS;
- transcript imutável;
- geração somente por ação explícita;
- isolamento total do trading.

**Ação externa necessária**
- escolher/configurar provedor TTS;
- armazenar chave no secret store;
- validar voz, custo, limites e privacidade;
- conectar retorno de áudio ao player.

**Evidência de conclusão**
- áudio real validado sem expor secret;
- fallback testado;
- `voice_ready` só deve mudar depois disso.

## 5. Vídeos da Academy

**Já preparado internamente**
- currículo textual;
- roteiro e storyboard de todas as aulas;
- duração estimada e aviso educacional.

**Ação externa necessária**
- renderizar mídia final;
- revisar áudio, legendas e identidade visual;
- hospedar/publicar em canal aprovado.

**Evidência de conclusão**
- arquivo/URL final por aula;
- revisão visual e educacional;
- todos os tópicos associados a mídia válida.

## 6. Google Play e Apple App Store

**Já preparado internamente**
- PWA funcionando;
- metadados base;
- checklists Android/iOS;
- separação entre preparação e publicação.

**Ação externa necessária**
- contas de desenvolvedor;
- toolchain autorizado;
- assinatura de pacotes;
- testes em dispositivos;
- políticas de privacidade/dados e metadados finais;
- submissão às lojas.

**Evidência de conclusão**
- pacote assinado;
- versão/release id;
- resultado da revisão/publicação de cada loja.

## Regra final

Mesmo quando todas as dependências externas forem concluídas, o lançamento continua exigindo revisão humana final. Isso não habilita broker nem ordens reais.
