"""TEST-ONLY entrypoint: run the unmodified actual app with a private CI UI probe.

This file is NEVER imported by production source and can start only under four
explicit synthetic CI flags. It patches ONE function in memory of this CI
process; no production code or Library route is added.
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for path in (str(ROOT), str(ROOT / "scripts")):
    if path not in sys.path:
        sys.path.insert(0, path)

from aion_library_ci_joint_host import require_synthetic, read_from_real_app_session

require_synthetic()

import atlasquant_aion_admin

_original_shell = atlasquant_aion_admin.render_library_shell
_original_gate = atlasquant_aion_admin.library_shell_gate


def _ci_gate_diagnostics(**kwargs):
    result = _original_gate(**kwargs)
    # Only constant policy reason/boolean; never session, username or DB details.
    print("AION_CI_GATE_REASON=" + str(result.get("reason")) +
          " VISIBLE=" + str(result.get("visible") is True), flush=True)
    return result


atlasquant_aion_admin.library_shell_gate = _ci_gate_diagnostics


def _ci_only_shell(st, *, gate):
    if not _original_shell(st, gate=gate):
        return False
    # The genuine AtlasQuant admin + shell authorization gate runs FIRST.
    # The test overlay never accepts selection or scope parameters from UI.
    try:
        result = read_from_real_app_session()
        st.caption("AION CI · metadados sintéticos validados em PostgreSQL")
        st.text("Estado sintético: " + result.state)
        st.text("Versão sintética: " + str(result.version))
        st.text("Integridade sintética: " + ("CONFIRMADA" if result.integrity_checked else "NEGADA"))
    except Exception as exc:
        # CI-only diagnostic prints exception CLASS NAMES only, never messages,
        # IDs, SQL, paths, session fields, tokens or document metadata.
        chain = []
        cursor = exc
        for _ in range(7):
            if cursor is None:
                break
            chain.append(type(cursor).__name__)
            cursor = cursor.__cause__
        print("AION_CI_READ_EXCEPTION_TYPES=" + ",".join(chain), flush=True)
        # Fixed finite stage codes, never raw tracebacks, SQL, user identity,
        # passwords, token values, document IDs, file paths or error messages.
        allowed = {
            "read_from_real_app_session", "read_selected", "read_preview",
            "_preflight", "_principal", "host_access", "roles_for",
            "_lookup_roles", "_identity", "inspect", "verify",
            "identity_envelope", "_new_handle", "_verify_handle",
        }
        trace_chain = []
        cursor = exc
        for _ in range(7):
            if cursor is None:
                break
            locations = []
            tb = cursor.__traceback__
            while tb is not None:
                name = tb.tb_frame.f_code.co_name
                if name in allowed:
                    locations.append(name)
                tb = tb.tb_next
            trace_chain.append(">".join(locations[-8:]) if locations else "UNKNOWN")
            cursor = cursor.__cause__
        print("AION_CI_DENIAL_STAGES=" + "|".join(trace_chain), flush=True)

        # Uniform browser response, regardless of internal cause.
        st.caption("Consulta sintética indisponível")
    # CI-only widget: clicking it causes the ordinary authenticated Streamlit
    # rerun. Never accepts document/scope/role args and is never in runtime.
    st.button("Revalidar metadados sintéticos (CI)",
              key="aion_ci_library_read_recheck")
    return True


atlasquant_aion_admin.render_library_shell = _ci_only_shell
runpy.run_path(str(ROOT / "usd_macro_pro_v4_cloud.py"), run_name="__main__")
