"""AtlasQuant Academy visual micro-animations.

Pure local HTML/CSS/SVG teaching aids. No external assets, scripts, providers,
network calls or trading side effects.
"""
from __future__ import annotations

import streamlit as st

SCHEMA="ATLASQUANT_ACADEMY_VISUALS_V1"

_BASE_CSS="""
<style>
.aqviz{position:relative;overflow:hidden;border:1px solid rgba(137,170,210,.22);border-radius:14px;
background:linear-gradient(180deg,#0d2036,#081624);height:250px;margin:8px 0 12px;color:#dceaff;font-family:system-ui}
.aqviz .grid{position:absolute;inset:0;background-image:linear-gradient(rgba(160,190,220,.07) 1px,transparent 1px),linear-gradient(90deg,rgba(160,190,220,.07) 1px,transparent 1px);background-size:32px 32px}
.aqviz .label{position:absolute;font-size:12px;font-weight:700;padding:4px 7px;border-radius:7px;background:rgba(8,20,34,.86);border:1px solid rgba(137,170,210,.2)}
.aqviz .note{position:absolute;left:14px;bottom:10px;right:14px;font-size:11px;color:#91a7c0}
.aqviz .zone{position:absolute;border:1px dashed rgba(109,226,197,.85);background:rgba(109,226,197,.12);border-radius:6px}
.aqviz .danger{border-color:rgba(255,107,122,.9);background:rgba(255,107,122,.1)}
.aqviz .candle{position:absolute;width:18px;border-radius:2px;animation:aq-pop .8s both}
.aqviz .wick{position:absolute;width:2px;left:8px;background:#cad7e8}
@keyframes aq-pop{from{opacity:.1;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
@keyframes aq-pulse{0%,100%{opacity:.35}50%{opacity:1}}
@keyframes aq-slide{0%{transform:translateX(-8px);opacity:.2}100%{transform:translateX(0);opacity:1}}
.aqviz .pulse{animation:aq-pulse 2.3s infinite}.aqviz .slide{animation:aq-slide 1.6s both}
</style>
"""


def _fvg()->str:
    return _BASE_CSS+"""
<div class="aqviz"><div class="grid"></div>
<div class="label" style="left:16px;top:12px">FVG bullish · 3 velas</div>
<div class="candle" style="left:25%;top:128px;height:48px;background:#45d39a;animation-delay:.1s">
 <div class="wick" style="top:-20px;height:88px"></div></div>
<div class="candle" style="left:48%;top:58px;height:86px;background:#45d39a;animation-delay:.45s">
 <div class="wick" style="top:-18px;height:122px"></div></div>
<div class="candle" style="left:72%;top:68px;height:48px;background:#45d39a;animation-delay:.8s">
 <div class="wick" style="top:-15px;height:80px"></div></div>
<div class="zone pulse" style="left:29%;right:24%;top:112px;height:20px"></div>
<div class="label" style="left:39%;top:142px">faixa sem sobreposição<br>high vela 1 ↔ low vela 3</div>
<div class="note">O candle 2 cria displacement. A faixa destacada ajuda no timing; sozinha não define direção nem garante retorno.</div>
</div>"""


def _ote()->str:
    return _BASE_CSS+"""
<div class="aqviz"><div class="grid"></div>
<div class="label" style="left:16px;top:12px">OTE · retração dentro de swing válido</div>
<div style="position:absolute;left:18%;right:12%;top:52px;height:150px;border-left:3px solid #6de2c5;border-right:3px solid #6de2c5"></div>
<div class="label" style="left:11%;top:42px">0%</div>
<div class="label" style="left:11%;top:108px">50% EQ</div>
<div class="zone" style="left:18%;right:12%;top:133px;height:50px"></div>
<div class="label" style="right:14%;top:132px">62%</div>
<div class="label pulse" style="right:28%;top:151px">70,5%</div>
<div class="label" style="right:14%;top:176px">79%</div>
<div class="label" style="left:11%;top:194px">100%</div>
<div class="note">50% marca equilíbrio; a zona 62–79% e a referência 70,5% são localização no modelo, não números mágicos nem sinal isolado.</div>
</div>"""


def _liquidity()->str:
    return _BASE_CSS+"""
<div class="aqviz"><div class="grid"></div>
<div class="label" style="left:16px;top:12px">Sweep de liquidez → resposta → MSS</div>
<svg viewBox="0 0 640 210" style="position:absolute;left:0;top:20px;width:100%;height:210px">
 <line x1="60" y1="80" x2="580" y2="80" stroke="#7189a5" stroke-dasharray="7 6"/>
 <text x="65" y="70" fill="#9fb0c6" font-size="12">topos / liquidez</text>
 <path d="M60 155 L120 125 L180 145 L240 105 L300 122 L350 78 L382 48 L410 96 L452 125 L505 105 L565 142"
       fill="none" stroke="#6de2c5" stroke-width="4" class="slide"/>
 <circle cx="382" cy="48" r="10" fill="#ff6b7a" class="pulse"/>
 <text x="395" y="47" fill="#ff9aa6" font-size="12">sweep</text>
 <line x1="405" y1="120" x2="515" y2="120" stroke="#f1c75b" stroke-dasharray="6 5"/>
 <text x="455" y="114" fill="#f1c75b" font-size="12">swing</text>
</svg>
<div class="note">O sweep não é entrada automática. A leitura melhora quando há displacement e confirmação estrutural posterior.</div>
</div>"""


def _order_block()->str:
    return _BASE_CSS+"""
<div class="aqviz"><div class="grid"></div>
<div class="label" style="left:16px;top:12px">Order Block · origem + consequência estrutural</div>
<div class="zone" style="left:18%;width:20%;top:137px;height:34px"></div>
<div class="label" style="left:19%;top:177px">zona de origem</div>
<div class="candle" style="left:24%;top:132px;height:34px;background:#ff6b7a"><div class="wick" style="top:-14px;height:62px"></div></div>
<div class="candle" style="left:40%;top:112px;height:44px;background:#45d39a;animation-delay:.25s"><div class="wick" style="top:-16px;height:72px"></div></div>
<div class="candle" style="left:52%;top:78px;height:61px;background:#45d39a;animation-delay:.5s"><div class="wick" style="top:-14px;height:88px"></div></div>
<div class="candle" style="left:64%;top:50px;height:53px;background:#45d39a;animation-delay:.75s"><div class="wick" style="top:-13px;height:80px"></div></div>
<div class="label pulse" style="left:50%;top:25px">displacement + estrutura</div>
<div class="note">Não basta escolher “a última vela contrária”. A zona precisa de contexto, deslocamento/consequência estrutural e regra de invalidação.</div>
</div>"""


def _structure()->str:
    return _BASE_CSS+"""
<div class="aqviz"><div class="grid"></div>
<div class="label" style="left:16px;top:12px">BOS / CHOCH / MSS</div>
<svg viewBox="0 0 640 210" style="position:absolute;left:0;top:24px;width:100%;height:205px">
 <path d="M45 165 L125 105 L190 140 L270 72 L335 115 L405 62 L470 108 L535 142 L595 92"
       fill="none" stroke="#6de2c5" stroke-width="4"/>
 <circle cx="125" cy="105" r="5" fill="#edf4ff"/><circle cx="270" cy="72" r="5" fill="#edf4ff"/>
 <circle cx="405" cy="62" r="5" fill="#edf4ff"/><circle cx="535" cy="142" r="7" fill="#ff6b7a" class="pulse"/>
 <line x1="270" y1="72" x2="405" y2="72" stroke="#f1c75b" stroke-dasharray="6 5"/>
 <text x="300" y="62" fill="#f1c75b" font-size="12">BOS continuidade</text>
 <line x1="470" y1="108" x2="590" y2="108" stroke="#ff9aa6" stroke-dasharray="6 5"/>
 <text x="500" y="100" fill="#ff9aa6" font-size="12">MSS/CHOCH</text>
</svg>
<div class="note">O nível precisa ser um swing relevante e a confirmação deve seguir regra objetiva. Pavio isolado não é automaticamente mudança estrutural.</div>
</div>"""


def _volume_profile()->str:
    bars=[(52,35),(72,55),(92,90),(112,145),(132,190),(152,150),(172,95),(192,55)]
    rects="".join(
        f'<div style="position:absolute;left:42%;top:{top}px;width:{width}px;height:14px;background:rgba(109,226,197,.34);border-radius:0 6px 6px 0"></div>'
        for top,width in bars
    )
    return _BASE_CSS+f"""
<div class="aqviz"><div class="grid"></div>
<div class="label" style="left:16px;top:12px">Volume Profile · atividade por preço</div>
{rects}
<div class="label pulse" style="left:66%;top:127px">POC</div>
<div class="zone" style="left:39%;width:44%;top:100px;height:78px"></div>
<div class="label" style="left:15%;top:105px">Value Area</div>
<div class="note">No Forex spot, mostre sempre a fonte: tick/volume de um provedor não é o volume centralizado de todo o mercado.</div>
</div>"""


_VISUALS={
    "fvg":_fvg,
    "ote":_ote,
    "liquidity-sweeps":_liquidity,
    "order-block":_order_block,
    "bos-choch-mss":_structure,
    "liquidity-structure":_structure,
    "volume-profile":_volume_profile,
}


def concept_visual_html(topic_id:object)->str:
    fn=_VISUALS.get(str(topic_id or "").strip().casefold())
    return "" if fn is None else fn()


def visual_topics()->tuple[str,...]:
    return tuple(sorted(_VISUALS))


def render_concept_visual(topic_id:object)->bool:
    html=concept_visual_html(topic_id)
    if not html:
        return False
    st.markdown(html,unsafe_allow_html=True)
    return True


__all__=["SCHEMA","concept_visual_html","visual_topics","render_concept_visual"]
