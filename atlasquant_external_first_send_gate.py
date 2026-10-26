"""G75 LAB ONLY: no trusted independent first-send custody is provisioned.

Approval, configuration, budgets and caller-supplied transports are not custody.
There is deliberately no configuration switch or callback to authorize a send.
This containment gate does not establish P0 closure.
"""

G75_EXTERNAL_FIRST_SEND_AUTHORITY_UNAVAILABLE = "G75_EXTERNAL_FIRST_SEND_AUTHORITY_UNAVAILABLE"


def require_external_first_send_authority() -> None:
    """Always deny until trusted external custody is implemented and reviewed."""
    raise RuntimeError(G75_EXTERNAL_FIRST_SEND_AUTHORITY_UNAVAILABLE)
