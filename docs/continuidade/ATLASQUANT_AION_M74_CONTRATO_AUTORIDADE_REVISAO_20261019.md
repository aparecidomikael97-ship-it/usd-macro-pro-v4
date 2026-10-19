# AtlasQuant AION — M74: contrato de autoridade e revisao (19/10/2026)

**Estado:** desenho tecnico em LAB; nenhuma implementacao de produto homologada. HARD NO-GO.

## Base confirmada
O M71 demonstrou que a funcao de validacao direta aceita um gate READY antigo apos a reabertura de incidente (RED em Ubuntu e Windows). M73 desenvolveu adaptador somente diagnostico com 18 novos cenarios e 17 controles antigos, 35/35 PASS em cada sistema. M73 NAO corrige a funcao original M71.

## Requisitos antes de qualquer integracao operacional
1. Fonte de identidade e autoridade independente, autenticada, com escopo, emissor e vinculo de aprovacao verificaveis. Valores declarados pelo chamador nunca constituem prova.
2. Registro persistente de revisao de incidentes, com contador monotonicamente crescente, sobrevivendo a crash/reinicio; reabertura e incidente novo invalidam autorizacoes antigas mesmo dentro do TTL.
3. Diagnostico de snapshot somente com origem autenticada; ausencia, alteracao, inconsistencias ou indisponibilidade da origem causam bloqueio.
4. Uma decisao de habilitar precisa de revalidacao transacional, com compare-and-act atomico ou token de fencing verificado pelo gravador no mesmo limite de consistencia. Duas leituras consecutivas nao bastam.
5. Aprovar identidade, revisao e transacao sao verificacoes distintas. Um resultado DIAGNOSTIC_COHERENT_ONLY jamais deve virar READY por mapeamento de string.
6. Nenhum mecanismo de recuperacao pode repetir automaticamente operacoes externas incertas: preservar ZERO_AUTO_RESEND.

## Matriz de testes a implementar — todos com expectativa segura BLOCKED
- M74-01: identidade/revisao declaradas sem atestado de origem.
- M74-02: revisao inferior a ultima revisao duravel apos reinicio.
- M74-03: revisao passa por estado intermediario e volta ao valor anterior (ABA).
- M74-04: alteracao apos leitura, antes da tentativa de escrita (TOCTOU).
- M74-05: incidente reaberto dentro do prazo do gate antigo.
- M74-06: fonte indisponivel, inconsistente ou sem revisao verificavel.
- M74-07: dois executores concorrentes com mesmo ticket; somente um pode atravessar o fencing.
- M74-08: interrupcao antes ou apos gravacao nao pode deixar autoridade ambigua nem executar novamente por automatismo.

## Evidencia exigida para progresso
Congelar casos e gabarito antes da execucao. Verificar hashes da implementacao original A118. Preservar o RED M71 e os historicos Quality/Security sem mascarar falhas. Realizar ensaios Ubuntu/Windows e verificacao de chamadas reais antes de considerar uma proposta de integracao; toda mudanca em LAB/PR Draft e revisao independente.

## Bloqueios ativos
0/6 P0 homologados, Worker OFF, sem merge, deploy ou gasto extra, HARD NO-GO. A passagem dos testes do prototipo M73 comprova apenas comportamento do prototipo.

## Triagem estatica complementar — codigo original examinado
- `atlasquant_aion_authority_verifier.py`: existe verificador Ed25519 para declaracoes de autoridade, com checagem de registro de chave, vinculo de escopo e nonce persistente. Retorno positivo ainda define `execution_allowed=False` e `approval_implied=False`. Isso e um componente reutilizavel, nao homologacao de acionamento.
- `atlasquant_aion_trusted_authority_bridge.py`: consulta o verificador criptografico e recusa simples booleano previamente calculado pelo chamador. Declara `execution_allowed=False` sem autorizacao operacional.
- `atlasquant_aion_owner_signature_ceremony.py`: tem contrato para assinatura externa Ed25519 do HUMAN_OWNER, vinculado a estado assinado, mas nao faz captura de assinatura, aprovacao nem execucao.
- `atlasquant_aion_trusted_readiness_authority.py`: ausencia de raiz de confianca resulta deliberadamente em BLOCKED.
- `atlasquant_aion_global_worker_activation.py`: `activate_global_worker_feature_flag` verifica aprovacao, flag e gate, mas encerra com `_independent_activation_authority_denial()` sem gravacao habilitadora. Esta barreira deve permanecer intacta ate revisao independente.
- `atlasquant_aion_global_worker_reactivation_gate.py`: `validate_reactivation_gate_for_execution` valida conteudo, TTL, ledger e flag, mas nao consome observacao atual de incidente; esta e a lacuna reproduzida em M71.

### Consequencia de arquitetura
Evitar duplicar verificacao criptografica existente. Separar claramente: (a) identidade comprovada; (b) concessao de autoridade em escopo; (c) decisao humana; (d) revisao de incidente autenticada e persistida; (e) habilitacao atomica com escritor. A existencia de (a) ou (b) nao comprova (c), (d) ou (e).

### Status de execucao M74 nesta rodada
Branch de laboratorio criada e documento de requisitos registrado. **Nenhum teste M74 novo foi executado, nenhuma correcao de produto foi aplicada e nenhum P0 foi homologado.** Tentativa inicial de registrar suite adversarial nao concluiu; o gabarito acima continua como planejamento, nao resultado.
