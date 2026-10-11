# AION — consolidação V1–V5 e protocolo físico mínimo V6

**Revisão:** 11/10/2026. **Base:** Draft #1221, HEAD 2acae11ae76e300fae879bb1fd442409eb1e63c6. **Estado:** FIRST INSTALL = HARD NO-GO.

## 1. Escopo real auditado

Foi revisado o papel dos contratos de referência V1–V5 e seu manifesto de 20 requisitos bloqueados. A aprovação dos testes offline não autoriza uma cerimônia humana, matrícula externa ou instalação.

| Camada | Fontes de referência | Demonstrações limitadas | NÃO comprova |
|---|---|---|---|
| V1 | ceremony.py, windows.py, plan.py | Escopo e requisitos de identidade e host simulados | Proprietário ou Windows físicos verificados |
| V2 | webauthn_reference.py, causal_readback_reference.py, evidence_dossier_reference.py | Assinatura WebAuthn offline, readback e dossiê sintético | Autenticador de produção ou proveniência institucional |
| V3 | ledger_storage.py, webauthn_ledger_reference.py | Challenge e credential SQLite local, reinício e concorrência | Resistência à restauração privilegiada |
| V4 | commitments.py, signed_anchors.py, recovery_bridge.py | Compromissos, assinaturas e divergências entre fixtures | Trusted clock, WORM ou witness externo |
| V5 | receipt_admission.py, epoch_root_reference.py | Consumo local de nonce/recibo e validação matemática de troca de raiz | Raiz realmente matriculada, consenso externo ou autorização de install |

Os módulos V3 e V5 têm dois bancos SQLite experimentais distintos. A transação local de cada um NÃO fornece atomicidade entre bancos ou instituições. Antes de qualquer conexão operacional, é obrigatório especificar protocolo causal entre ledgers, idempotência, readback sem reescrita, tratamento UNKNOWN_OUTCOME e prova externa.

**Limitação HIGH:** a restauração conjunta de todos os bancos, pins, floors e âncoras sob uma só autoridade pode manter um estado antigo autoconsistente. Chaves e processos separados mas controlados pelo mesmo operador não constituem custódia independente.

A V6 inclui apenas um relatório read-only em atlasquant_aion_first_install_preparation_v6/consolidation.py, com 13 fontes registradas, fases de 20 gates e riscos. O relatório não executa métodos produtivos e não consegue conceder GO.

## 2. Protocolo mínimo para validação física futura

### P0 — consentimento de inventário

Antes de qualquer comando Windows, obter autorização explícita e independente especificando: host exato em canal privado, operador responsável, janela de execução, comandos de leitura previamente revisados, recursos permitidos, destino privado dos resultados e parada imediata diante de elevação de privilégio ou saída sensível. NÃO inferir aprovação a partir de uma mensagem genérica de continuidade do projeto.

**A V6 NÃO contém comando ou scanner de host**. Esta PR prepara apenas o protocolo.

### P1 — leitura de capacidades do host (somente após P0)

Verificar edição/build/arquitetura e atualizações do Windows, presença declarada de soluções de proteção e possibilidades de isolamento. Não ler secrets, credenciais, chaves, registros de biometria, PIN ou dados pessoais. Qualquer comando que possa sair da máquina ou coletar identificador sensível requer revisão e aprovação distinta.

### P2 — artefato instalador (outra autorização)

Revisar publisher, cadeia de confiança, assinatura e hash do futuro pacote sem executá-lo. No momento não há comprovação de assinatura do instalador nesta Draft. Uma verificação de pacote não concede sua execução.

### P3 — recuperação, rede e empresas (outra autorização)

Preparar testes descartáveis A/B, ACL por processo, isolamento de egress e cenários de corrupção, falha e restauração. Não rodar testes físicos, de rede, power loss ou dados reais nesta etapa.

### P4 — witness externo, LGPD, FinOps e release (autorizações distintas)

Exigir matrícula independente da raiz, custódia distinta, sequência monotônica, head autenticado, WORM/versioning e reconciliação causal. Fazer avaliação LGPD/fornecedores/residência e orçamento integral versus referência temporária R$ 200/mês. Compra, merge, deploy, instalação e Worker são decisões separadas do proprietário, não consequências de CI verde.

## 3. Quadro de decisão atual

| Ação | Estado |
|---|---|
| Auditar e documentar V1–V5 offline | Em andamento / escopo autorizado |
| Preparar roteiro do Windows | Documento, sem leitura física |
| Executar inventário Windows | NÃO AUTORIZADO por esta Draft |
| Usar TPM/FIDO2/Windows Hello | NÃO TESTADO; MATRÍCULA BLOQUEADA |
| Criar ou ativar witness externo | BLOQUEADO |
| Instalar AION | HARD NO-GO |
| Ativar Worker, merge e deploy | BLOQUEADO |
| Gastar ou provisionar fornecedor | BLOQUEADO |

## 4. Prova e privacidade

O futuro dossiê deve vincular cada um dos 20 gates a escopo, experimento negativo, origem independente, carimbo de tempo verificável, hash, revogação e decisão do verificador. Nenhum PIN, chave privada, token, dado de cliente, assinatura biométrica ou documento pessoal deve aparecer em PR, CI ou log público. Preencher uma URI, um SHA ou o texto VERIFIED não é prova independente.

Os testes da V6 devem demonstrar que qualquer falsificação de owner, status, recibo ou fase deixa o resultado em HARD_NO_GO. Existência de fonte é apenas inventário, não prova do funcionamento nem atestado do software.

## 5. Critérios de encerramento e próximo trabalho

CI específica Windows e Linux + Quality global original Linux sobre HEAD final. O manifesto original permanece inalterado: 20/20 gates BLOCKED. Branch Draft isolada; sem deploy, merge, instalação, Worker ou gasto.

A próxima decisão, somente após este pacote: solicitar ao proprietário permissão específica **apenas para rever um inventário mínimo read-only do Windows**, com lista exata de comandos e limites — não uma autorização para instalar o AION.
