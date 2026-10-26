"""G107 synthetic read-only SQLite record inspection, not external custody."""
from contextlib import closing


def lookup_stored_reservation(custodian, effect_digest):
    with closing(custodian._connect()) as db:
        row = db.execute(
            "SELECT effect_digest,request_id,decision_sha256,owner_id,"
            "tenant_id,workspace_id,sequence FROM first_attempts "
            "WHERE effect_digest=?", (effect_digest,),
        ).fetchone()
    if row is None:
        return None
    columns = ("effect_digest", "idempotency_key", "decision_sha256",
               "owner_id", "tenant_id", "workspace_id", "sequence")
    return dict(zip(columns, row))
