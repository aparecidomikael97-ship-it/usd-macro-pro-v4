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
        self.assertGreaterEqual(len(app.button),4)
        self.assertGreaterEqual(len(app.metric),8)

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
