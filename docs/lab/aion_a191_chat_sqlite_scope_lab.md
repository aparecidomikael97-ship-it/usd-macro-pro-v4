# A191 — regressão adversarial na persistência REAL do AION Chat (LAB)

Data: 27/10/2026. **NO-GO operacional, 0/6 P0 homologadas.**

## Escopo

Executar os métodos da classe **aion_chat.store.SQLiteChatStore REAL** em um banco SQLite
temporário com dados inteiramente sintéticos e sem nenhuma chamada de rede, IA,
provider, cloud ou cliente. Este ensaio **não desenvolve a aba Negócios** (congelada
por decisão do proprietário em 27/10); examina a camada comum de memória/conversas
que também sustenta AION pessoal, Trader e Investimentos.

## Testes executados

- Isolamento por owner/tenant/workspace em leitura da conversa, listagem, pesquisa,
  histórico, leitura exata de mensagem e contexto de busca.
- Falha fechada de gravações indevidas (archive, append, checkpoint e summary).
- Metadados de anexos, ChatService, cursores de paginação, abertura posterior e
  backup/restore com a API SQLite real.
- Observabilidade explícita de **duas limitações RED**:
  1. Quem puder construir livremente um objeto Scope com os mesmos três textos
     consegue apresentar-se como outro escopo ao SQLiteChatStore. Scope é somente
     uma estrutura de dados e **NÃO É AUTENTICAÇÃO**. Entrada confiável, sessão
     assinada e autorização por tenant no backend continuam faltando.
  2. Backup/restore local preserva a separação de consultas, mas **NÃO PROVA
     anti-rollback ou registro independente da primeira operação**.
     A190/G122 permanece 5 RED verdadeiros por SO.

## Leitura de resultados

- Verde nesta bateria significa apenas que os métodos do banco SQLite local
  obedecem ao filtro de Scope *quando Scope foi fornecido honestamente*.
- O teste de falsificação de Scope é intencionalmente um **contraexemplo RED
  observado**: seu próprio sucesso em reproduzir a fraqueza NÃO conta como P0
  resolvida.
- Para evoluir: provar quem emitiu Scope no servidor e impedir o caller de
  forjar/repinar identity/namespace; aplicar isso a todas as consultas, caches,
  anexos, auditoria e armazenamento, seguido de ensaios de invasão controlada.

## Limites

Nenhuma alteração em arquivos operacionais; apenas testes, documentação e CI
isolados. Nenhuma credencial, usuário real, envio, cobrança, negociação real,
merge, deploy ou AWS. **Sem novos gastos até 05/11/2026**. Qualquer reavaliação
financeira só a partir de 06/11 com autorização específica do proprietário.

**HARD NO-GO até homologação verdadeira das seis P0; não mascarar G122.**
