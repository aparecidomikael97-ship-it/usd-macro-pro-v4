# AION A190 / G113 — custódia em processo separado: evidências e limites

**Data:** 2026-10-26. **PR Draft:** #1603, branch LAB. **NÃO é serviço externo nem homologação.** 0/6 P0 homologadas, HARD NO-GO. Sem merge, deploy, Worker, SEND real ou fundos.

## O que foi implementado

- **Emulador:** `labs/a190/g113_subprocess_witness_lab.py`. Cada comando invoca um processo Python separado por IPC local. O processo guarda cadastros e reservas em um segundo arquivo SQLite do mesmo computador. Nenhum socket de rede nem provedor externo é usado.
- **Cliente:** `labs/a190/g113_subprocess_witness_client_lab.py`. Verifica assinatura Ed25519 de nonce, evento de negócio, origem, escopo, efeito, idempotência, ordinal e contador com chave pública previamente fixada na fixture. Uma resposta `ALREADY_RESERVED`, mesmo assinada corretamente, não é aprovação de novo envio.
- **Transação:** inclusão atômica por evento de negócio com `BEGIN IMMEDIATE`, high-water crescente e assinatura somente depois de `COMMIT`. O mesmo evento com novo request ID não cria outra reserva. Eventos legítimos distintos podem compartilhar o mesmo payload; dependem de IDs de evento distintos previamente cadastrados.
- **Recuperação:** resposta perdida após possível COMMIT deve ser tratada como `UNCERTAIN`; consultar status antes de qualquer ação e não reenviar automaticamente. O desaparecimento do Outbox local não apaga o segundo arquivo de demonstração.
- **Bootstrap:** somente comando explícito de laboratório. A ausência do arquivo não cria banco vazio automaticamente durante `status`/`reserve`.

## Evidência objetiva

[GitHub Actions G113 40365730794](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40365730794), commits fonte `bf533a60747e6801020edd76c4032e31e027cae8`:

- Ubuntu: **13/13 PASS**, job `121722780495`.
- Windows: **13/13 PASS**, job `121722780221`.
- Assinatura mantida entre reinícios; reservas duplicadas recusadas; perda de ACK após COMMIT não dá novo direito; desaparecimento do arquivo local não apaga o segundo arquivo; evento desconhecido/identidade alterada/assinatura falsa/replay recusados; quatro subprocessos concorrentes reservam uma vez.
- **Controle negativo deliberado:** `G113_SAME_HOST_WITNESS_ROLLBACK=STILL_VULNERABLE_NOT_P0`. Um operador com acesso ao segundo arquivo SQLite restaura uma cópia antiga e o mesmo evento pode ser reservado novamente. Este é um bypass reproduzido, NÃO proteção comprovada. O teste verde atesta que o ataque ainda funciona.

## Por que G113 ainda NÃO é independente

1. Testes, processo de assinatura, arquivo SQLite e host são administrados pela mesma autoridade. O operador controla as chaves sintéticas e pode recriar o banco.
2. A chave privada de fixture é transmitida na linha de comando do processo (VISÍVEL a um administrador do host); isso jamais será permitido numa implementação de produção.
3. O comando `enroll_synthetic_only` aceita um evento de negócio informado pelo próprio chamador. Logo, a origem original continua NÃO autenticada externamente.
4. Não existe armazenamento remoto imutável/monotônico, isolamento de credenciais, proteção contra restauração da própria custódia ou atestação do VFS SQLite nativo.
5. O cliente não está integrado ao Worker nem a um fornecedor real. Um recibo G113 não é licença para SEND.

## Critérios obrigatórios da próxima fase G114+ (sem contratação/deploy agora)

| Requisito | Evidência de implantação real, não do mesmo host |
| --- | --- |
| Isolamento da autoridade | Serviço e banco sob credenciais, operação e retenção independentes; AION sem privilégio de restaurar/apagar o histórico |
| Origem do evento | Inscrição original verificada pelo proprietário/fonte de negócio; mesmo payload não confunde eventos distintos; novo ID técnico não altera identidade original |
| Chave confiável | HSM/KMS ou mecanismo equivalente mantido fora do host e do pedido; chave pública provisionada previamente em local protegido |
| Resolução de COMMIT incerto | Recibo e status verificáveis após queda/timeout/restart, sem nova reserva ou SEND automático |
| Antirollback | Restauração do host e de todos os seus arquivos NÃO restaura autoridade; testemunha independente mantém contador e evento já gasto |
| SQLite nativo | Vínculo da versão atestada à instância VFS/handle em leitura e admissão de escrita, inclusive restauração do MESMO inode |
| Governança/custos | Quotas/limites, auditoria, LGPD, isolamento de tenants e justificativa antes de qualquer custo adicional |

As cinco exigências reais A184 permanecem deliberadamente RED, sem skip/xfail/waiver. CI local verde, sozinho, jamais fecha P0.

## Decisão pendente antes de integração real

Escolher e autorizar um custodiante externo concreto, com orçamento e plano de retenção de chaves/dados, após análise do custo total do AtlasQuant. Até lá, continuar com especificações, teste de protocolo e PRs Draft, sem provisionar contas, segredos, infraestrutura paga nem executar operações reais.

**0/6 P0 HOMOLOGADAS · HARD NO-GO · NO MERGE / DEPLOY / WORKER / SEND / FUNDOS.**
