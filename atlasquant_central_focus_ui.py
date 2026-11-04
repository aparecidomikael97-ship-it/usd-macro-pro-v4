"""Focused private central landing for AtlasQuant. Presentation only, no provider IO."""
from __future__ import annotations

from html import escape


_CSS = """
<style>
.aqc-focus{width:100%;min-height:780px;padding:0!important;background:#070e1b!important;color:#ebf5ff;font-family:Inter,Segoe UI,Arial,sans-serif;border:1px solid #223952;border-radius:15px;overflow:hidden}
.aqc-focus *{box-sizing:border-box}.aqc-focus button{font:inherit;cursor:pointer}
.aqc-top{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;padding:17px 25px;background:#0a182a;border-bottom:1px solid #213b53}
.aqc-brand{display:flex;align-items:center;gap:11px}.aqc-logo{display:grid;place-items:center;width:40px;height:40px;border:1px solid #47bfe2;border-radius:12px;color:#73eff5;font-size:25px;font-weight:950;background:#12354a}
.aqc-brand strong{display:block;letter-spacing:.12em;font-size:16px}.aqc-brand small{font-size:9px;letter-spacing:.22em;color:#7ab9d8;font-weight:850}
.aqc-user{display:flex;align-items:center;gap:9px}.aqc-user strong{font-size:12px}.aqc-user small{display:block;color:#9fb1c4;font-size:10px}
.aqc-avatar-button{position:relative;display:grid;place-items:center;overflow:hidden;border:2px solid #53d3e8;border-radius:50%;width:44px;height:44px;background:#173951;color:#eaf9ff;font-size:18px;font-weight:850}
.aqc-avatar-button img{position:absolute;width:100%;height:100%;object-fit:cover;inset:0}.aqc-edit-photo{border:1px solid #416680;border-radius:8px;padding:8px 11px;background:#112a3e;color:#ccecf5;font-size:11px}
.aqc-layout{display:grid;grid-template-columns:188px minmax(0,1fr);min-height:725px}
.aqc-aside{padding:25px 11px;background:#0a1627;border-right:1px solid #223b56}
.aqc-aside-label{font-size:10px;font-weight:850;letter-spacing:.14em;color:#87a8bd;margin:0 10px 14px}
.aqc-aside button{display:block;width:100%;text-align:left;margin-bottom:8px;padding:12px 13px;border:1px solid transparent;border-radius:10px;background:transparent;color:#a9c3d5;font-size:12px}
.aqc-aside button:hover,.aqc-aside button:focus-visible{border-color:#42b9d1;background:#14354a;color:#fff}
.aqc-aside button.aqc-current{background:#13384b;border-color:#45c7da;color:#e7fbff;font-weight:850}
.aqc-aside .aqc-muted-link{font-size:11px;color:#8ba5b7}
.aqc-main{min-width:0;padding:30px clamp(16px,3vw,46px);background:radial-gradient(circle at 78% 2%,#12344b55,transparent 39%),#091422}
.aqc-kicker{color:#5ce4ec;letter-spacing:.16em;font-size:11px;font-weight:900}
.aqc-main h1{font-size:clamp(24px,3vw,37px);margin:9px 0 8px;font-weight:900;letter-spacing:-.035em}
.aqc-lead{font-size:13px;color:#b0c6d9;line-height:1.65;margin:0 0 19px}
.aqc-hero{position:relative;overflow:hidden;border:1px solid #36859b;border-radius:19px;background:linear-gradient(110deg,#102639 0%,#11384d 68%,#12374e 100%);padding:29px clamp(17px,3vw,38px);box-shadow:0 10px 30px #0003}
.aqc-hero:after{content:"";position:absolute;width:290px;height:290px;right:-65px;top:-65px;border:27px solid #54d9ee13;border-radius:50%;pointer-events:none}
.aqc-hero>*{position:relative;z-index:1}.aqc-hero h2{font-size:clamp(27px,3.2vw,39px);margin:9px 0 5px;font-weight:900;letter-spacing:-.03em}
.aqc-hero h3{font-size:16px;color:#78eaf0;margin:0 0 12px;font-weight:800}
.aqc-hero p{font-size:12px;line-height:1.65;color:#bdd4e2;max-width:660px}
.aqc-badges{display:flex;flex-wrap:wrap;gap:8px;margin:20px 0}
.aqc-badges span{font-size:10px;border:1px solid #396e83;border-radius:6px;background:#0e2e41;padding:7px 9px;color:#d0f7fb}
.aqc-primary{display:inline-flex;align-items:center;gap:8px;padding:13px 18px;background:#42d4e5;border:1px solid #77f4f8;border-radius:10px;color:#063044;font-weight:900;font-size:13px}
.aqc-primary:hover{background:#82eff7}
.aqc-shortcut-title{display:flex;align-items:baseline;justify-content:space-between;gap:12px;flex-wrap:wrap;margin:25px 0 12px}
.aqc-shortcut-title h3{font-size:15px;margin:0}.aqc-shortcut-title small{font-size:11px;color:#839fb9}
.aqc-shortcuts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:11px}
.aqc-shortcuts button{padding:14px;border:1px solid #2a5067;border-radius:12px;background:#102738;color:#d8f6fb;text-align:left;min-height:80px}
.aqc-shortcuts button:hover{border-color:#53dbe7;background:#153c50}
.aqc-shortcuts strong{font-size:13px;display:block}.aqc-shortcuts small{font-size:10px;display:block;color:#94b8cc;margin-top:7px}
.aqc-other{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:11px}
.aqc-other button{min-height:70px;text-align:left;padding:12px;border:1px solid #2b4258;border-radius:11px;color:#b5c8d9;background:#0c1d2d}
.aqc-other button strong{font-size:12px;display:block;color:#e5f3fc}.aqc-other button small{display:block;font-size:10px;margin-top:5px;color:#8da5b8}
.aqc-other button:hover{border-color:#4da6ba}
.aqc-foot{font-size:11px;color:#8299af;margin:21px 0 0;line-height:1.55}
.aqc-photo-help{font-size:10px;color:#8caabe;max-width:220px}
.aqc-focus button:focus-visible{outline:3px solid #85ebf3;outline-offset:2px}
@media(max-width:900px){.aqc-layout{grid-template-columns:145px minmax(0,1fr)}.aqc-other{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:650px){.aqc-layout{display:block}.aqc-aside{display:flex;gap:5px;padding:9px;overflow-x:auto}.aqc-aside-label{display:none}.aqc-aside button{width:auto;min-width:max-content;padding:10px;margin:0}.aqc-main{padding:17px}.aqc-shortcuts{grid-template-columns:1fr}.aqc-top{padding:12px}.aqc-user strong{display:none}.aqc-user small{display:none}.aqc-edit-photo{font-size:10px}.aqc-hero{padding:21px}.aqc-other{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""


def focused_central_html(name: str = "Usuário") -> str:
    """All navigation reuses the existing authenticated central routing gate.

    The photo is local to this browser, never sent to the public repository.
    """
    display = escape(str(name or "Usuário")[:100])
    initial = escape((str(name or "U").strip()[:1] or "U").upper())
    avatar_key = escape(str(name or "Usuário")[:100], quote=True)
    return (
        _CSS + '<section class="ref-workspace ref-central aqc-focus" data-workspace="central" data-avatar-key="' + avatar_key + '">'
        '<header class="aqc-top"><div class="aqc-brand"><span class="aqc-logo">A</span>'
        '<div><strong>ATLASQUANT</strong><small>ECOSSISTEMA</small></div></div>'
        '<div class="aqc-user"><div><strong>' + display + '</strong><small>Perfil pessoal</small></div>'
        '<button type="button" class="aqc-avatar-button" data-avatar-editor aria-label="Trocar foto do perfil">'
        '<span data-avatar-initial>' + initial + '</span><img data-profile-avatar alt="Foto do perfil" hidden></button>'
        '<button type="button" class="aqc-edit-photo" data-avatar-editor>Editar foto</button>'
        '<input type="file" data-avatar-input accept="image/png,image/jpeg,image/webp" aria-label="Selecionar foto" hidden>'
        '<button type="button" class="aqc-edit-photo" data-avatar-clear>Remover foto</button>'
        '<span class="aqc-photo-help" data-avatar-status aria-live="polite"></span></div></header>'
        '<div class="aqc-layout"><aside class="aqc-aside"><p class="aqc-aside-label">ÁREAS</p>'
        '<button class="aqc-current" data-route="home">⌂ Central</button>'
        '<button data-route="area:trader_radar">◉ AtlasQuant Trader</button>'
        '<button data-route="area:investimentos">▥ Investimentos</button>'
        '<button data-route="area:aion">✧ AION</button>'
        '<button data-route="profile" class="aqc-muted-link">Perfil</button>'
        '<button data-route="notifications" class="aqc-muted-link">Notificações</button>'
        '<button data-route="settings" class="aqc-muted-link">Configurações</button>'
        '<button data-route="session" class="aqc-muted-link">Sessão</button>'
        '</aside><main class="aqc-main"><span class="aqc-kicker">PAINEL DE CONTROLE · FOCO ATUAL</span>'
        '<h1>Bem-vindo ao seu AtlasQuant.</h1>'
        '<p class="aqc-lead">Seu ambiente de análise, com prioridade para Forex e Índices.</p>'
        '<section class="aqc-hero" aria-label="Área principal AtlasQuant Trader">'
        '<span class="aqc-kicker">ÁREA PRINCIPAL</span><h2>ATLASQUANT TRADER</h2>'
        '<h3>Forex &amp; Índices</h3>'
        '<p>Força relativa de moedas, 28 pares Forex, índices internacionais, WIN/WDO '
        'e contexto econômico em um painel direto e organizado.</p>'
        '<div class="aqc-badges"><span>28 PARES FOREX</span><span>8 MOEDAS</span>'
        '<span>WIN / WDO</span><span>D1 · H4 · M15</span></div>'
        '<button type="button" class="aqc-primary" data-route="area:trader_radar">Acessar AtlasQuant Trader →</button>'
        '</section><div class="aqc-shortcut-title"><h3>Comece sua análise</h3>'
        '<small>Três áreas objetivas, sem excesso de informação</small></div>'
        '<div class="aqc-shortcuts">'
        '<button data-route="open:home"><strong>⌂ Início</strong><small>Panorama e principais eventos do dia</small></button>'
        '<button data-route="open:radar"><strong>◉ Radar</strong><small>Moedas, Forex, índices e vieses</small></button>'
        '<button data-route="open:master"><strong>▦ Painel Mestre</strong><small>Macro, micro, geopolítica, notícias e calendário</small></button>'
        '</div><div class="aqc-shortcut-title"><h3>Demais áreas</h3>'
        '<small>Estruturas preservadas para o futuro</small></div>'
        '<div class="aqc-other">'
        '<button data-route="area:trader"><strong>Trader</strong><small>Área original</small></button>'
        '<button data-route="area:negocios"><strong>Negócios</strong><small>Em pausa</small></button>'
        '<button data-route="area:investimentos"><strong>Investimentos</strong><small>Em preparação</small></button>'
        '<button data-route="area:aion"><strong>AION</strong><small>Núcleo congelado</small></button>'
        '</div><p class="aqc-foot">Poderoso por dentro. Simples por fora. '
        'Dados e vieses só serão exibidos quando houver evidências validadas. '
        'A foto de perfil é guardada somente neste navegador.</p>'
        '</main></div></section>'
    )


__all__ = ["focused_central_html"]
