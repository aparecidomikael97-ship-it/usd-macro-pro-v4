# AION BUSINESS Privacy, LGPD & Audit Governance V1

Schema: `ATLASQUANT_AION_BUSINESS_PRIVACY_AUDIT_GOVERNANCE_V1`

## Objetivo

Formalizar os controles de privacidade, LGPD e auditoria da aba Negócios antes
de qualquer tratamento de dados reais.

## Perfil de privacidade

Cada cliente deve ter:

- finalidades definidas;
- categorias de dados necessárias;
- base jurídica identificada para revisão;
- prazo de retenção;
- contato do responsável/controlador quando aplicável.

A versão demo não contém dados pessoais reais e não emite conclusão jurídica.

## Consentimento

Registros de consentimento precisam de:

- referência do titular;
- finalidade;
- granted/denied booleano exato;
- data/hora;
- fonte.

Registro incompleto não é tratado como consentimento válido.

## Acesso por perfil

A matriz usa:

**default deny + least privilege**

Perfis:

- CLIENT_ADMIN;
- CLIENT_OPERATOR;
- AION_SUPPORT;
- AION_ADMIN;
- AUDITOR.

Leitura e escrita são separadas. A demo não executa escrita externa.

## Retenção

O sistema calcula quando uma revisão de retenção é devida, mas não exclui dados
automaticamente.

## Solicitações do titular

Tipos previstos:

- EXPORT;
- DELETE;
- CORRECT;
- RESTRICT.

O estado inicial válido é `REVIEW_REQUIRED`.

Nenhuma solicitação executa exportação, exclusão, correção ou restrição na demo.

## Auditoria

Eventos registram:

- ator;
- ação;
- alvo;
- referência de aprovação;
- digest antes/depois;
- timestamp;
- digest do evento.

Um evento de auditoria não concede autoridade por si só.

## Versionamento e rollback

Configurações de automação recebem versão e digest.

Rollback pode ser preparado entre duas versões, mas:

- exige aprovação humana;
- não altera produção;
- não executa rollback automaticamente.

## Segurança

Nenhum dado pessoal real, exportação, exclusão, write externo ou rollback de
produção ocorre nesta versão.
