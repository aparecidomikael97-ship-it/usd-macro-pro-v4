# A322 — Primeira referência de confiança fora do AION: opções práticas e teste de transferência (LAB)

**HARD NO-GO · ZERO_AUTO_RESEND · 0/6 P0 homologadas · sem merge/Worker/deploy/provider/ordens/novos gastos.**

## Por que existe

A321 (#1773) validou a detecção matemática de divergências entre cabeças de histórico assinadas, no Ubuntu e no Windows. Porém as duas testemunhas, as chaves, a cabeça inicial e os desafios ainda eram declarados pelo próprio ambiente de teste. É possível reconstruir toda a história dentro de um computador e produzir matemática coerente. A322 prepara o **primeiro repasse controlado da referência pública** e compara modelos de custos e governança, sem fingir ter criado custódia externa.

## Contrato implementado

Arquivo: labs/a322_genesis_out_of_band_handoff_lab.py.

A função **generate_genesis_card(public_manifest, ceremony_id)** gera somente dados públicos e determinísticos a partir de um manifesto canônico A319:

- SHA-256 completo dos bytes canônicos do manifesto.
- Geração, época de incidente, sequência e hash do high-water inicial.
- Digest das **chaves públicas** da raiz e identificador da cerimônia.
- Impressão abreviada para conferência manual **de 128 bits** (8 grupos de 4 caracteres hexadecimais); **a validação programática usa sempre o SHA-256 de 256 bits completo**.
- Decisão HOLD_ONLY.

Não gera chaves privadas, credenciais nem conta externa, não grava banco real, não cria autoridade de confiança nem fornece um pin seguro por conta própria.

A função **verify_declared_genesis_handoff** compara o manifesto com o cartão e **duas cópias declaradas**. Verifica SHA-256 de cada cópia e recusa cópias repetidas, identidade de custodiante igual, mesmo domínio administrativo, mesmo login, mesmo dispositivo, mesmo domínio de recuperação da conta, mesmo canal de entrega, campos desconhecidos e instruções de GO.

**Resultado positivo significa apenas LAB_HANDOFF_COPIES_MATCH_UNATTESTED:** os dados enviados pelo chamador são coerentes. Não confirma que as cópias chegaram a pessoas/serviços diferentes, que sobreviverão ao ataque, nem que cada titular realmente controla a chave. Toda saída é HOLD, inclusive quando duas cópias coincidem.

A contraprova A322 substitui **o manifesto, as raízes públicas, a sequência, o cartão e ambos os recibos locais**. A verificação matemática passa, mas bootstrap_independently_authenticated permanece False — logo não existe raiz fora do controle do host.

## Comparativo de opções para nosso momento

| Opção | Mensalidade do serviço exigida pelo desenho | Valor nesta etapa | Problema não resolvido |
|---|---|---|---|
| **Duas pessoas realmente independentes guardando impressão digital em meios offline separados** | **Não é exigida** (custos físicos/logísticos ainda podem existir) | Piloto manual de primeiro pin e exercício de conferência; **opção para estudar agora**, sem instalação | Não entrega high-water confiável e resposta automática antes de cada efeito |
| **Duas testemunhas externas com administradores separados e log append-only resistente a rollback** | **A avaliar** (não supor serviço gratuito) | Modelo candidato a operação automatizada futura após auditoria, custeio e autorização | Implantação, autenticidade da raiz, resistência à supressão, IAM, revogação, ACK externo, SLA e preço não verificados |
| **Duas pastas no notebook ou espelho em nuvem/Git controlado pela mesma conta e recuperação** | O custo não resolve o risco | **Não usar como fonte independente** | Mesmo administrador pode substituir as duas referências; falso sentimento de segurança |

Não há preço cotado nesta fase, nem contratação, ativação ou serviço externo validado. Um repositório privado GitHub ou armazenamento supostamente imutável sob a mesma conta não garante separação de autoridade.

## Exemplo de cerimônia futura — NÃO executada

1. Uma vez definidos os responsáveis, **duas pessoas ou entidades efetivamente independentes** verificariam por meios já autenticados os dados públicos da raiz e receberiam cópias por canais fora do controle do AION.
2. Cada responsável conservaria um registro com digest completo, geração, cabeça/seq e data verificável, em custódia sem permissão de substituição pelo AION. A prova do canal e da identidade precisa vir **de fora** dos campos declarados.
3. Antes de qualquer recuperação, compararíamos o estado do AION com **ambas** as referências obtidas diretamente dos custodiantes. Divergência, ausência de testemunha ou retrocesso exige **HOLD e investigação**, nunca auto-reenvio.
4. Para um efeito real automático ainda seria necessário testemunho independente consultável na operação, ACK de resultado do provedor e resolução de COMMIT incerto. Não disponibilizado pelo piloto offline.

**Não entregar chaves privadas, senhas, frases de recuperação ou dados de cliente a nenhum custodiante.** Este contrato manuseia apenas digests e chaves públicas sintéticas.

## Testes

Comando: python -m unittest -v labs.test_a322_genesis_out_of_band_handoff_lab

São 32 testes novos com fraude documental, substituição total da origem, reutilização de contas/dispositivos, perfis de custos e decisões inseguras. CI GitHub Actions: Ubuntu/Windows com as regressões A321–A299. A biblioteca criptográfica é instalada apenas no runner.

## Decisão que falta para a P0-3/P0-4

**A322 permite escolher um piloto manual sem mensalidade obrigatória, não homologar o sistema.** Para raiz verdadeiramente independente, ainda precisamos nomear custodiantes, autenticar cada identidade e chave pública sem confiança inicial estabelecida no próprio host, comprovar retenção antirollback e acesso independente, além da fronteira de efeitos, ACK, idempotência e incidentes. Nenhuma autoridade foi estabelecida nesta PR.

**0/6 P0 homologadas, HARD NO-GO, ZERO_AUTO_RESEND.**
