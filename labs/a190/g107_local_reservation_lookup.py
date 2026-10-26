"""G107 synthetic read-only SQLite record inspection, not external custody."""
from contextlib import closing
import sqlite3

from aion_chat.separate_custody_a181_lab import CustodyUnavailable


def lookup_stored_reservation(custodian, effect_digest):
    # Native sqlite3 failure must never be promoted to an approval. Convert
    # storage errors to the same fail-closed contract as absent custody.
    try:
        with closing(custodian._connect()) as db:
            row = db.execute(
                "SELECT effect_digest,request_id,decision_sha256,owner_id,"
                "tenant_id,workspace_id,sequence FROM first_attempts "
                "WHERE effect_digest=?", (effect_digest,),
            ).fetchone()
    except (sqlite3.Error, OSError) as exc:
        raise CustodyUnavailable("G109_EXACT_RESERVATION_LOOKUP_UNAVAILABLE") from exc
    if row is None:
        return None
    columns = ("effect_digest", "idempotency_key", "decision_sha256",
               "owner_id", "tenant_id", "workspace_id", "sequence")
    return dict(zip(columns, row))
