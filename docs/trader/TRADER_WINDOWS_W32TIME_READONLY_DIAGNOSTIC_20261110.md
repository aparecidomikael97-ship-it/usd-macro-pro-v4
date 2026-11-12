# AtlasQuant Trader — diagnóstico read-only da sincronização do Windows

**Checkpoint: 10/11/2026. Preparado; não executado no Windows do usuário.**

## Bloqueio de origem

Nas imagens de 09/11/2026, `w32tm /resync` falhou mesmo após reiniciar o
serviço: o Windows relatou que não havia dados de tempo disponíveis. Esse
resultado impede atestar o horário de coleta de velas e releases econômicos.
**Não sabemos ainda a causa**; não assumir que a Internet/UDP 123 está
bloqueada, nem que o relógio está efetivamente correto apenas por estar
marcado como automático na interface.

Documentação oficial Microsoft:

- `Windows Time Service Tools and Settings`: parâmetros read-only
  `w32tm /query /source`, `/status /verbose`, `/peers` e `/configuration`.
- `w32tm /resync fails with no time data available`: cenários possíveis
  incluem DNS/nome do servidor NTP, tráfego UDP 123 bloqueado ou servidor
  remoto que não fornece horário adequado. A causa precisa ser observada.

## Programa preparado

`atlasquant_windows_time_diagnostic_lab.py` roda cinco consultas locais,
sem modificar configurações:

1. `sc.exe query w32time`: serviço ativo, parado ou status desconhecido.
2. `w32tm /query /status /verbose`: evidências locais de sincronização.
3. `w32tm /query /source`: fonte atual (não inclui nome no relatório).
4. `w32tm /query /peers`: quantidade de pares relatada.
5. `w32tm /query /configuration`: presença de NtpServer configurado.

O relatório contém hipóteses separadas para serviço parado, ausência de
servidor NTP configurado, relógio preso em fonte local e sincronização
falhando apesar de pares existentes. Não possui comandos `/resync`,
`/config`, alterações de registro, abertura de firewall ou testes de rede
externos; se uma consulta não funcionar, registra inconclusivo.

### Execução manual futura

Em um prompt Windows que tenha o Python instalado e os arquivos do projeto:

```powershell
py -3.11 atlasquant_windows_time_diagnostic_lab.py
```

**Não requer MetaTrader 5 aberto**, dados de conta nem módulo `MetaTrader5`.
Não é necessário executar como administrador para o código tentar ler o
status, embora políticas do Windows possam limitar algumas consultas.

O JSON é um resumo sem nome do servidor de horário, sem credenciais e sem
acesso à conta. O usuário poderá enviar apenas o resultado resumido para
orientarmos a correção posteriormente, com consentimento para qualquer
mudança no computador.

## Testes

- `test_atlasquant_windows_time_diagnostic_lab.py`: **15/15** cenários
  locais com respostas simuladas de `sc.exe` e `w32tm` (inglês/PT-BR,
  serviço parado, local CMOS, sem peers, peers presentes, consulta com
  erro e ausência de alegação indevida de UDP bloqueado).
- `python -m unittest discover -q -p 'test_atlasquant*.py'`:
  **414/414 aprovações locais**.
- CLI executado no Linux: bloqueado como `WINDOWS_ONLY`, exit code 2.

## Regras de segurança

`independent_utc_attestation=false`, `mt5_or_broker_accessed=false`,
`settings_changed=false`, `firewall_changed=false`,
`ntp_udp123_or_dns_failure_proven=false`, `trade_authorized=false`,
`operational_bias=AGUARDAR`.

**Dependência para avanço real:** executar essas consultas no PC autorizado,
analisar a saída, decidir com o usuário eventuais correções do Windows,
confirmar sincronização estável e só então tentar o coletor de ouro.
Sem merge, deploy, Worker, novos custos ou operações financeiras.
