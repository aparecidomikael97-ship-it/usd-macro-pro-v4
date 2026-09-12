from streamlit.testing.v1 import AppTest

# Executa o app sem navegador. O toggle da coleta automática fica ligado por padrão.
at = AppTest.from_file("usd_macro_pro_v4_cloud.py", default_timeout=120)
at.run()

if at.exception:
    msgs = []
    for exc in at.exception:
        try:
            msgs.append(str(exc.value))
        except Exception:
            msgs.append(str(exc))
    raise RuntimeError("Erros ao executar o app: " + " | ".join(msgs))

print("USD Macro Pro V8.6 executado em modo automático.")
