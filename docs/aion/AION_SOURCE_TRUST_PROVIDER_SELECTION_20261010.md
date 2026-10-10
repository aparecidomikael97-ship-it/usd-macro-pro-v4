# AION — escolha da autoridade de origem e witness independente

Data de elaboração: 10/10/2026. Issue P0 #1178. **Design, não implantação**. Base Draft #1181: bd1d301a80edcb1beadc4e73ab56e6b810016817.

## Decisão de segurança atual

O Global Worker e a verificação de ativação permanecem **BLOQUEADOS** enquanto não existir origem independentemente matriculada. O SHA do GitHub, token, login ADMIN, conteúdo self-signed, relógio local e um snapshot trusted passado pelo chamador não concedem propriedade, frescor ou antirollback.

A referência Ed25519 da Draft #1179 é offline e recebe um valor supostamente trusted. Ela **não** constitui uma âncora de confiança. A Draft #1180 impõe o veto no runner, a #1181 impõe NO-GO no relatório, e o novo componente de readiness evita até GET não autorizado do checkpoint enquanto a fonte for desconhecida. Nenhuma dessas etapas provisiona testemunha independente.

## Modelo de confiança mínimo futuro (proposta)

**Identidade:** matriz de propriedade entre HUMAN_OWNER, uma organização e um workspace B2B, com atribuições assinadas e revogáveis por servidor confiável, isoladas de campos do próprio checkpoint. Cada arquivo individual é identificado por repositório canônico, branch dedicado, path e SHA do conteúdo. Um administrador de tenant B não pode promover uma origem de tenant A.

**Raiz:** par público do provedor de matrícula instalado em canal verificado fora do GitHub/branch/runtime, com versão de enrollment, autoridade humana, validade e provas de rotação. Chaves privadas nunca entram no código fonte, ações de CI, prompt, arquivo runtime ou logs.

**Cabeça monotônica:** serviço/witness em domínio de persistência e administração independente do repositório e do próprio aplicativo. Retorna sequence/commit SHA/digest e tempo assinados, em protocolo com desafio anti-replay, custódia fora do domínio de rollback e consulta fresca antes de qualquer ação. Um único JSON no mesmo GitHub **não** é witness independente. Offline sem acesso ao witness implica NO-GO.

**Assinaturas:** source e witness devem ser chaves/autoridades distintas, envelopes canônicos com domain separation e vinculação a owner/tenant/workspace/resource, sequência, digest e expiração. Não supor que dois keypairs gerados pelo mesmo processo criem independência.

**Controles operacionais:** MFA/biometria para enrollment/rotação crítica do proprietário; trilha auditável de aprovação; fail-closed por revogação, relógio inconfiável, witness offline, divergência SHA, troca de namespace, CAS/UNKNOWN_OUTCOME, token reutilizado, falha de leitura e ruptura da custódia. Não apagar UNKNOWN_OUTCOME para fingir conclusão.

**Gate do Worker:** autenticador obtém identidade e witness por canal próprio; só um verificador interno aprovado lê o checkpoint e valida readback; depois dos claims CAS e antes do executor, revalida frescor/autoridade e fencing. Não aceitar prova autoenviada por request/session_state. Proibir fallback positivo e flag de bypass. O relatório de readiness deve refletir o mesmo estado.

## Opções para futura escolha, nenhuma aprovada

1. **Serviço externo independente de auditoria append-only + chaves de matrícula fora do GitHub.** Maior adequação a cenários B2B/tenant e comprovação de antirollback, mas envolve governança, custo/latência, disponibilidade e gestão de chaves a investigar.
2. **Dispositivo seguro controlado pelo proprietário (Windows Hello/TPM/FIDO2) + witness externo distinto.** Oferece confirmação física do proprietário, mas um TPM local sozinho não dá testemunha remota monotônica, não resolve indisponibilidade do computador e precisa validação física na máquina autorizada.
3. **Armazenamento local sem testemunha externa.** Útil para estudo offline ou restauração, mas **não satisfaz** fonte independente/antirollback para ativar Worker de produção.
4. **Assinatura e SHA armazenados no mesmo branch GitHub.** Rejeitar como prova independente: um rollback/rewrite pode devolver ambos em conjunto.

### Antes de qualquer implementação positiva

- Levantar opções concretas e custos dentro do orçamento existente, sem adquirir serviços.
- Aprovar a escolha de autoridade/custódia, recuperação e política de revogação com o HUMAN_OWNER.
- Matricular e autenticar as chaves num ambiente autorizado; nunca por código de teste sintético.
- Exigir testes de chave comprometida, rotação, rollback/replay, interrupção do witness, A→B, revogação, CAS conflitante e relógio, Win/Linux + verificação física do proprietário.
- Somente após isso propor autorização separada para integração real, merge, deploy e instalação.

Estado: PARTIALLY_CLOSED / HARD NO-GO, sem autorização para Worker, armazenamento remoto novo, gasto, migração, chaves reais ou deploy.
