# AION — proposta de inventário mínimo Windows (P0/P1)

**Data:** 11/10/2026
**Base:** Draft #1222 / HEAD `8d12c14b542fd517ef2ae270a16d8ab42f277f84`
**Status:** PREPARAÇÃO OFFLINE; `FIRST INSTALL = HARD NO-GO`

## Limites e autorização

Esta Draft propõe apenas um **inventário de versão e arquitetura do Windows**. NÃO significa que o usuário autorizou sua execução. Uma mensagem genérica como "vamos lá" NÃO atende à autorização específica exigida para leitura do host. O proprietário precisa aprovar explicitamente o computador, o operador, a janela, o script e os campos coletados antes de qualquer execução no seu computador.

**Nenhuma leitura do Windows do proprietário foi realizada nesta PR.** O GitHub Actions pode executar a saída padrão inerte em runners descartáveis para comprovar que a opção sem flag não consulta o host.

## Script proposto

`tools/aion_windows_basic_inventory_readonly_v1.ps1`.

Comportamento padrão, sem autorização: imprime três linhas explicativas (`PLAN_ONLY_NO_WINDOWS_READ`, escopo, `FIRST_INSTALL_HARD_NO_GO`) e termina **antes de consultar o registro do Windows ou qualquer propriedade do dispositivo**.

**Comando futuro de inventário, EXCLUSIVAMENTE após autorização separada:**

```powershell
pwsh -NoProfile -NonInteractive -File .\tools\aion_windows_basic_inventory_readonly_v1.ps1 -AuthorizeReadOnlyInventory
```

É proibido usar esse comando antecipadamente. O switch `-AuthorizeReadOnlyInventory` é uma barreira adicional no script; sua presença NÃO substitui a autorização expressa e contextual do proprietário.

**Leituras propostas:** somente a chave pública de metadados do SO `HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion`, e exclusivamente as propriedades `ProductName`, `EditionID`, `DisplayVersion`, `CurrentBuildNumber`, `UBR`. Complementar com `RuntimeInformation.OSArchitecture` e `ProcessArchitecture`.

**Saída:** JSON exclusivamente em stdout (sem salvar arquivo): schema, HARD_NO_GO, nome/edição/versão/build/arquitetura do SO e marcações explícitas `NOT_INSPECTED` para TPM, FIDO2, Hello, BitLocker e capacidades de segurança.

**NÃO coletar:** nome de usuário, hostname, número de série, identificador de máquina, chave de produto, registro fora da chave autorizada, biometria, PIN, credenciais, tokens, certificados, chaves de criptografia, diretórios privados, conteúdo de aplicações, emails ou dados de clientes.

**NÃO realizar:** consulta à rede, instalação, download, worker, deploy, merge, API paga, elevação de privilégio, alteração de registro, mudança de segurança, exportação de arquivo, experimentos de isolamento, matrícula de raiz ou emissão de credenciais.

## Premissas e situações não comprovadas

- O inventário não mede estado real de BitLocker, TPM, FIDO2/Windows Hello, AppContainer, firewall nem políticas de contas.
- Valores de versão podem falhar se algum campo de registro não estiver disponível; nesse caso, interromper a execução, sem fallback para uma coleta mais ampla.
- Os comandos não auditam o armazenamento privado do AION, não avaliam assinatura de instalador e não demonstram vínculo físico do HUMAN_OWNER.
- A integridade do próprio script antes de rodar exige conferir o commit/sha e o diff em ambiente autorizado.
- A apresentação de um relatório assinado por processo local ou CI não transforma a observação em prova independente.
- Um teste estático não equivale a ensaio físico. Não assumir que a presença de uma flag no código basta para impor consentimento social.

## Validação nesta PR

1. Testes offline em Windows e Linux do texto do script, cobrindo ausência de chamadas à rede, escrita, coleta pessoal ou promoção a GO.
2. Parse do PowerShell no runner Windows, sem leitura do host.
3. No runner descartável Windows, execução **apenas sem switch**, comprovando a saída PLAN_ONLY.
4. Regressões V6 de consolidação e dos 20 requisitos bloqueados.
5. Quality global original no Linux e `git diff --check`.

Mesmo se todos os testes forem verdes, **não avançar para nenhuma atividade física sem aprovação explícita separada**. O manifesto original deve permanecer 20/20 BLOCKED.

## Pedido de autorização futura para o proprietário

> Autorizo especificamente **apenas o inventário básico read-only de versão e arquitetura**, conforme o script `aion_windows_basic_inventory_readonly_v1.ps1` da Draft preparada, no meu PC Windows conectado e dentro desta sessão. Autorizo somente a consulta dos cinco campos de SO e das duas arquiteturas descritas; não autorizo leitura de identificadores pessoais, chaves, TPM, FIDO2, biometria, arquivos privados, rede, alterações, instalação, Worker, merge, deploy ou gastos. Confirmarei o escopo antes da execução.

O texto acima é um **modelo de autorização, não autorização já concedida**.
