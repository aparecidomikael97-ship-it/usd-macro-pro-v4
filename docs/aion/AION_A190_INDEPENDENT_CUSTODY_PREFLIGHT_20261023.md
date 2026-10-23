# A190 PRE-FLIGHT — fronteira independente de confiança e custódia monotônica

Data: 2026-10-23. Escopo: somente decisão arquitetural em LAB; sem execução de efeito real. Vinculado à missão #1486. Base: PR Draft A189 #1485, commit 6457552ae2b26d8fc4e550a59d8aad1ee90e54fc.

**Estado observado:** 0/6 P0 homologados; HARD NO-GO; UNCERTAIN; ZERO_AUTO_RESEND. Nenhum merge, deploy, Worker, conta, credencial, pagamento ou contratação é autorizado por este documento.

## 1. Evidências e limite do experimento anterior

- A189, GitHub Actions #39959614969: dois jobs concluídos com sucesso, Ubuntu/Windows; logs conferidos neste preflight: 10 testes A189 e 21 regressões anteriores em cada SO. PASS demonstra cenários locais e contraexemplos, não segurança operacional.
- A189 demonstrou que um rollback de apenas SQLite **ou** apenas witness local é detectado, mas rollback **conjunto** SQLite+witness e falsificação de witness com hash recalculado são aceitos.
- A184 canônico no mesmo head, #39959614735: os jobs Quality, Security unittest e Security pytest candidatos encerraram com sucesso; os cinco requisitos externos de ambos SO e a auditoria de dependências permaneceram RED. Quantidades 6413, 368 e 2825 e 43 alertas constam do relatório e do comentário de rastreio #1477, sem nova recontagem de todos os logs por este preflight.
- A188 isolou a conexão em subprocesso, mas expôs bypass por acesso SQLite bruto ao mesmo arquivo e restauração offline. A187 mostrou que a fábrica Python pode ser falsificada e o handler removido. Nenhum desses controles cria autoridade independente.

**Nova hipótese estática a testar (NÃO executada neste preflight):** em A189, bootstrap_synthetic nega um novo genesis se **algum** dos dois arquivos existir. Se o atacante remover **ambos**, a condição de existência deixa de bloquear genesis; a função cria um novo ledger vazio e witness seq=0. Um novo processo pode então reservar de novo um evento anteriormente reservado. Isso é variante precisa de dual rollback, agora por destruição total+rebootstrap. O futuro teste G0 deve verificar saída e exata linha causal; não registrar como reprodução dinâmica ainda.

## 2. Modelo de ameaças e linhas de autoridade

Atacante A: código do aplicativo/plug-in AION comprometido rodando como usuário do aplicativo; pode chamar Python, criar conexões SQLite, editar os próprios arquivos, controlar request_id/event_id e provocar perda de ACK.

Atacante B: administrador/root do **mesmo host**, com poderes para substituir processos/ACL, restaurar snapshots de disco e extrair segredos acessíveis no host. Um guard no mesmo host não deve prometer resistir a B. Uma testemunha que compartilha disco, backup, conta e root de confiança com A/B não é independente.

Falhas não maliciosas: crash entre commits, queda de energia, WAL/SHM atrasado, ACK perdido depois de efeito, failover para snapshot antigo, revogação e ausência do custodiante H0.

| Principal/ativo | Pode autorizar | Não deve poder |
| --- | --- | --- |
| HUMAN_OWNER autenticado por desafio vinculado à ação | decisão humana explícita, com escopo e prazo | fabricar recibo de fornecedor; ignorar UNKNOWN |
| Orquestrador AION, não confiável para a raiz | solicitar intenção canônica e consultar evidência | alterar piso monotônico, raiz, recibo, WAL/SHM protegido ou liberar retry |
| Serviço store em identidade OS própria | transações locais e validação dos comandos allowlisted | ser autoridade de emissão da própria raiz ou prova de efeito externo |
| Custodiante independente | CAS de epoch/sequence, revogação e recibo verificável sob raiz previamente fixada | aceitar re-enrollment silencioso, substituir histórico por snapshot do cliente |
| Autorizador/fornecedor do efeito | recusar mesma chave semântica, emitir resultado assinado/autenticável | assumir que um request_id novo equivale a evento novo sem prova de origem |
| Auditor/operador humano | reconciliar provas discordantes e liberar nova intenção quando cabível | transformar silêncio/timeout em sucesso ou resend automático |

**Regra de confiança:** não contar duas assinaturas como independentes se o mesmo processo controla as duas chaves, nem dois arquivos como dois domínios de falha se o mesmo host os reverte.

## 3. Alternativas comparadas — decisão provisória

| Caminho | O que consegue demonstrar | Limite incontornável isoladamente | H0 offline / custo |
| --- | --- | --- | --- |
| A — serviço local com usuário OS separado, ACL no arquivo + WAL/SHM, IPC allowlisted | app de menor privilégio não lê/grava SQLite diretamente, se SO efetivamente negar | admin/root, rollback de host, origem de eventos e efeito remoto | pode operar localmente em escopo limitado; manutenção/compatibilidade Windows/Linux; sem custo contratado |
| B — testemunha monotônica em principal e host independentes, chave/raiz fixada fora do app | reabertura após rollback local abaixo de piso remoto pode falhar fechada | sozinha não prova que fornecedor realizou, não realizou ou duplicou um efeito; outage impede novas escritas seguras | offline: negar novas reservas/efeitos; potencial custo de operação/conectividade não cotado |
| C — serviço transacional/fornecedor com idempotência de evento original e recibo independente | pode ordenar a primeira reserva e correlacionar efeito/ACK, **se contrato de API comprovado** | nem todo fornecedor garante efeito exatamente uma vez; ambiguidades e indisponibilidade persistem | offline: nenhum novo efeito; contratos e custo ainda desconhecidos |

**Escolha de direção para protótipo, não decisão de compra:** A como defesa em profundidade; B como autoridade anti-rollback; C como condição de qualquer efeito real cuja primeira tentativa/resultado precise ser provada. A+B sem C pode proteger história, mas **não** certificar efeito externo ou idempotência semântica. Se não houver B independente ou contrato C comprovável, não integrar execução real. Evitar novo hash/contador no mesmo host como substituto.

TPM/HSM/FIDO2 podem proteger identidade/chaves sob condições específicas, mas não presumir que contador, anti-rollback, atestado remoto, idempotência e recuperação H0 estejam disponíveis/seguros sem provas de hardware, plataforma, políticas de backup e restauração.

## 4. Protocolo mínimo candidato

1. Capturar intenção imutável com evento original autenticado, escopo, payload canônico, hash, HUMAN_OWNER quando exigido, nonce e validade. Rejeitar evento derivado só de texto do próprio cliente.
2. Consultar identidade e epoch/raiz fora do aplicativo; validar cadeia de chaves, rotação, revogação, versão e relógio/expiração. Se não confiável ou indisponível, **DENY**.
3. Antes de qualquer efeito, custodiante independente faz uma reserva condicional monotônica CAS(event_id original, intention_hash, sequence/epoch). A negação, timeout ou ACK incerto não permite outra primeira tentativa.
4. Aplicar política de fornecedor com chave de idempotência semântica, se e somente se seu contrato garantir semântica verificável. Nenhum código chama resend automaticamente.
5. Guardar recibo emitido pelo principal do efeito, com vinculação à reserva original, estado final, sequência e identificação de emissor validada por raiz independente. Hash SHA-256 do próprio app não conta como recibo.
6. Se ACK perdido ou desfecho externo inconclusivo: **UNCERTAIN** persistente, sem retry; reconciliação por leitura autenticada do custodiante e fornecedor, ou revisão humana. Observação local não autoriza sucesso.
7. Em reinício H0, rejeitar qualquer epoch local abaixo do piso independente; não fazer auto-bootstrap se arquivos, witness, credenciais ou recibos faltarem. Um novo genesis exige cerimônia auditável independente, nunca reset por deleção.

## 5. Gates falsificáveis — testes exigidos antes de propor integração

| Gate | Ensaio obrigatório | Critério de aceitação | Falha/NO-GO explícito |
| --- | --- | --- | --- |
| G0 — destruição dos dois arquivos | reservar r1/e1; eliminar SQLite e witness sintéticos; tentar bootstrap e re-reserva r1/e1 | controle futuro independente nega, nunca reautoriza r1 | implementação A189 local isolada presumivelmente reabre; reproduzir sem mascarar |
| G1 — principal OS | app de UID/SID de menor privilégio tenta SELECT, INSERT, abrir WAL/SHM, renomear arquivo e apontar VFS base | cada acesso hostil é negado e logs/UID/SID/permissões comprovam processo real | OS_DENIED sem exercer operação/guard inválido, admin/root acessando tudo sem delimitação |
| G2 — rollback conjunto | snapshot antigo de DB+WAL+SHM+backup+witness local restaurado, mas piso remoto preservado | custodiante independente rejeita epoch stale e qualquer re-enrollment silencioso | se mesma conta/host puder retroceder também o piso, RED |
| G3 — evento/primeira tentativa/ACK | IDs diferentes para mesmo evento original; crash antes/depois do efeito e ACK perdido | uma única autorização de primeira tentativa; resultado UNKNOWN sem resend; recibo legítimo do fornecedor para confirmação | event_id autoalegado, recibo autoassinado ou inferência de sucesso pelo DB |
| G4 — Windows/Ubuntu reais | repetir G1–G3 com IDs de conta distintos, regressões SQLite live, FD/VFS, cache, WAL/SHM, ABA/same-inode, power-loss quando viável | jobs/exit code/asserts + logs que mostram operações exercidas, Windows e Ubuntu separados | experiência só Linux, simulação Python ou comportamento OS_DENIED não exercido não homologa |
| G5 — dependências/gates canônicos | executar Quality/Security com os mesmos seletores e external-RED | os cinco requisitos só deixam RED mediante evidência independente pertinente; audit tratado em trilha própria | skip/xfail/continue-on-error, esconder 43 advisories, ou divulgar CI global verde com gate externo vermelho |

**Desenho do menor ensaio OS permitido:** usar runners efêmeros, contas temporárias de laboratório, arquivos totalmente sintéticos e nenhuma credencial; imprimir UID/SID do escritor legítimo e atacante, ACL efetiva, caminho do banco e resultado de acesso raw. Os testes devem verificar que o ator legítimo **consegue** o mesmo acesso que o não privilegiado é impedido de fazer. Windows e Ubuntu têm APIs e escaladas distintas; nunca extrapolar resultado de um SO ao outro. Não usar root/admin como prova do isolamento contra root/admin.

## 6. Critérios de procedência para futuro recibo

Objeto canônico proposto (sem dados reais): schema_version, issuer_id, independently_pinned_key_id, trust_epoch, monotonic_sequence, authenticated_original_event_id, request_id, canonical_intent_sha256, nonce, scope, decision, expiry, revocation_reference, previous_checkpoint_digest, provider_transaction_id, provider_outcome, issued_at, signature.

Obrigatório: domínio de emissão que não aceite que o próprio aplicativo escolha issuer/root/key_id; desafio de proprietário vinculado ao objeto exato; verificações de replay, substituição de chave, rotação/revogação, ordem e conexão ao efeito do provedor. A resposta com todos esses campos assinada por chaves de fixture continua **não autenticada externamente**.

## 7. H0, disponibilidade e política de custo

- Se custodiante/fonte de recibos não responde na inicialização H0: sistema sinaliza indisponibilidade de autoridade; nenhuma nova execução, reserva, envio ou migração. Pode oferecer visualização de histórico local com rótulo **não verificado/desatualizado**, sem apresentar como fonte autoritativa.
- Recuperação após outage requer leitura autenticada do piso monotônico e reconciliação; proibir fallback silencioso para witness local, snapshot antigo ou chave autocriada.
- Orçamento histórico do produto: teto operacional R$200/mês; exceção pontual até R$250 **somente mediante justificativa e aprovação do proprietário**. Custos de serviço remoto, tráfego, retenção, HSM e manutenção devem ser cotados antes de qualquer provisionamento. Neste preflight: **R$0 de nova despesa autorizada ou incorrida**; não há cotação verificada.
- Não escolher solução pela menor latência/preço antes de comprovar as garantias contratuais e a disponibilidade H0.

## 8. Evidência, estado e próxima ação

Este arquivo é **preflight estático**, não prova os gates G0–G5, não executa workflow novo, não altera módulos do runtime e não é PR de homologação. Os dados do A189 foram conferidos por leitura de diff + workflows/logs; a interpretação G0 é hipótese de revisão estática.

**Próximo passo executável da A190:** reproduzir G0 em runner efêmero, depois construir G1 com dois principais OS reais e controles positivos/negativos. Registrar os bypasses de B (admin/root) como RED, medir manutenção e comparar com B/C sem contratar. Se não houver domínio externo de confiança verificável para G2/G3, parar a implementação operacional e solicitar a decisão do proprietário.

**Status não negociável:** P0-1 a P0-6 = NÃO HOMOLOGADOS; 5 external-RED por SO; 43 vulnerabilidades herdadas; HARD NO-GO; ZERO_AUTO_RESEND; UNCERTAIN. Sem main, merge, deploy, Worker, broker real, credenciais reais, serviço pago ou efeito real.
