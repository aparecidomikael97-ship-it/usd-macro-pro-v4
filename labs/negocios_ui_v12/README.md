# AtlasQuant Negócios — CRM UI V1.2 (laboratório RED → GREEN)

**Somente protótipo local HTML/JS responsivo, fictício e OFFLINE. HARD NO-GO.**

Continuidade do V1.1, com correções específicas de segurança semântica e acessibilidade. Não é o CRM real; não possui backend, isolamento autenticado por tenant, autorização financeira, mensageria, provedor de estoque, conexão bancária, persistência, processamento de dados pessoais ou autorização de operação.

## Defeitos demonstrados antes do patch

Em V1.1 intacto, os oito primeiros casos de `test_adversarial.py` foram executados como teste RED. Resultado: **8 FAIL**:

1. `OPORTUNIDADE (SIMULADA)` persistia após desmarcar critério obrigatório.
2. Indicador fictício de leads qualificados não acompanhava avanço/revogação.
3. Fração de centavo (`0.005`) era arredondada silenciosamente.
4. `1e2` era aceito como R$ 100,00.
5. `1e1` era aceito como 10 unidades de estoque.
6. A frase `Lucro garantido` escapava ao filtro didático.
7. `Aumentaremos suas vendas em 50%` escapava ao filtro didático.
8. Navegação inferior mobile não indicava `aria-current=page`.

**Corrigidos:** revogar automaticamente a promoção visual após retirada de requisito; métrica de referência sincronizada no exemplo; aceitar apenas inteiros decimais simples em quantidades e até duas casas exatas para reais (cálculo centesimal, sem arredondamento); estender exemplos do filtro de linguagem, mantendo aviso de cobertura limitada; fornecer `aria-current` também na navegação móvel.

## Execução local

Requer Python 3 + Playwright com Chromium acessível no caminho `/usr/bin/chromium` (ajustar script em outro sistema). Todas as execuções com `offline=True`:

```sh
python test_adversarial.py
python test_responsive.py
python test_ui_v11.py
```

**Resultados deste ciclo em Linux/Chromium:**
- RED em V1.1: 8/8 testes adversariais iniciais falharam. Evidência: `RED.log`.
- GREEN em V1.2: 12/12 testes adversariais PASS (8 regressões corrigidas + 4 controles adicionais).
- Smoke V1.1 reproduzido no V1.2: 19 grupos desktop + 15 grupos mobile PASS. **Grupos de verificações**, não 34 testes unitários independentes.
- Responsividade: 35 combinações de aba/largura (7 larguras × 5 telas), sem rolagem horizontal/erros de execução.

## Limites que não foram resolvidos por testes locais

- O filtro de texto é uma orientação educativa: semântica humana, contexto e outras promessas ainda podem escapar; não é aprovação jurídica/comercial.
- Qualquer input e estado podem ser manipulado no navegador; não constitui controle de autenticação, integridade, estoque ou financeiro.
- A avaliação de estoque/pagamento é somente matemática de demonstração, **NÃO** confirmação externa.
- Marcar itens LGPD não comprova conformidade.
- Sem CI hospedada, teste físico Android/iOS ou prova de conexão com produtos existentes.
- As 84 falhas/erros históricas do Núcleo e os requisitos H0/F1/T1/F2 continuam pendentes. Worker OFF; ZERO_AUTO_RESEND; nenhuma alteração da `main` nem deploy/merge/gastos.

Versão anterior V1.1 preservada na branch separada. `index.html` V1.2 é autocontido e pode ser aberto localmente; não precisa de conexão. As imagens geradas demonstram layout, não provas de implantação.
