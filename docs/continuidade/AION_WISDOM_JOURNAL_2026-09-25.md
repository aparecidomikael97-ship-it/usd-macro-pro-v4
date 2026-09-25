# AION — Diário de Sabedoria

Data de consolidação: 2026-09-25

## Objetivo

Separar **experiência registrada** de **conhecimento organizado**.

O Aprendizado Controlado continua responsável por registrar previsões, resultados,
erros, calibração, evidências e experimentos. O Diário de Sabedoria fica acima
dessa camada e guarda somente lições revisáveis e auditáveis.

Cada registro responde:

- o que foi aprendido;
- de onde veio;
- qual o estado de verdade;
- qual a confiança no conhecimento;
- onde a lição se aplica;
- quando foi validada;
- quando precisa ser revisada;
- quais episódios de aprendizado deram origem ao registro.

## Estados de verdade

- CONFIRMED
- INFERENCE
- HYPOTHESIS
- UNKNOWN

Um registro CONFIRMED exige referência de evidência. Se um registro antigo vier
marcado como CONFIRMED sem evidência, a normalização rebaixa para UNKNOWN.

## Aprendizado → Sabedoria

Um episódio SETTLED pode gerar **candidato** para o Diário de Sabedoria.

Esse candidato:

- nunca vira regra automaticamente;
- nunca muda peso/modelo;
- nunca promove Challenger;
- nunca habilita trading real;
- exige revisão humana.

Acerto observado com evidência pode virar INFERENCE. Sem evidência suficiente,
permanece HYPOTHESIS. Erro sem causa confirmada registra explicitamente que a
causa continua desconhecida.

## Revisão

Cada lição pode ter `review_due_at`.

Estados de revisão:

- CURRENT
- DUE
- UNKNOWN

A ausência de prazo de revisão não é tratada como prova de que a lição continua
atual; fica UNKNOWN.

## Checkpoint Mestre

O Checkpoint Mestre passa a ter uma seção `wisdom` com:

- `entries`
- `digest`

O digest protege integridade lógica e facilita auditoria/continuidade.

## Restrições permanentes

O Diário de Sabedoria não:

- altera pesos;
- altera estratégia;
- faz deploy;
- ativa feature flag;
- publica conteúdo;
- executa compra/venda;
- transforma histórico em probabilidade de lucro futuro.

Ele organiza conhecimento. Mudança operacional continua exigindo evidência,
Sandbox/Shadow quando aplicável, Guardian e revisão humana.
