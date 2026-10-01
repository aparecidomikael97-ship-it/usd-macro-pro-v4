"""Test-only Streamlit exercise of the actual Library shell renderer.

Never import into the production app. This synthetic fixture refuses to start
unless the CI-only environment guard is set; it has no real DB or users.
"""
import os
import time
import streamlit as st

from atlasquant_access_control import AccessUser, authenticate, hash_password
from atlasquant_aion_library_workspace_shell import (
    library_shell_gate, library_workspace_choices, render_library_shell,
)

if os.environ.get('AION_LIBRARY_BROWSER_FIXTURE') != 'CI_SYNTHETIC_ONLY':
    raise RuntimeError('browser fixture disabled outside isolated CI')

st.set_page_config(page_title='Biblioteca AION - Ensaio sintético',layout='wide')
scenario=os.environ.get('AION_LIBRARY_TEST_SCENARIO','disabled')
if scenario not in {'allowed','disabled','expired','user','production'}:
    raise RuntimeError('unsupported synthetic scenario')
now=int(time.time())
pw='SyntheticBrowserPassword##'
hash_=hash_password(pw,salt=b't'*16,iterations=200_000)
role='USER' if scenario=='user' else 'ADMIN'
users={'fixture.1': AccessUser('fixture.1',role,hash_)}
ses=authenticate('fixture.1',pw,users)
if scenario=='expired':
    issued,last=now-50_000,now-10_000
else:
    issued,last=now-15,now-2
access={'allowed':True,'mode':'AUTHENTICATED','role':role,
        'session':dict(ses, authenticated_at=issued,last_seen=last)}

def check(session,clock):
    return {'valid': 0 < session['authenticated_at'] <= session['last_seen'] <= clock
            and clock-session['authenticated_at'] <= 43_200
            and clock-session['last_seen'] <= 7_200}

gate=library_shell_gate(
    access=access,users=users,
    environment='PRODUCTION' if scenario=='production' else 'SANDBOX',
    preview_flag='false' if scenario=='disabled' else 'true',
    now=now, session_time_check=check)
choices=library_workspace_choices(standard=('🧠 Central','🗂️ Secretaria'),gate=gate)
st.caption('Ensaio visual isolado · Nenhuma conta ou documento real')
st.selectbox('Área AION',choices,key='aion_test_area')
if gate['visible']:
    render_library_shell(st,gate=gate)
else:
    st.warning('Biblioteca indisponível neste cenário de acesso.')
