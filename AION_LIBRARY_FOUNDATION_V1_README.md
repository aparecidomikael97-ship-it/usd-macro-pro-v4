# AION Biblioteca Foundation V1 — Handoff consolidado

## Escopo e origem
Entrega isolada para a issue #474, derivada do ZIP WIP enviado pelo Drael. O ZIP recebido possui SHA-256 `64aeea47b9da00609dfc206799954b877cbf6587b1f0bdf0f5702f1297797131`; integridade original verificada (manifesto 3/3 e testzip limpo). Referência GitHub: commit `91732c3fd62d50a518296e4c10c159b095cd8c6b` da branch `integration/aion-core-nightshift-v1-20261001`.

## Arquivos desta entrega
- `aion_core/library_foundation.py`: catálogo offline V1, máquina de estados editorial, isolamento por tenant/domínio, dedup indexada por digest, controle de versões, metadados de origem/licença, trilha de auditoria imutável e snapshots; **não** indexa documentos e **não** realiza I/O.
- `test_aion_core_library_foundation.py`: 32 testes de unidade e regressão, incluindo 5 testes adicionais de dedup, transição/auditoria adversarial, metadados e digest.
- `pre_task_hashes.json`: snapshot do Drael com 1.284 hashes SHA-256 de arquivos existentes antes da tarefa; esta entrega preserva os bytes do snapshot original. O snapshot completo não pode ser comprovado contra o repositório remoto sem verificar cada arquivo individualmente; 12 arquivos AION Core+testes recuperados foram comparados com ele, e 6 blobs de módulo foram conferidos exatamente no commit de referência.
- `AION_LIBRARY_FOUNDATION_V1_CHECKPOINT.json`: proveniência da correção, provas e limitações.
- `MANIFEST_SHA256.json`: hashes e tamanhos exatos dos cinco arquivos da entrega (exclui a si próprio).

## Correções realizadas no WIP
1. Corrigida definição sintática de `_SECRET_RE` que impedia importação do módulo.
2. Corrigida a direção da verificação de encadeamento do log de auditoria.
3. Dedup determinística preserva o primeiro registro de um digest em cada tenant+domínio; removido ramo morto do código.
4. `extra_fields` fora da API tipada agora falha fechado (até nomes supostamente permitidos não são silenciosamente ignorados).
5. Aprovação exige tipo de fonte além da referência, licença informada e identificador de aprovação humana registrado.
6. Snapshot inclui o conteúdo editorial/auditoria em seu digest; adulterações com salto de estado são rejeitadas pelo verificador de invariantes.

## Provas locais
- `python -m unittest -q test_aion_core_domain_registry test_aion_core_evidence_pack test_aion_core_memory_architecture test_aion_core_provenance test_aion_core_security_audit test_aion_core_trust_engine test_aion_core_library_foundation`: **124 testes aprovados**, sendo 92 originais + 32 novos.
- `python -m compileall -q aion_core test_aion_core_*.py`: aprovado.
- Os seis módulos originais extraídos do ZIP Nightshift tiveram seus Git blob SHA-1 comparados com o commit remoto `91732c3f`: 6/6 iguais.
- Arquivos originais recuperados comparados com `pre_task_hashes.json`: 12/12 iguais. Isto **não** comprova paridade de todos os 1.284 arquivos de um checkout completo.
- Arquivo ZIP final: testzip() e hashes do manifesto devem passar na verificação da entrega.

## Limites de confiança e próximos passos
- A credencial/identidade dos aprovadores **NÃO é autenticada** por esta biblioteca; `human_approved_by` é um registro declaratório. Antes de liberar ingestão ou indexação em produção, conectar ao RBAC/approval assinado e à política de proveniência/licenciamento verificável.
- `sha256` de conteúdo e dados de metadados são recebidos como afirmações do chamador; antes de ingestão real, recalcular SHA-256 dos bytes e verificar licenças e autorização.
- A trilha é imutável dentro dos objetos de dados desta biblioteca em memória, **não** tem assinatura criptográfica nem persistência de auditoria.
- Metadados são dados não confiáveis. Não interpretar instruções contidas em títulos ou fontes. Sem OCR, sem LLM, sem RAG ou ingestão nesta fase.
- Antes de eventual merge: CI do repositório, revisão de arquitetura, testes de segurança adicionais, verificação de acessos por tenant nos adaptadores, e aprovação administrativa explícita.
- Sem merge, deploy, alteração de PRs protegidas (#472/#473) ou produção nesta entrega.
