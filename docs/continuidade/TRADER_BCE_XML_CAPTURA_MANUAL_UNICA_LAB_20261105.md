# AtlasQuant Trader — captura manual única do XML BCE (LAB, 05/11/2026)

## Objetivo e limite

O ambiente atual não consegue resolver `www.ecb.europa.eu`, e o computador AM12 permanece offline. Por isso **nenhum XML original foi coletado nesta revisão**. O módulo `atlasquant_trader_ecb_xml_manual_capture_lab.py` é uma ferramenta opcional, de execução **manual e única**, preparada para ser usada futuramente em ambiente com rede autorizada. Não é scheduler, feed, robô, prévia de deploy nem fonte de sinais.

URL fixa: `https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml`. O arquivo **hist-90d** representa uma janela móvel de cerca de 90 dias, portanto sua disponibilidade para datas antigas não é garantida para sempre.

## Como usar somente quando houver autorização manual

Em computador autorizado, com Python instalado, pasta existente e acesso à internet, o operador poderá executar **uma vez**:

```bash
python atlasquant_trader_ecb_xml_manual_capture_lab.py --output-dir "./evidencias_bce" --manual-one-shot
```

Sem `--manual-one-shot`, não realiza requisição HTTP nem grava arquivo. A pasta deve existir; não aceita destino simbólico. O código usa HTTPS com verificação padrão de certificados, não permite redirecionamentos, solicita compressão identity, exige resposta 200, URL final exata, Content-Type XML e corpo limitado a 400 KB. Verifica apenas a estrutura superficial do envelope, remetente e série XML para não salvar HTML/erro como cotação. Não tenta baixar todos os 28 pares separadamente: o BCE publica referências por EUR.

Cada execução bem-sucedida cria **dois arquivos exclusivos, sem sobrescrever registros existentes**: os bytes do XML recebido e um recibo JSON contendo SHA-256 calculado, tamanho, URL, status HTTP, Content-Type, horários locais de início e conclusão da consulta e nome dos arquivos. Falhas não devem resultar em um arquivo incompleto apresentado como prova. Não armazena credenciais e não habilita atualizações automáticas.

## Segurança epistemológica

- Um hash local demonstra apenas integridade dos bytes capturados, **não** prova independente de origem ou do horário real de disponibilização pública. HTTPS com certificados do sistema não é uma testemunha histórica externa; certificados, proxies, relógio local e provedores precisam de auditoria separada.
- A data da referência é **diferente** da data/hora da coleta. O XML obtido posteriormente pode conter correções ou revisões que não estavam disponíveis na data do movimento. O próprio XML não é preço bid/ask ou candle M15 de execução.
- Os testes de rede usam respostas falsas em memória e um diretório temporário. Não realizam download real, não comprovam taxa de acerto ou qualidade de viés.
- Ao receber o arquivo real, o laboratório deverá conferir sua hash com o recibo, passar pelo leitor `atlasquant_trader_ecb_g8_xml_reference_history_lab.py`, comparar valores com `atlasquant_trader_ecb_g8_xml_transcript_reconciliation_lab.py` e depois obter preços M15 de fonte independente e licenciada. Diferenças ou dados ausentes significam **AGUARDAR**, sem reparo silencioso.

**HARD NO-GO:** não há merge, publicação, operação, Worker, Scheduler, compras, acessos ao AM12 offline ou alteração da interface PR #1816.
