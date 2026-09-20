"""AtlasQuant contextual voice assistant.

Presentation/education only. It explains already-computed AtlasQuant state and
never fetches market data, changes a score/gate, sends an order, or converts
analysis into execution.

In-app speech output uses the browser/device speech engine only after an explicit
user action. Optional microphone input uses the browser SpeechRecognition API
when available; support/privacy characteristics depend on the user's browser.
"""
from __future__ import annotations

from html import escape
import json
import math
import re
import unicodedata
from typing import Any, Mapping, Sequence

import streamlit as st

SCHEMA="ATLASQUANT_VOICE_ASSISTANT_V1"

QUESTION_CATEGORIES=(
    "why","wrong","against","macro","technical","liquidity","event","data","next","overview",
)


def _safe(value:Any,default:float=0.0)->float:
    try:
        x=float(value)
        return x if math.isfinite(x) else float(default)
    except Exception:
        return float(default)


def _text(value:Any,fallback:str="não disponível")->str:
    out=str(value or "").strip()
    return out if out and out not in {"—","N/D","None"} else fallback


def _norm(value:object)->str:
    raw=unicodedata.normalize("NFKD",str(value or ""))
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).casefold()


def _json_for_script(value:Any)->str:
    """JSON safe inside an HTML script element; dynamic market text cannot close the script."""
    return (
        json.dumps(value,ensure_ascii=False)
        .replace("&","\\u0026")
        .replace("<","\\u003c")
        .replace(">","\\u003e")
        .replace("\u2028","\\u2028")
        .replace("\u2029","\\u2029")
    )


def _action(row:Mapping[str,Any])->str:
    action=str(row.get("action") or "").upper()
    if action in {"COMPRA","VENDA","NÃO OPERAR","NAO OPERAR"}:
        return "NÃO OPERAR" if "OPERAR" in action else action
    bias=str(row.get("bias") or row.get("side") or row.get("direction") or "").upper()
    if "COMPRA" in bias or "BUY" in bias:
        return "COMPRA"
    if "VENDA" in bias or "SELL" in bias:
        return "VENDA"
    return "NÃO OPERAR"


def _blockers(row:Mapping[str,Any])->list[str]:
    values=[]
    for key in ("hard_blocks","blockers","soft_blocks"):
        raw=row.get(key,[])
        if isinstance(raw,(list,tuple)):
            values.extend(str(x).strip() for x in raw if str(x).strip())
    # stable de-duplication
    return list(dict.fromkeys(values))


def _supporting(row:Mapping[str,Any])->list[str]:
    values=[]
    action=_action(row)
    keys=("up","positives") if action=="COMPRA" else ("down","positives") if action=="VENDA" else ("positives",)
    for key in keys:
        raw=row.get(key,[])
        if isinstance(raw,(list,tuple)):
            values.extend(str(x).strip() for x in raw if str(x).strip())
    return list(dict.fromkeys(values))


def assistant_context(
    row:Mapping[str,Any]|None,
    *,
    macro_context:Mapping[str,Any]|None=None,
)->dict[str,Any]:
    r=dict(row or {})
    macro=dict(macro_context or {})
    fed=dict(macro.get("fed",{}) or {})
    event=macro.get("event")
    if not isinstance(event,Mapping):
        event={}
    pair=_text(r.get("pair"),"este ativo")
    action=_action(r)
    ready_raw=r.get("data_ready")
    ready_map=dict(ready_raw) if isinstance(ready_raw,Mapping) else {}
    data_score_raw=r.get("data_score",ready_map.get("score",0))
    data_sufficient=bool(ready_map.get("sufficient",False)) if ready_map else bool(ready_raw)
    return {
        "schema":SCHEMA,
        "pair":pair,
        "action":action,
        "bias":_text(r.get("bias",r.get("direction")),"neutro"),
        "state":_text(r.get("state"),"aguardando"),
        "reason":_text(r.get("reason"),"não há motivo dominante suficiente"),
        "next_action":_text(r.get("next_action"),"aguardar confirmação válida"),
        "priority":max(0.0,min(100.0,_safe(r.get("priority",0)))),
        "quality":max(0.0,min(100.0,_safe(r.get("quality",0)))),
        "data_score":max(0.0,min(100.0,_safe(data_score_raw))),
        "h4":_text(r.get("h4")),
        "h1":_text(r.get("h1")),
        "m15":_text(r.get("m15")),
        "w1":_text(r.get("w1")),
        "d1":_text(r.get("d1")),
        "gate":_text(r.get("gate")),
        "event":_text(r.get("event"),_text(event.get("evento"),"normal")),
        "event_date":_text(event.get("data_txt",event.get("data")),"não confirmada"),
        "movement":_text(r.get("movement"),"não disponível"),
        "news":_text(r.get("news",r.get("news_align")),"não disponível"),
        "target":_text(r.get("target")),
        "pd_zone":_text(r.get("pd_zone")),
        "sweep_type":_text(r.get("sweep_type")),
        "sweep_level":_text(r.get("sweep_level")),
        "ict_read":max(0.0,min(100.0,_safe(r.get("ict_read",0)))),
        "inst_read":max(0.0,min(100.0,_safe(r.get("inst_read",0)))),
        "strength_diff":_safe(r.get("strength_diff",r.get("macro_diff",0)),0),
        "blockers":_blockers(r),
        "supporting":_supporting(r),
        "fed_tone":_text(fed.get("tom",macro.get("fed_tone")),"neutro"),
        "fed_strength":_safe(fed.get("forca",macro.get("fed_strength",0)),0),
        "usd_score":_safe(macro.get("usd_score",0),0),
        "data_sufficient":data_sufficient,
        "real_orders_enabled":False,
        "automatic_execution":False,
    }


def beginner_script(context:Mapping[str,Any])->str:
    c=dict(context or {})
    pair=_text(c.get("pair"),"este ativo")
    action=_action(c)
    if action=="COMPRA":
        lead=f"{pair}: o viés atual favorece alta"
    elif action=="VENDA":
        lead=f"{pair}: o viés atual favorece baixa"
    else:
        lead=f"{pair}: agora é não operar"
    reason=_text(c.get("reason"),"os dados ainda não deram vantagem clara")
    nxt=_text(c.get("next_action"),"aguardar confirmação")
    return (
        f"{lead}. Motivo principal: {reason}. "
        f"Próximo passo: {nxt}. "
        "Isso é uma leitura do AtlasQuant, não uma garantia nem uma ordem para corretora."
    )


def advanced_script(context:Mapping[str,Any])->str:
    c=dict(context or {})
    pair=_text(c.get("pair"),"este ativo")
    action=_action(c)
    support=[str(x) for x in list(c.get("supporting",[]) or []) if str(x).strip()]
    blockers=[str(x) for x in list(c.get("blockers",[]) or []) if str(x).strip()]
    support_txt="; ".join(support[:4]) if support else "nenhuma confluência adicional validada foi registrada"
    against_txt="; ".join(blockers[:4]) if blockers else "nenhum bloqueio explícito foi registrado, mas o cenário continua sujeito a invalidação"
    return (
        f"Análise avançada do {pair}. A leitura atual é {action}, com prioridade { _safe(c.get('priority')):.0f} "
        f"de 100, qualidade { _safe(c.get('quality')):.0f} e prontidão dos dados { _safe(c.get('data_score')):.0f}. "
        f"Motivo dominante: {_text(c.get('reason'))}. "
        f"Força relativa: {_safe(c.get('strength_diff')):+.1f} pontos. "
        f"Contexto técnico: W1 {_text(c.get('w1'))}; D1 {_text(c.get('d1'))}; H4 {_text(c.get('h4'))}; "
        f"H1 {_text(c.get('h1'))}; M15 {_text(c.get('m15'))}. Gate {_text(c.get('gate'))}. "
        f"Liquidez: sweep {_text(c.get('sweep_type'))} em {_text(c.get('sweep_level'))}; "
        f"Premium ou Discount: {_text(c.get('pd_zone'))}; alvo de referência {_text(c.get('target'))}. "
        f"Notícias: {_text(c.get('news'))}. Evento: {_text(c.get('event'))}. "
        f"Fed: tom {_text(c.get('fed_tone'))}, intensidade {_safe(c.get('fed_strength')):+.2f}. "
        f"Fatores a favor: {support_txt}. Fatores contra ou invalidações: {against_txt}. "
        f"Próximo passo: {_text(c.get('next_action'))}. "
        "A explicação descreve o estado calculado e não executa ordens nem garante resultado."
    )


def classify_question(question:object)->str:
    q=_norm(question)
    if not q:
        return "overview"
    patterns=(
        ("wrong",("errad","invalid","mudar o vies","muda o vies","chance de estar","probabilidade de estar","quando deixa")),
        ("against",("contra","risco","perigo","pode dar errado","fraqueza","bloque")),
        ("macro",("macro","fed","fomc","dxy","dolar","juros","inflacao","cpi","pce","payroll","pmi","banco central")),
        ("technical",("tecnic","h4","h1","m15","fvg","order block","breaker","mitigation","mss","choch","bos","ote","fibo","crt","amd")),
        ("liquidity",("liquid","sweep","varred","premium","discount","alvo","target","bsl","ssl")),
        ("event",("noticia","evento","calendario","news","release")),
        ("data",("dado","qualidade","stale","atualizado","frescor","confiavel","fonte")),
        ("next",("agora","proximo","esperar","o que fazer","qual passo","gatilho")),
        ("why",("porque","por que","motivo","razao","subir","descer","alta","baixa","compra","venda","vies")),
    )
    for category,terms in patterns:
        if any(term in q for term in terms):
            return category
    return "overview"


def _answer_for_category(category:str, c:Mapping[str,Any], *, beginner:bool=False)->str:
    c=dict(c or {})
    pair=_text(c.get("pair"),"este ativo")
    action=_action(c)
    blockers=[str(x) for x in list(c.get("blockers",[]) or []) if str(x).strip()]
    support=[str(x) for x in list(c.get("supporting",[]) or []) if str(x).strip()]

    if beginner:
        return beginner_script(c)
    if category=="wrong":
        why=("; ".join(blockers[:5]) if blockers else
             "o cenário pode mudar se estrutura, dados, evento ou gate deixarem de confirmar o estado atual")
        return (
            f"Sim, o viés de {pair} pode estar errado. O AtlasQuant não trata esse viés como certeza. "
            f"Hoje, os principais pontos que podem invalidar ou enfraquecer a leitura são: {why}. "
            f"H4 {_text(c.get('h4'))}, H1 {_text(c.get('h1'))}, M15 {_text(c.get('m15'))} e Gate {_text(c.get('gate'))}. "
            f"Se esses elementos deixarem de confirmar, a leitura deve voltar para aguardar ou não operar."
        )
    if category=="against":
        why="; ".join(blockers[:6]) if blockers else "não há bloqueio explícito registrado neste snapshot"
        return (
            f"Os fatores contra a leitura de {pair} são: {why}. "
            f"Evento: {_text(c.get('event'))}; movimento: {_text(c.get('movement'))}; dados {_safe(c.get('data_score')):.0f}/100. "
            "Mesmo sem bloqueio explícito, risco nunca é zero."
        )
    if category=="macro":
        return (
            f"No macro de {pair}, a diferença de força está em {_safe(c.get('strength_diff')):+.1f} pontos. "
            f"O tom do Fed está {_text(c.get('fed_tone'))}, com intensidade {_safe(c.get('fed_strength')):+.2f}. "
            f"Notícias: {_text(c.get('news'))}. Evento relevante: {_text(c.get('event'))}. "
            f"O motivo dominante registrado pelo motor é: {_text(c.get('reason'))}."
        )
    if category=="technical":
        return (
            f"No técnico de {pair}: W1 {_text(c.get('w1'))}; D1 {_text(c.get('d1'))}; "
            f"H4 {_text(c.get('h4'))}; H1 {_text(c.get('h1'))}; M15 {_text(c.get('m15'))}. "
            f"Leitura ICT {_safe(c.get('ict_read')):.0f}/100 e institucional {_safe(c.get('inst_read')):.0f}/100. "
            f"O Gate está {_text(c.get('gate'))}. Isso serve como confirmação ou veto do contexto, não como ordem automática."
        )
    if category=="liquidity":
        return (
            f"Na liquidez de {pair}, o sweep registrado é {_text(c.get('sweep_type'))} em {_text(c.get('sweep_level'))}. "
            f"A localização Premium ou Discount está {_text(c.get('pd_zone'))}, e o alvo de referência é {_text(c.get('target'))}. "
            "A liquidez precisa ser lida junto de deslocamento, estrutura, dados frescos e gate."
        )
    if category=="event":
        return (
            f"Para {pair}, a leitura de notícia está {_text(c.get('news'))}. "
            f"O evento atual está classificado como {_text(c.get('event'))}, com data {_text(c.get('event_date'))}. "
            "Evento de alto impacto pode reduzir a confiança do contexto e exigir nova confirmação depois da divulgação."
        )
    if category=="data":
        return (
            f"A prontidão dos dados de {pair} está em {_safe(c.get('data_score')):.0f}/100 e a qualidade em {_safe(c.get('quality')):.0f}/100. "
            f"O Gate está {_text(c.get('gate'))}. Se o dado ficar stale, incompleto ou inconsistente, o comportamento seguro é não operar."
        )
    if category=="next":
        return (
            f"Para {pair}, o próximo passo registrado é: {_text(c.get('next_action'))}. "
            f"A leitura atual é {action}. Isso descreve o que o modelo precisa ver a seguir; não é uma ordem para entrar no mercado."
        )
    if category=="why":
        extra=(" Fatores adicionais: "+"; ".join(support[:4])+".") if support else ""
        return (
            f"O {pair} está com leitura {action} principalmente porque {_text(c.get('reason'))}. "
            f"A diferença de força é {_safe(c.get('strength_diff')):+.1f} pontos, "
            f"com H4 {_text(c.get('h4'))}, H1 {_text(c.get('h1'))} e M15 {_text(c.get('m15'))}."
            f"{extra}"
        )
    return advanced_script(c)


def answer_question(
    question:object,
    context:Mapping[str,Any],
    *,
    mode:str="Avançado",
)->dict[str,Any]:
    c=dict(context or {})
    category=classify_question(question)
    beginner=not str(mode or "").casefold().startswith("avan")
    answer=_answer_for_category(category,c,beginner=beginner)
    return {
        "schema":SCHEMA,
        "category":category,
        "question":str(question or "").strip(),
        "answer":answer,
        "mode":"Avançado" if not beginner else "Iniciante",
        "pair":_text(c.get("pair"),"este ativo"),
        "real_orders_enabled":False,
        "automatic_execution":False,
        "changes_model_state":False,
    }


def browser_speech_html(text:object, *, button_label:str="🔊 Ouvir", key:str="voice")->str:
    safe_text=_json_for_script(str(text or ""))
    safe_key=re.sub(r"[^a-zA-Z0-9_-]","_",str(key or "voice"))
    label=escape(str(button_label or "🔊 Ouvir"))
    return f"""
    <div style="font-family:system-ui;margin:0;padding:0">
      <button id="speak_{safe_key}" style="width:100%;min-height:42px;border-radius:10px;border:1px solid rgba(120,150,190,.35);background:#10243d;color:#edf4ff;font-weight:700;cursor:pointer">{label}</button>
      <div id="status_{safe_key}" style="font-size:12px;color:#8fa5bf;margin-top:5px">Reprodução somente após seu toque.</div>
    </div>
    <script>
    (() => {{
      const btn=document.getElementById("speak_{safe_key}");
      const status=document.getElementById("status_{safe_key}");
      const text={safe_text};
      btn.addEventListener("click",()=>{{
        if(!("speechSynthesis" in window)){{
          status.textContent="Voz indisponível neste navegador. Use o texto exibido.";
          return;
        }}
        window.speechSynthesis.cancel();
        const u=new SpeechSynthesisUtterance(text);
        u.lang="pt-BR"; u.rate=.96; u.pitch=1.0;
        u.onstart=()=>status.textContent="Reproduzindo…";
        u.onend=()=>status.textContent="Concluído.";
        u.onerror=()=>status.textContent="Falha na reprodução neste dispositivo.";
        window.speechSynthesis.speak(u);
      }});
    }})();
    </script>
    """


def browser_mic_assistant_html(context:Mapping[str,Any], *, key:str)->str:
    """Optional browser mic: keyword Q&A in-page, with no trading side effects."""
    c=dict(context or {})
    answers={cat:_answer_for_category(cat,c,beginner=False) for cat in QUESTION_CATEGORIES}
    safe_answers=_json_for_script(answers)
    safe_key=re.sub(r"[^a-zA-Z0-9_-]","_",str(key or "assistant"))
    return f"""
    <div style="font-family:system-ui;border:1px solid rgba(137,170,210,.22);border-radius:12px;padding:10px;background:#0b1d31;color:#e7f0fb">
      <div style="font-weight:800;margin-bottom:7px">🎤 Conversa por voz no navegador</div>
      <div style="display:flex;gap:6px">
        <button id="mic_{safe_key}" style="min-height:40px;border-radius:9px;border:1px solid #36506f;background:#132d4a;color:white;font-weight:700;cursor:pointer">🎤 Falar</button>
        <button id="stop_{safe_key}" style="min-height:40px;border-radius:9px;border:1px solid #36506f;background:#132d4a;color:white;cursor:pointer">■ Parar</button>
      </div>
      <div id="heard_{safe_key}" style="font-size:12px;color:#91a7c0;margin-top:7px">O microfone depende do suporte do navegador e pode usar o serviço de reconhecimento dele.</div>
      <div id="reply_{safe_key}" style="font-size:13px;line-height:1.45;margin-top:8px"></div>
    </div>
    <script>
    (() => {{
      const answers={safe_answers};
      const heard=document.getElementById("heard_{safe_key}");
      const reply=document.getElementById("reply_{safe_key}");
      const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;
      let rec=null;
      const norm=(s)=>s.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g,"");
      const category=(q)=>{{
        const s=norm(q);
        const has=(xs)=>xs.some(x=>s.includes(x));
        if(has(["errad","invalid","chance","mudar o vies"]))return "wrong";
        if(has(["contra","risco","perigo","bloque"]))return "against";
        if(has(["macro","fed","fomc","dxy","juros","inflacao","payroll"]))return "macro";
        if(has(["tecnic","h4","h1","m15","fvg","order","mss","choch","bos","ote","fibo"]))return "technical";
        if(has(["liquid","sweep","varred","premium","discount","alvo","bsl","ssl"]))return "liquidity";
        if(has(["noticia","evento","calendario","release"]))return "event";
        if(has(["dado","qualidade","stale","frescor","fonte"]))return "data";
        if(has(["agora","proximo","esperar","o que fazer","gatilho"]))return "next";
        if(has(["porque","por que","motivo","subir","descer","alta","baixa","compra","venda","vies"]))return "why";
        return "overview";
      }};
      const speak=(text)=>{{
        if(!("speechSynthesis" in window))return;
        window.speechSynthesis.cancel();
        const u=new SpeechSynthesisUtterance(text);u.lang="pt-BR";u.rate=.96;
        window.speechSynthesis.speak(u);
      }};
      document.getElementById("mic_{safe_key}").onclick=()=>{{
        if(!SpeechRecognition){{
          heard.textContent="Reconhecimento de voz não é suportado neste navegador. Use o chat por texto.";
          return;
        }}
        rec=new SpeechRecognition();rec.lang="pt-BR";rec.interimResults=false;rec.maxAlternatives=1;
        rec.onstart=()=>heard.textContent="Ouvindo…";
        rec.onerror=(e)=>heard.textContent="Microfone indisponível: "+e.error;
        rec.onresult=(e)=>{{
          const q=e.results[0][0].transcript||"";
          heard.textContent="Você: "+q;
          const a=answers[category(q)]||answers.overview;
          reply.textContent="AtlasQuant: "+a;
          speak(a);
        }};
        rec.start();
      }};
      document.getElementById("stop_{safe_key}").onclick=()=>{{
        try{{if(rec)rec.stop();}}catch(e){{}}
        if("speechSynthesis" in window)window.speechSynthesis.cancel();
        heard.textContent="Parado.";
      }};
    }})();
    </script>
    """


def render_contextual_voice_assistant(
    row:Mapping[str,Any],
    *,
    mode:str="Iniciante",
    macro_context:Mapping[str,Any]|None=None,
    key_prefix:str="aq_voice",
)->dict[str,Any]:
    c=assistant_context(row,macro_context=macro_context)
    advanced=str(mode or "").casefold().startswith("avan")
    script=advanced_script(c) if advanced else beginner_script(c)
    pair_key=re.sub(r"[^a-zA-Z0-9_-]","_",c["pair"])

    st.markdown("### 🎙️ Assistente de Voz")
    if advanced:
        st.caption("Modo Avançado: explicação detalhada + perguntas contextuais. A resposta usa somente o estado já calculado pelo AtlasQuant.")
    else:
        st.caption("Modo Iniciante: explicação curta, direta e sem excesso de siglas.")

    st.iframe(
        browser_speech_html(script,button_label="🔊 Ouvir análise",key=f"{key_prefix}_{pair_key}_summary"),
        height=72,width="stretch",tab_index=0,
    )
    with st.expander("Ler o que será falado"):
        st.write(script)

    answer=None
    category=None
    if advanced:
        quick=st.selectbox(
            "Pergunta rápida",
            [
                "Por que esse viés?",
                "O que pode invalidar esse viés?",
                "Quais fatores estão contra?",
                "Como está o macro e o Fed?",
                "Como está o técnico?",
                "Como está a liquidez?",
                "Tem risco de notícia?",
                "Os dados estão confiáveis?",
                "Qual é o próximo passo?",
            ],
            key=f"{key_prefix}_{pair_key}_quick",
        )
        typed=st.text_input(
            "Ou pergunte com suas palavras",
            placeholder="Ex.: o que faria esse viés ficar errado?",
            key=f"{key_prefix}_{pair_key}_question",
        )
        if st.button("Responder",key=f"{key_prefix}_{pair_key}_ask",width="stretch"):
            q=typed.strip() or quick
            result=answer_question(q,c,mode="Avançado")
            answer=result["answer"];category=result["category"]
            st.session_state[f"{key_prefix}_{pair_key}_last_answer"]=answer
            st.session_state[f"{key_prefix}_{pair_key}_last_category"]=category

        answer=answer or st.session_state.get(f"{key_prefix}_{pair_key}_last_answer")
        category=category or st.session_state.get(f"{key_prefix}_{pair_key}_last_category")
        if answer:
            st.info(str(answer))
            st.iframe(
                browser_speech_html(answer,button_label="🔊 Ouvir resposta",key=f"{key_prefix}_{pair_key}_answer"),
                height=72,width="stretch",tab_index=0,
            )

        with st.expander("🎤 Conversar por microfone no navegador",expanded=False):
            st.caption("Opcional. O reconhecimento de voz depende do navegador; se não houver suporte, o chat por texto continua funcionando.")
            st.iframe(
                browser_mic_assistant_html(c,key=f"{key_prefix}_{pair_key}_mic"),
                height=245,width="stretch",tab_index=0,
            )

    return {
        "schema":SCHEMA,
        "mode":"Avançado" if advanced else "Iniciante",
        "pair":c["pair"],
        "script":script,
        "last_answer":answer,
        "last_category":category,
        "real_orders_enabled":False,
        "automatic_execution":False,
        "changes_model_state":False,
    }


__all__=[
    "SCHEMA","QUESTION_CATEGORIES","assistant_context","beginner_script","advanced_script",
    "classify_question","answer_question","browser_speech_html","browser_mic_assistant_html",
    "render_contextual_voice_assistant",
]
