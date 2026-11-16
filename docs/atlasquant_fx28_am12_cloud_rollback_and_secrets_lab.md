# AtlasQuant Trader — AM12 → nuvem: risco de rollback e provisionamento de segredos (LAB)

**Escopo:** somente o resumo de 20 campos de quarentena FX28, sem OHLC, login, número de conta, credenciais, arquivo do MT5 ou timestamp de preço. NÃO constitui autorização de transporte, produção, implantação, operações nem sinal. **LAB / AGUARDAR / HARD NO-GO.**

## O que foi realmente demonstrado

1. O arquivo M15 de 15/11 foi examinado em modo somente leitura: **672 slots preservados, 56 primeiros D1/W1 sem rotulagem de preço (28 pares), 616 não avaliados**.
2. Um envelope HMAC-SHA256 estrito de resumo de laboratório tem integridade, validade de 300 segundos e contador de sequência, usando chave pública **apenas de teste**.
3. Um banco SQLite transitório, criado somente nos testes, grava o contador antes de liberar o resumo: mensagens repetidas após abrir nova conexão ao **mesmo banco íntegro** são rejeitadas.
4. O novo `atlasquant_trader_fx28_external_replay_anchor_guard_lab.py` **compara** o contador/digest locais com um *checkpoint* externo assinado e amarrado a desafio novo. Na suíte, um checkpoint é produzido por helper **sintético**, sem serviço remoto real. Teste de cópia antiga do SQLite resulta em `LOCAL_DB_BEHIND_EXTERNAL_ANCHOR_POSSIBLE_RESTORE`. A igualdade retorna sempre **NO-GO**: validação do HMAC não comprova origem independente do serviço, segurança do armazenamento, relógio, identidade AM12 nem dados Pepperstone.

## Modelo de ameaças e resposta

| Risco | Resposta exigida | Implementado? |
|---|---|---|
| Repetição de recibo enquanto SQLite não foi alterado | Sequência maior que piso e `BEGIN IMMEDIATE`, CAS e `COMMIT` pré-display | **Sim, LAB** |
| Reinicialização de processo | Reabrir a mesma base privada com sequência preservada | **Testado, LAB** |
| Banco SQLite restaurado para snapshot anterior | Consultar autoridade EXTERNA, independente, monotônica e resistente a restore; comparar sequência + digest | **Somente comparação LAB com dados sintéticos** |
| Restauração também da fonte externa | A fonte externa deve possuir fronteira de backup/retenção e identidade operacional separadas; jamais confiar em dois backups do mesmo disco | **Não** |
| Oscilação, incerteza ou falha da fonte externa | **Bloquear; não reaproveitar último checkpoint nem zerar contador** | **Contrato de negação, sem serviço** |
| Crash entre alteração do contador externo e commit SQLite | **Bloquear e exigir reconciliação humana/auditável**; não permitir reset automático | **Somente procedimento proposto** |
| Credenciais copiadas ou ambiente cloud comprometido | Segregação e rotação, acesso mínimo, revogação, auditoria independente e revisão de segurança | **Não provisionado** |
| Relógio local falsificado | Relógio de referência independente e monitoramento de desvio; HMAC do tempo não cria prova de horário real | **Não** |
| Origem dos ticks/candles Pepperstone | Evidência broker + MT5 com `time_msc`, recibos contemporâneos e verificação de timezone | **Não** |

## Contrato de segredos — sem implantação

- **Separar pelo menos dois materiais criptográficos**, nunca usar a mesma chave para envelope AM12→Radar e checkpoint da autoridade externa. A chave do checkpoint deve permanecer sob administração **independente** do AM12 e do banco SQLite restaurável.
- **Provisionar fora do código e fora do repositório**, por cofre de segredos com controle de acesso mínimo, trilha de auditoria e capacidade de revogação; ambiente cloud recebe credencial via mecanismo secreto do provedor. Não copiar valores para issue, pull request, GitHub Actions, screenshot, log, arquivo .env versionado, notebook ou interface.
- **AM12:** se for instalado serviço no futuro, privilegiar cofre de credenciais do Windows protegido para conta de serviço exclusiva. Não presumir que o armazenamento local prova identidade física do computador.
- **Nuvem:** usar gerenciamento de segredos da hospedagem com rotação, escopo de leitura restrito ao receptor e auditoria; garantir que logs não imprimam conteúdo de `Authorization`, chaves ou corpo assinado. Nenhum serviço ou preço de fornecedor foi contratado nesta etapa.
- **HMAC é simétrico:** quem possui a chave pode gerar e validar mensagens. Mesmo com HMAC correta, não há prova criptográfica de “este dispositivo AM12”; para evoluir para clientes, avaliar assinatura assimétrica com chave privada isolada, dispositivo/identidade autenticados e verificação pública no cloud, mediante revisão.
- **Rotação/comprometimento:** versão nova de `key_id` e esquema, janela definida de troca, revogação do identificador anterior, nova cadeia monotônica autorizada. **Nunca zerar sequência nem reaproveitar identificador como atalho**. O módulo HMAC atual fixa `fx28-status-lab-v1`; mudar isso exige novo protocolo, testes, aprovação.
- **Nonce e clocks:** nonce novo imprevisível de 128 bits por desafio, gerado por fonte criptográfica aprovada pelo receptor; timestamp de expiração curto; fonte de tempo independente. O helper local de `synthesize_..._for_offline_tests_lab` jamais pode ser tratado como emissor externo real.

## Recuperação e disponibilidade: procedimento obrigatório

1. Parar qualquer leitor/transportador/gerador de resumo; manter `NO-GO` mesmo se painel ficar sem dados.
2. Identificar a causa da restauração, hashes e versões, comparar checkpoint externo adquirido com desafio inédito e SQLite, verificar integridade das duas fronteiras e eventuais logs independentes.
3. Em qualquer divergência, **não corrigir automaticamente o contador**, não reemitir último recibo, não alterar os dados de mercado, não reusar mensagem para atualizar a tela.
4. Só retomar eventual ingestão futura após análise humana autorizada, procedimento de reconciliação comprovado e novos testes de crash/concorrência. Este runbook **não** autoriza bootstrap nem recuperação.
5. Se a fonte externa estiver inacessível, a interface permanece `NAO_CONECTADO` ou `HARD NO-GO`.

## Critérios antes de considerar um transporte real

**Pendências obrigatórias**: escolha de serviço externo realmente monotônico (com CAS e domínio independente de backup), segurança de segredo e IAM; TLS autenticado/controle de acesso; armazenamento cloud sem rollback simples; política de retenção; demonstração de falha fechada em *crash* e restauração; rotação/revogação de chaves; autorização explícita de conexão; integração com o backend do Radar e revisão de privacidade.

Mesmo após tudo isso, o resultado transmite **somente metadados de quarentena**. Não representa calibração do viés, previsões point-in-time, prova de preço de abertura, lucro, nem permissão de operar. A campanha write-once de 15/11 e os 672 slots **não podem ser reprocessados retroativamente como evidência pré-evento**.
