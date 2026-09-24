import os
import unittest

from streamlit.testing.v1 import AppTest


class AtlasQuantAionAdminRuntimeTests(unittest.TestCase):
    def test_admin_console_renders_without_external_integrations(self):
        script = r'''
import os
os.environ["GITHUB_TOKEN_HISTORICO"]=""
os.environ["GITHUB_REPO_HISTORICO"]=""
os.environ["GITHUB_DATA_BRANCH"]="atlasquant-runtime"
os.environ["AION_MODEL_PROVIDER"]="offline"
from atlasquant_aion_admin import render_aion_admin_console
result=render_aion_admin_console(
    {"role":"ADMIN","username":"admin.test"},
    market_context={"fresh_confirmed":False,"summary":""},
    system_context={
        "truth_state":"CONFIRMED",
        "source_build":"test-build",
        "environment":"LOCAL",
        "app_version":"test",
        "market_status":"não confirmado nesta tela",
    },
)
import streamlit as st
st.write("AION_RUNTIME_OK",result["allowed"],result["real_orders_enabled"])
'''
        app=AppTest.from_string(script)
        app.run(timeout=45)
        self.assertEqual(len(app.exception),0)
        self.assertGreaterEqual(len(app.button),1)
        self.assertGreaterEqual(len(app.metric),8)
        self.assertGreaterEqual(len(app.selectbox),1)
        self.assertEqual(str(app.selectbox[0].value),"🧠 Central")

    def test_selected_workspace_failure_is_isolated_without_raw_exception_message(self):
        script = r'''
import os
os.environ["GITHUB_TOKEN_HISTORICO"]=""
os.environ["GITHUB_REPO_HISTORICO"]=""
os.environ["GITHUB_DATA_BRANCH"]="atlasquant-runtime"
os.environ["AION_MODEL_PROVIDER"]="offline"
import atlasquant_aion_admin as aion_admin

def explode(*args, **kwargs):
    raise RuntimeError("secret internal trace must not be shown")

aion_admin._render_central = explode
result=aion_admin.render_aion_admin_console(
    {"role":"ADMIN","username":"admin.test"},
    market_context={"fresh_confirmed":False,"summary":""},
    system_context={
        "truth_state":"CONFIRMED",
        "source_build":"test-build",
        "environment":"LOCAL",
        "app_version":"test",
        "market_status":"não confirmado nesta tela",
    },
)
import streamlit as st
st.write(
    "AION_WORKSPACE_ISOLATION",
    result["workspace_status"],
    result["workspace_error_type"],
    result["real_orders_enabled"],
)
'''
        app=AppTest.from_string(script)
        app.run(timeout=45)
        self.assertEqual(len(app.exception),0)
        self.assertGreaterEqual(len(app.error),1)
        self.assertIn("erro isolado",str(app.error[0].value).lower())
        page_text=" ".join(str(x.value) for group in (
            app.error, app.caption, app.markdown, app.info, app.warning, app.success
        ) for x in group)
        self.assertIn("RuntimeError",page_text)
        self.assertNotIn("secret internal trace must not be shown",page_text)

    def test_foundation_auxiliary_failures_open_in_safe_degraded_mode(self):
        script = r'''
import os
os.environ["GITHUB_TOKEN_HISTORICO"]=""
os.environ["GITHUB_REPO_HISTORICO"]=""
os.environ["GITHUB_DATA_BRANCH"]="atlasquant-runtime"
os.environ["AION_MODEL_PROVIDER"]="offline"
import atlasquant_aion_admin as aion_admin

def explode(*args, **kwargs):
    raise RuntimeError("sensitive foundation trace must not be shown")

aion_admin.configured_users = explode
aion_admin.audit_account_entitlements = explode
aion_admin.build_master_status_board = explode
aion_admin.collect_approval_inbox = explode

result=aion_admin.render_aion_admin_console(
    {"role":"ADMIN","username":"admin.test"},
    market_context={"fresh_confirmed":False,"summary":""},
    system_context={
        "truth_state":"CONFIRMED",
        "source_build":"test-build",
        "environment":"LOCAL",
        "app_version":"test",
        "market_status":"não confirmado nesta tela",
    },
)
import streamlit as st
st.write(
    "AION_FOUNDATION_RESILIENCE",
    result["foundation_status"],
    len(result["foundation_diagnostics"]),
    result["real_orders_enabled"],
)
'''
        app=AppTest.from_string(script)
        app.run(timeout=45)
        self.assertEqual(len(app.exception),0)
        self.assertGreaterEqual(len(app.warning),1)
        page_text=" ".join(str(x.value) for group in (
            app.error, app.caption, app.markdown, app.info, app.warning, app.success
        ) for x in group)
        self.assertIn("modo degradado seguro",page_text.lower())
        self.assertIn("RuntimeError",page_text)
        self.assertNotIn("sensitive foundation trace must not be shown",page_text)
        self.assertIn("não pôde ser confirmada",page_text.lower())

    def test_non_admin_console_fails_closed(self):
        script = r'''
from atlasquant_aion_admin import render_aion_admin_console
result=render_aion_admin_console({"role":"USER","username":"user.test"})
import streamlit as st
st.write("AION_ALLOWED",result["allowed"],result["reason"])
'''
        app=AppTest.from_string(script)
        app.run(timeout=30)
        self.assertEqual(len(app.exception),0)
        self.assertGreaterEqual(len(app.error),1)
        self.assertIn("bloqueado",str(app.error[0].value).lower())


if __name__=="__main__":
    unittest.main()
