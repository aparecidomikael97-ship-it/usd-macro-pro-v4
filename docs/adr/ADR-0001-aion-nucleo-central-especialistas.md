# ADR-0001 — AION Núcleo central com especialistas por domínio

- Título: AION Núcleo central com especialistas por domínio
- Data: 2026-09-29
- Status: ACCEPTED

## Contexto

ARCHITECTURE.md descreve o AION como camada de inteligência do AtlasQuant. O checkpoint de 27/09 define quatro áreas administrativas: Trade, Investimentos, Negócios e AION Core. A reconciliação de 29/09 precisa impedir que essas portas sejam lidas como quatro IAs independentes.

## Problema

Quatro produtos administrativos podem ser implementados como sistemas separados, com memória, permissão e verdade próprias.

## Alternativas consideradas

Quatro assistentes autônomos foram rejeitados. Um núcleo único com especialistas de domínio preserva contexto, Guardian e Checkpoint Mestre.

## Decisão

O AION é um núcleo central único. As portas ADMIN são Trader, Negócios, Investimentos e AION/AI. Os especialistas correspondentes são AION Trader Expert, AION Business Expert, AION Investment Expert e o AION completo. Eles compartilham Core, contexto, memória, ferramentas e permissões separadas por domínio.

## Consequências

A nomeação dos experts e as quatro portas de produto ficam aprovadas e pendentes de implementação completa. Os especialistas já registrados no Core não recebem, por esta decisão, permissão nova.

## Componentes afetados

docs/aion/ARCHITECTURE.md; atlasquant_aion_specialists.py; Checkpoint Mestre.

## Segurança

Nenhuma porta amplia real_trade, gasto, publicação ou deploy. Isolamento de domínio não é autonomia.

## Compatibilidade

Os nomes AtlasQuant Trade, Investimentos, Negócios e AION Core de 27/09 continuam válidos como portas e são refinados, não apagados.

## Rollback/migração

Reverter a nomenclatura não apaga este ADR. Um ADR posterior deve marcá-lo SUPERSEDED e apontar o substituto.

## PR/commit relacionado

Nenhum PR deste registro é citado como prova de produção. Evidência por caminho de arquivo, sem SHA de deploy.

## Supersedes

Nenhum ADR anterior. Refina a leitura do checkpoint de 27/09.

## Superseded by

Nenhum.
