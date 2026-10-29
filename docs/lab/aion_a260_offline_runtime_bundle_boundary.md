# A260 — Fronteira verificável entre LAB e candidato offline do Outbox

**Status: LAB apenas · HARD NO-GO · 0/6 P0 homologadas · sem Worker, merge, deploy ou gasto novo.**

## Diagnóstico após A259

A259 removeu a injeção de `first_attempt_guard` do construtor comum `ExecutionOutbox`, movendo a simulação que admite `True` para `labs/a259_synthetic_outbox_fixture.py`. Entretanto, `render.yaml` atual instala dependências com `pip install -r requirements.txt` e inicia o Streamlit diretamente da árvore do repositório (`branch: main`, `autoDeployTrigger: off`). **Não existe uma etapa real de artefato operacional com exclusão comprovada de `labs/`**. Um checkout completo do repositório ainda pode conter o simulador inseguro.

## Escopo real da A260

**Não alteramos Render ou o runtime em operação.** Criamos um **exemplo mínimo de artefato offline de estudo**, exclusivamente para isolar o código A259 e testar a política de inclusão:

- `labs/a260_offline_runtime_bundle.py` cria um ZIP determinístico de **seis arquivos explicitamente permitidos**: `aion_chat/__init__.py`, `attachments.py`, `models.py`, `privacy.py`, `store.py` e `atlasquant_aion_execution_outbox.py`.
- Não usa `git archive`, cópia de diretório ou `include all Python`. A inclusão é baseada somente na tupla imutável `RUNTIME_FILES`. Qualquer outro arquivo — em especial `labs/`, testes, `__pycache__` e `*.pyc` — é recusado.
- Metadados ZIP canônicos, publicação create-only, esquema de manifesto com hash SHA-256 por arquivo, verificação de arquivos ausentes/duplicados/extras, entrada symlink, arquivo fonte symlink e tamanho máximo de arquivo/ZIP.
- Inspeção AST antes da criação e na verificação: nenhum `import labs`; `ExecutionOutbox.__init__` sem argumento de testemunha, `_reserved_first_attempt` contendo somente `return False`. Estas são verificações **locais**, sem autenticidade criptográfica independente.
- Metadados de qualquer artefato: `STUDY_ONLY_OFFLINE_NO_SEND`, `p0_homologated=0`, `authorizes_send=false`, `permits_worker=false`, `permits_deploy=false`.
- Sem chave, credencial de serviço, execução real, efeito externo, Worker ou provedor.

## Ensaios

Treze testes: criação/checagem do ZIP e lista exata; determinismo byte a byte; recusa de overwrite; injeção de fixture LAB; entrada duplicada/extra; mudança clandestina de `return False` para `True`; manifesto adulterado ou declarando autoridade; symlink ZIP; fontes ausentes; symlink em fonte; extração e importação do Outbox no **subprocesso isolado**, garantindo ausência de pacote `labs` e recusa do callback True; tentativa de importar LAB a partir de arquivo permitido.

**XFAIL aberta:** a configuração real do Render ainda não utiliza esse empacotador. Nenhuma build real fica protegida por esta prova de laboratório enquanto o pipeline não utilizar um artefato revisado e bloqueado por política de release independente.

## Limites honestos

- Este ZIP é um **candidato offline mínimo do Outbox/chat**, não o pacote completo do Trader, Investimentos ou Streamlit. Não é automaticamente uma build executável do aplicativo.
- A verificação dos hashes do manifesto detecta corrupção e adulteração sem atualizar o manifesto; **um invasor que controla o host pode reempacotar o ZIP e recalcular hashes**. Ela não prova procedência de source, assinatura externa ou antirollback.
- Um host com execução arbitrária pode importar `labs/` do checkout original ou monkeypatchar Python. O ZIP não representa sandbox, isolamento do sistema operacional ou autoridade independente.
- `Render autoDeployTrigger: off` é um controle configurado, não garantia de que futuras mudanças de serviço/deploy dependem do A260.
- Antes de qualquer operação real: pipeline aprovado que exija artefato allowlisted, isolamento efetivo dos pacotes dev, assinaturas/proveniência de build independentes, guardião de origem/evento/reserva externo, recibos de provedor e P0-5/P0-6 native FD/VFS COMMIT.

**HARD NO-GO operacional · 0/6 P0 homologadas · UNCERTAIN=ZERO_AUTO_RESEND.** Trader prioritário, Investimentos preparado e Negócios congelada; nenhum custo novo.
