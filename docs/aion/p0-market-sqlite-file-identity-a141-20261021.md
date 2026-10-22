# AION P0 A141 — Identidade do arquivo SQLite e risco de troca de diretório (LAB)

21/10/2026. PR Draft empilhada sobre #1424. Não altera main, Worker, fornecedores, checkpoint nem credenciais. Todos os testes usam filesystem temporário local e credenciais GitHub Actions SOMENTE LEITURA.

## Motivação: cinco classes distintas de falha

1. **Troca do próprio arquivo** (`os.replace`): a instância A140 ainda podia abrir outra cópia válida do banco no mesmo caminho. A141 fixa, apenas durante aquela instância, `(st_dev,st_ino)` do banco SQLite e do diretório. Trocar o objeto bloqueia leitura, reserva e atualização local.
2. **Troca de diretório entre inicialização e uso**: A141 rejeita alteração da identidade do diretório e uso explícito de symlink/junction do Windows verificados no caminho. Hardlink do banco é recusado quando `st_nlink != 1`.
3. **Troca entre checagem e `sqlite3.connect`**: refaz a verificação de identidade imediatamente após a conexão ser criada, antes de `BEGIN IMMEDIATE` ou `INSERT`, e após as PRAGMAs de leitura.
4. **Restauração de conteúdo com mesmo inode**: guarda um mínimo de unidades já observado pela instância. Se a soma local cair abaixo desse valor enquanto ela está ativa, retorna DENY em vez de permitir nova reserva.
5. **Reinício/rollback de um banco formalmente válido**: a A141 NÃO resolve. Testes negativos preservados mostram que um novo objeto pode abrir snapshot antigo e readmitir a intenção. Uma testemunha externa durável e autenticada permanece obrigatória.

## Evidências RED-first e GREEN

- Testes 01-14 da A141 (Windows + Ubuntu) reproduziram inicialmente **10 FAIL / 1 ERROR** por sistema em 14 testes antes das verificações de identidade. Três casos já passavam; nenhum fornecedor/Worker foi chamado.
- Depois de fixar identidades, testes de restore com `os.replace`, junction simulado, hardlink e troca no momento do sqlite3.connect passaram nos dois sistemas.
- Testes 15-17 abordam regressão com MESMO inode. Antes de marcar o mínimo de unidades por instância, os testes 15 e 16 demonstraram que a soma poderia retroceder sem sinalização; o teste 17 mantém propositalmente a prova de que o novo processo NÃO possui referência independente.
- Bateria regressiva preserva 45 A140, 30 A139, 25 A138 e 14 workflow por sistema.

## Limites CRÍTICOS, não confundíveis com prova de segurança

- **Esta checagem NÃO é uma abertura atomicamente vinculada ao file descriptor**. Existe janela TOCTOU, especialmente swap ABA: o atacante pode fazer a checagem observar o caminho original enquanto a conexão SQLite possui handle de outro banco. Junctions/links em volumes de rede também dependem do sistema operacional.
- `st_dev` e `st_ino` da própria máquina não são um selo de confiança, não autenticam histórico entre boots e podem ser manipulados por quem controla o disco. Guardar high-water em RAM apenas protege a instância viva, não é um monotonic log independente.
- Após a segunda revisão Codex, o código preserva (somente por instância) os IDs, unidades, estados e digests de reservas já observadas; impede desaparecimento/substituição de registro de soma igual e regressão de `LOCAL_OUTPUT_OBSERVED` para `RESERVED_UNCERTAIN`. Essa memória não autentica registros anteriores à abertura nem sobrevive à criação de outra instância/reinício; ainda não há C/R por emissor independente.
- A evidência A134 de recovery e A135 de writer continuam HARD NO-GO até credenciais e chaves matriculadas fora de GitHub/host, leitura autenticada de HEAD externo monotônico, readback fresco, revogação, e prova causal do fornecedor com separação HUMAN_OWNER.
- O SQLite é um contrato LOCAL para simulações, sem dados atuais de mercado, sem integração externa e sem orçamento real. Nenhum dos seis P0 é homologado por A141.

## Próximo bloqueio técnico

Investigar abertura de arquivos/diretórios pela identidade real do handle em APIs específicas para Windows/Linux (ou isolamento por ACL de diretório controlado), sem representar Python `Path.is_symlink`/`Path.is_junction` como proteção atômica. Em paralelo, desenhar proveniência externa durável/fresca e política de enrollment/custódia separada; não provisionar serviço pago sem aprovação.

**HARD NO-GO · 0/6 P0 homologados · Worker OFF · ZERO_AUTO_RESEND · SEM MERGE OU DEPLOY.**
## Segunda revisão independente Codex — diferenças entre objeto e processo

Codex local inspecionou SOMENTE arquivos copiados de A141 no TEMP Windows em modo read-only; sem executar scripts, modificar arquivos, rede ou chaves. Indicou quatro riscos locais: inicialização de objeto sobre histórico existente não fixava high-water, leitura de outra instância não atualizava a marca, soma de unidades não protegia IDs/estados individuais e os testes rotulados 'novo processo' construíam apenas outro OBJETO. Foi corrigida a nomenclatura dos testes, sem apresentar objeto novo como crash process.

Testes novos 18–22 primeiro demonstraram o problema: instância reaberta sobre DB com consumo prévio aceitava rewind in-place; outra instância observada por `reservation_state` deixava de ser exigida; regressão de `LOCAL_OUTPUT_OBSERVED` para `RESERVED_UNCERTAIN` com a MESMA soma autorizava segunda gravação local; troca de run_id preservando unidades também passava. Hardlink introduzido após iniciar é bloqueado.

Correção LAB: `_verify_policy` revalida todas as linhas da tabela `reservations` em cada operação, conserva high-water local e mapa por run_id já visto, nega diminuição, mudança de unidades, desaparecimento e retrocesso de estado/digest; permite somente avanço local reservado→saída observada. `__init__` observa e fixa o histórico atual da instância após a inicialização, mas essa observação é da mesma base local (não é custódia externa).

**RED-first nova suite** antes dessa correção: https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39696858484. **GREEN direcionado** após fix: https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39696959611 = **22 A141 +45 A140 +30 A139 +25 A138 +14 contrato =136 PASS Windows /136 PASS Ubuntu, 272 PASS**, sem waiver.

**Reiterar LIMITAÇÃO:** testes 12/17 continuam deliberadamente provando que uma NOVA instância criada sobre cópia válida antiga pode aceitar histórico retrocedido; sem testemunha externa, isso não pode ser negado confiavelmente. Não há abertura atômica vinculada ao handle do diretório SQLite; há janela ABA e possível conteúdo anterior ao check. Este LAB NÃO remove o HARD NO-GO.
