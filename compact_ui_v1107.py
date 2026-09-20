"""Shared, theme-aware presentation rules; no effect on calculations."""
import streamlit as st

COMPACT_CSS = """
<style>
.stMainBlockContainer {padding-top:1.3rem;padding-bottom:2rem;max-width:1480px;}
[data-testid="stVerticalBlock"] {gap:.7rem;}
h1 {font-size:1.85rem!important;letter-spacing:-.035em;padding-bottom:.3rem!important;}
h2 {font-size:1.35rem!important;letter-spacing:-.02em;}
h3 {font-size:1.1rem!important;}
h4 {font-size:1rem!important;}
[data-testid="stMetric"] {border:1px solid var(--secondary-background-color);border-radius:10px;padding:10px 12px!important;box-shadow:none!important;background:var(--secondary-background-color)!important;}
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * {font-size:1.4rem!important;line-height:1.25;color:var(--text-color,#111827)!important;font-weight:800!important;opacity:1!important;}
[data-testid="stMetricValue"] > div {white-space:normal!important;overflow:visible!important;text-overflow:clip!important;overflow-wrap:anywhere;}
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {font-size:.8rem!important;color:var(--text-color,#111827)!important;font-weight:650!important;opacity:.82!important;}
[data-testid="stNumberInput"] input,[data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea {color:var(--text-color,#111827)!important;-webkit-text-fill-color:var(--text-color,#111827)!important;font-weight:650!important;opacity:1!important;}
[data-testid="stAlert"] {padding:.65rem .85rem;border-radius:9px;}
[data-testid="stAlert"] p {font-size:.88rem;}
[role="tablist"] {gap:4px;flex-wrap:wrap!important;height:auto!important;overflow:visible!important;}
[role="tab"] {font-size:.85rem!important;height:36px!important;padding:0 11px!important;border-radius:7px;}
[role="tab"][aria-selected="true"] {background:var(--secondary-background-color);font-weight:650;}
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] {display:none;}
[data-testid="stExpander"] {border-radius:10px;}
@media(max-width:760px){
 .stMainBlockContainer {padding-left:1rem;padding-right:1rem;}
 [data-testid="stHorizontalBlock"] {flex-wrap:wrap!important;}
 [data-testid="stColumn"] {min-width:145px!important;flex:1 1 145px!important;}
 [role="tab"] {padding:0 8px!important;font-size:.8rem!important;}
}
</style>
"""

def apply_compact_theme():
    st.markdown(COMPACT_CSS, unsafe_allow_html=True)
