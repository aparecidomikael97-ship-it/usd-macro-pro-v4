"""AtlasQuant Academy — detailed educational video blueprints.

Storyboards only. No rendering, upload, TTS provider call or trading side effect.
Every blueprint is capped at 20 minutes and designed for animated chart teaching.
"""
from __future__ import annotations

from typing import Any, Mapping

from atlasquant_academy import academy_topic

SCHEMA="ATLASQUANT_ACADEMY_VIDEO_BLUEPRINTS_V1"
MAX_VIDEO_SECONDS=20*60


def _scene(order:int,title:str,seconds:int,visual:str,teaching:str)->dict[str,Any]:
    return {
        "order":int(order),
        "title":str(title),
        "seconds":int(seconds),
        "visual":str(visual),
        "teaching":str(teaching),
    }


BLUEPRINTS:dict[str,dict[str,Any]]={
    "technical-to-liquidity":{
        "target_seconds":420,
        "hook":"A resistência que você marcava pode também ser o lugar onde vários stops ficam visíveis.",
        "scenes":[
            _scene(1,"O que você já conhece",45,"Gráfico limpo com suporte, resistência e pullback.","Começar no vocabulário tradicional para reduzir a curva de aprendizado."),
            _scene(2,"Onde ficam as ordens",65,"Adicionar pequenos marcadores acima dos topos e abaixo dos fundos.","Mostrar que extremos visíveis podem concentrar stops/ordens sem afirmar intenção de participantes específicos."),
            _scene(3,"Rompimento não é confirmação",75,"Preço ultrapassa a resistência, coleta o extremo e volta para dentro.","Diferenciar breakout, sweep e confirmação posterior."),
            _scene(4,"Da liquidez para a estrutura",85,"Após o sweep, destacar displacement e mudança estrutural.","Conectar o conceito conhecido à leitura ICT/SMC."),
            _scene(5,"Quando NÃO usar",70,"Exemplos de rompimento legítimo e mercado sem confirmação.","Evitar ensinar que toda varredura é reversão."),
            _scene(6,"Checklist AtlasQuant",80,"Tela Radar → dados → viés → liquidez → confirmação → invalidação.","Transformar conceito em processo simples e repetível."),
        ],
    },
    "liquidity-sweeps":{
        "target_seconds":480,
        "hook":"Antes de procurar entrada, descubra onde o preço pode estar procurando liquidez.",
        "scenes":[
            _scene(1,"Mapa de liquidez",60,"Marcar PDH/PDL, PWH/PWL, Asia High/Low e EQH/EQL.","Mostrar extremos objetivos e por que são observados."),
            _scene(2,"Sweep passo a passo",80,"Animar pavio atravessando um extremo e preço retornando.","Sweep é observação de preço; ainda não é entrada."),
            _scene(3,"Resposta do preço",90,"Adicionar candle de deslocamento após a varredura.","Exigir resposta/impulso em vez de antecipar reversão."),
            _scene(4,"MSS/CHOCH",80,"Destacar swing interno e fechamento estrutural.","Mostrar confirmação estrutural depois da liquidez."),
            _scene(5,"Continuação também existe",80,"Exemplo em que o extremo rompe e o preço continua.","Ensinar que nem toda busca de liquidez produz reversão."),
            _scene(6,"Aplicação no Radar",90,"Ativo com viés, dados, sessão e botão Por que isso?.","Ligar teoria à leitura prática sem ordem real."),
        ],
    },
    "fvg":{
        "target_seconds":420,
        "hook":"FVG fica muito mais simples quando você olha apenas três velas.",
        "scenes":[
            _scene(1,"As três velas",55,"Mostrar três candles numerados 1, 2 e 3; candle 2 com displacement.","Definir a sequência visual antes de colocar nomes."),
            _scene(2,"FVG de alta",75,"Animar high da vela 1 e low da vela 3; sombrear a faixa sem sobreposição entre esses níveis.","Explicar o desequilíbrio bullish de três velas com precisão."),
            _scene(3,"FVG de baixa",75,"Animar low da vela 1 e high da vela 3; sombrear a faixa sem sobreposição.","Espelhar o conceito para baixa."),
            _scene(4,"Por que o candle 2 importa",70,"Comparar displacement forte com três candles comuns sem impulso.","Evitar marcar qualquer pequeno espaço como FVG operacional."),
            _scene(5,"Retorno e invalidação",75,"Preço retorna parcialmente, respeita; depois mostrar exemplo atravessando totalmente.","Ensinar mitigação/revisita e quando a zona perde utilidade no modelo."),
            _scene(6,"Contexto primeiro",70,"Sobrepor liquidez, dealing range e direção maior.","FVG ajuda no timing; não cria sozinho o viés macro."),
        ],
    },
    "bos-choch-mss":{
        "target_seconds":500,
        "hook":"Rompimento de estrutura só faz sentido quando você sabe qual swing realmente importa.",
        "scenes":[
            _scene(1,"Swing válido",60,"Marcar HH/HL ou LH/LL em gráfico simples.","Separar ruído interno de pivôs relevantes."),
            _scene(2,"BOS",85,"Tendência continua e fecha além do swing na direção dominante.","BOS como continuidade, não como qualquer toque no nível."),
            _scene(3,"CHOCH / MSS",95,"Após sweep, mostrar displacement e quebra de swing oposto.","Explicar mudança de comportamento e necessidade de contexto."),
            _scene(4,"Pavio x fechamento",65,"Comparar só pavio além do nível com fechamento convincente.","Mostrar por que critérios objetivos reduzem falsas leituras."),
            _scene(5,"Timeframes",80,"H4/H1 como contexto e M15 como timing.","Evitar MSS pequeno contra estrutura maior sem confirmação."),
            _scene(6,"Checklist",115,"Liquidez → displacement → estrutura → retorno → invalidação.","Dar uma sequência didática para revisão."),
        ],
    },
    "order-block":{
        "target_seconds":520,
        "hook":"Order Block não é simplesmente a última vela vermelha antes de subir.",
        "scenes":[
            _scene(1,"Erro mais comum",55,"Circular várias velas contrárias aleatórias.","Mostrar por que marcar toda vela contrária cria dezenas de zonas inúteis."),
            _scene(2,"Origem relevante",85,"Destacar zona antes de displacement forte.","Relacionar OB a origem de movimento relevante."),
            _scene(3,"Estrutura",90,"Displacement rompe/muda estrutura e deixa zona de origem.","Exigir consequência estrutural, não apenas formato da vela."),
            _scene(4,"Liquidez e localização",85,"Adicionar sweep anterior e Premium/Discount.","Melhorar contexto da zona sem transformar confluência em garantia."),
            _scene(5,"Reteste",85,"Preço retorna ao bloco, reage; comparar com bloco atravessado.","Mostrar reação possível e invalidação."),
            _scene(6,"Planejamento",120,"Entrada hipotética, invalidação e alvo de liquidez sem executar ordem.","Ensinar processo de risco e cenário, não promessa."),
        ],
    },
    "breaker-mitigation":{
        "target_seconds":600,
        "hook":"Breaker começa fazendo sentido quando você vê uma zona falhar e mudar de função.",
        "scenes":[
            _scene(1,"Zona original",70,"Criar OB/zona estrutural original.","Estabelecer o ponto de referência."),
            _scene(2,"Falha da zona",95,"Preço atravessa a zona e confirma deslocamento do outro lado.","Mostrar invalidação real em vez de simples toque."),
            _scene(3,"Breaker",100,"No retorno, destacar a zona antiga sendo testada pelo lado oposto.","Explicar mudança de função dentro da sequência estrutural."),
            _scene(4,"Mitigation",100,"Mostrar retorno a uma origem relevante para mitigação/reequilíbrio.","Distinguir conceito de breaker sem fingir que nomenclaturas são universais."),
            _scene(5,"Confirmações",100,"Liquidez, displacement, estrutura e localização.","Evitar zonas isoladas."),
            _scene(6,"Dois exemplos inválidos",75,"Zonas rompidas sem sequência válida.","Treinar o aluno a dizer não."),
            _scene(7,"Resumo visual",60,"Fluxograma da sequência.","Fixar a ordem dos eventos."),
        ],
    },
    "ote":{
        "target_seconds":480,
        "hook":"A Fibonacci não escolhe a direção; ela mede onde está a retração dentro de um swing já validado.",
        "scenes":[
            _scene(1,"Escolha do swing",70,"Marcar low→high bullish e high→low bearish.","Sem swing válido, os níveis não têm contexto."),
            _scene(2,"Equilibrium 50%",55,"Traçar 50% como referência central do range.","Explicar premium/discount de forma visual."),
            _scene(3,"Zona OTE",90,"Destacar 62%–79% e linha de 70,5%.","Apresentar a faixa comum do modelo e 70,5 como referência, não número mágico."),
            _scene(4,"Confluência",90,"Adicionar FVG/OB/liquidez dentro ou perto da zona.","Mostrar que retração é localização, não sinal isolado."),
            _scene(5,"Invalidação",75,"Preço rompe swing/invalidação antes do gatilho.","Ensinar quando a ideia deixa de valer."),
            _scene(6,"Exemplo completo",100,"Do contexto HTF ao gatilho M15.","Juntar swing, OTE, estrutura e risco."),
        ],
    },
    "sessions-killzones":{
        "target_seconds":540,
        "hook":"O mesmo padrão pode ter leituras diferentes dependendo da sessão em que aparece.",
        "scenes":[
            _scene(1,"Relógio Forex",70,"Linha do tempo Ásia → Londres → Nova York.","Introduzir janelas sem afirmar que horário sozinho gera setup."),
            _scene(2,"Asia Range",80,"Construir Asia High/Low durante a faixa.","Criar referência objetiva para liquidez."),
            _scene(3,"Londres",95,"Sweep de um extremo da Ásia + resposta.","Exemplo de manipulação/expansão possível."),
            _scene(4,"New York AM",95,"Adicionar evento macro e interação com extremos anteriores.","Mostrar por que calendário importa no timing."),
            _scene(5,"Sem confirmação",75,"Sweep ocorre, mas estrutura não confirma.","Reforçar NÃO OPERAR."),
            _scene(6,"AtlasQuant",125,"Radar mostra sessão, notícia, viés, dados e próximo passo.","Levar a teoria à interface simples."),
        ],
    },
    "crt-amd":{
        "target_seconds":660,
        "hook":"CRT e AMD ficam mais fáceis quando você enxerga range, manipulação e expansão como uma sequência.",
        "scenes":[
            _scene(1,"Range",80,"Criar candle/range de referência e seus extremos.","Definir limites antes do movimento."),
            _scene(2,"Acumulação",90,"Preço negocia dentro da faixa.","Explicar espera e construção de liquidez."),
            _scene(3,"Manipulação",110,"Sweep de um lado e retorno.","Mostrar caça a extremo como observação, sem atribuir intenção certa."),
            _scene(4,"MSS / displacement",100,"Impulso confirma mudança após o sweep.","Exigir consequência estrutural."),
            _scene(5,"Distribuição / expansão",110,"Preço busca liquidez do outro lado.","Mapear alvo e invalidação."),
            _scene(6,"CRT",90,"Sobrepor o conceito de candle-range/raid.","Separar modelo da leitura retrospectiva."),
            _scene(7,"Erros comuns",80,"Exemplos sem range claro ou sem confirmação.","Evitar encaixar modelo em qualquer gráfico."),
        ],
    },
    "volume-profile":{
        "target_seconds":600,
        "hook":"Antes de olhar o perfil, descubra de onde vem o volume.",
        "scenes":[
            _scene(1,"Limitação do Forex spot",90,"Mostrar vários provedores/venues em vez de uma bolsa central.","Explicar que não existe um volume centralizado único do spot FX."),
            _scene(2,"Histograma por preço",80,"Construir barras horizontais de atividade.","Apresentar o conceito do perfil."),
            _scene(3,"POC e Value Area",100,"Destacar POC e região de valor.","Explicar aceitação de preço sem promessa direcional."),
            _scene(4,"HVN/LVN",90,"Comparar nós de alto e baixo volume.","Mostrar regiões de maior/menor atividade na fonte escolhida."),
            _scene(5,"Confluência",100,"Combinar com liquidez, estrutura e sessão.","Usar perfil como contexto adicional."),
            _scene(6,"Modo Iniciante x Avançado",80,"Iniciante vê resumo; avançado vê perfil completo.","Evitar poluição visual."),
            _scene(7,"Checklist da fonte",60,"Exibir nome da fonte e aviso metodológico.","Impedir falsa precisão."),
        ],
    },
    "atlasquant-reading":{
        "target_seconds":540,
        "hook":"Abra o AtlasQuant e descubra em menos de um minuto onde vale olhar primeiro.",
        "scenes":[
            _scene(1,"Escolha de modo",50,"Mostrar Iniciante e Avançado.","Explicar que o motor é o mesmo; muda a quantidade de informação visível."),
            _scene(2,"Radar",100,"Cartões de ativos com Compra/Venda/Não Operar, prioridade e dados.","Ensinar que o Radar ordena atenção, não executa ordens."),
            _scene(3,"Por que está assim?",100,"Abrir um ativo e destacar motivo, próximo passo, H4/H1/M15 e Gate.","Ensinar leitura causal/resumida."),
            _scene(4,"Ouvir análise",70,"Tocar botão de voz no dispositivo.","Mostrar acessibilidade e explicar que voz repete a leitura, sem criar sinal novo."),
            _scene(5,"Safety e dados",90,"Mostrar stale/hard block virando NÃO OPERAR.","Ensinar que segurança pode vetar um viés."),
            _scene(6,"Academy e Paper",80,"Abrir aula e validação Paper.","Mostrar caminho de aprendizado/treino."),
            _scene(7,"Modo Avançado",50,"Liberar diagnósticos completos.","Mostrar progressão sem assustar iniciante."),
        ],
    },
}


def video_blueprint(topic_id:object)->dict[str,Any]|None:
    key=str(topic_id or "").strip().casefold()
    topic=academy_topic(key)
    if topic is None:
        return None
    spec=dict(BLUEPRINTS.get(key,{}) or {})
    scenes=list(spec.get("scenes",[]) or [])
    if not scenes:
        scenes=[
            _scene(1,"Abertura",45,"Título + gráfico/infográfico simples.",topic["summary"]),
            _scene(2,"Conceito",90,"Animação visual do conceito.",topic["watch"]),
            _scene(3,"Aplicação",90,"Exemplo Forex progressivo.",topic["forex"]),
            _scene(4,"Erro comum",60,"Contraste exemplo válido x inválido.",topic["pitfall"]),
            _scene(5,"Checklist",60,"Resumo visual em passos.","Revisar conceito, risco e contexto antes de qualquer decisão."),
        ]
    total=sum(max(1,int(x.get("seconds",0))) for x in scenes)
    return {
        "schema":SCHEMA,
        "topic_id":topic["id"],
        "title":topic["title"],
        "level":topic["level"],
        "hook":str(spec.get("hook") or topic["summary"]),
        "scenes":scenes,
        "total_seconds":total,
        "max_seconds":MAX_VIDEO_SECONDS,
        "within_20_min":bool(total<=MAX_VIDEO_SECONDS),
        "animation_first":True,
        "rendered_video":False,
        "published_video":False,
        "automatic_publish":False,
        "trading_side_effects":False,
    }


def blueprint_catalog()->list[dict[str,Any]]:
    from atlasquant_academy import ACADEMY_TOPICS
    return [video_blueprint(x["id"]) for x in ACADEMY_TOPICS]


def blueprints_ready()->bool:
    rows=blueprint_catalog()
    return bool(rows) and all(
        x and x["scenes"] and x["within_20_min"] and x["total_seconds"]>0
        and x["animation_first"] and not x["rendered_video"] and not x["published_video"]
        for x in rows
    )


__all__=[
    "SCHEMA","MAX_VIDEO_SECONDS","BLUEPRINTS","video_blueprint",
    "blueprint_catalog","blueprints_ready",
]
