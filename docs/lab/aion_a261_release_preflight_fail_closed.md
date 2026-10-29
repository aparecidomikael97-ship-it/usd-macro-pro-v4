# A261 — Pré-verificação offline de publicação, sempre HARD NO-GO

**Status: estudo LAB; não autoriza merge, Render, Worker, serviços, custos nem efeitos externos. P0 0/6.**

## Situação confirmada

A260 verificou um ZIP mínimo do chat/Outbox que não contém `labs/` e cujo `ExecutionOutbox` não pode receber o callback sintético. Entretanto, **`render.yaml` usa a árvore fonte do repositório, instala `requirements.txt` e inicia `usd_macro_pro_v4_cloud.py` pelo Streamlit**. A configuração atual tem `autoDeployTrigger: off`, mas esse atributo não prova um build allowlisted nem impede alguém com acesso de fazer um deploy por outra via.

**A261 não toca no Render.** Em `labs/a261_offline_release_preflight.py`, avaliamos o candidato A260 com o verificador anterior e analisamos o arquivo `render.yaml` em parser YAML de carga segura com proibição explícita de chaves duplicadas. O diagnóstico gera motivos separados para candidato inválido, configuração desconhecida, auto-deploy ativado, checkout fonte sem vínculo com o ZIP e Streamlit ausente do candidato A260.

Mesmo com ZIP estruturalmente válido, o resultado é **sempre `HARD_NO_GO_NOT_A_DEPLOY_AUTHORIZATION`**, `p0_homologated=0`, `authorizes_send=False`, `permits_worker=False`, `permits_deploy=False`, `permits_merge=False`, `release_approved=False` e `independent_provenance_verified=False`. A checagem de estrutura pode ser `True` e isso não libera publicação.

## Interface de auditoria

O comando é somente leitura e intencionalmente **retorna código de saída 2** mesmo em caso de pacote válido. Isso evita interpretar a execução da pré-verificação como um `exit 0` de liberação.

```bash
python -B -m labs.a261_offline_release_preflight --candidate /tmp/estudo-a260.zip --render-config render.yaml
```

O comando NÃO é integrado ao Render, não roda o aplicativo, não constrói um pacote Streamlit, não cria credenciais e não assina qualquer raiz. Uma futura integração de publicação demandaria projeto separado com artefato completo, revisão independente, custódia externa e autorização específica antes de modificar serviços.

## Testes

14 cenários em Ubuntu e Windows:
- ZIP A260 válido + Render atual continuam NO-GO;
- CLI real devolve `2` e JSON negado;
- flags `verified`, `root_independent`, `p0_homologated=6` adicionadas ao YAML são recusadas;
- chaves duplicadas de YAML, inclusive `autoDeployTrigger`, são recusadas;
- auto-deploy `on` aciona motivo explícito;
- comando falso afirmando rodar `preflight` ainda não comprova artefato vinculado;
- arquivo ausente, ZIP inválido, falso header ZIP, configuração malformada e tags YAML não seguras negados;
- nenhum segundo serviço desprotegido é ignorado;
- 60 classificações concorrentes sempre recusadas;
- caminho CLI sem ZIP continua retornando código de falha;
- **XFAIL #14:** o Render atual não chama a A261; portanto esta é uma pré-verificação exercitada em CI e não enforcement efetivo no ambiente de produção.

## Fronteiras de confiança

O parser YAML é de laboratório e analisa os campos usados na configuração atualmente conhecida. Não prova a identidade ou a intenção de quem alterou o YAML e não garante que o provedor Render tenha carregado aquele arquivo. Hashes A260 são locais; host adversário pode trocar chaves, código, relógio, arquivos, deploy ou middleware. **CI verde é ensaio de recusa, não homologação operacional.**

**HARD NO-GO · 0/6 P0 · UNCERTAIN=ZERO_AUTO_RESEND.** AION completo, Trader prioritário, Investimentos preparado e Negócios congelada, sem novos custos.
