"""A149 subprocess JSON/stdin transport — isolated synthetic LAB, NO NETWORK.

This CLI is NOT authenticated transport. Authentication attaches to signed
publication *contents*, and cannot establish who controls the local process.
NO external provider/Worker, no production command and no auto retry.
"""
import json
import sys

from aion_p0_a149_authenticated_cas_lab import (
    A149Denied, LAB_ONLY, AuthenticatedWitnessLAB,
    PublishRequest, SignedPublishRequest,
)

_FIELDS = {"operation", "directory", "ledger_id", "request", "signature_b64",
           "request_id", "fault"}


def _unique_pairs(pairs):
    out = {}
    for key, val in pairs:
        if key in out:
            raise A149Denied("duplicate_json_field")
        out[key] = val
    return out


def _decode():
    raw = sys.stdin.read(16385)
    if len(raw) > 16384:
        raise A149Denied("request_too_large")
    try:
        req = json.loads(raw, object_pairs_hook=_unique_pairs)
    except (ValueError, TypeError) as exc:
        raise A149Denied("invalid_request_json") from exc
    if type(req) is not dict or set(req) - _FIELDS:
        raise A149Denied("invalid_top_level_request")
    if not {"operation", "directory", "ledger_id"}.issubset(req):
        raise A149Denied("missing_request_fields")
    return req


def _receipt_json(envelope):
    if envelope is None:
        return None
    return {"receipt": {field: getattr(envelope.receipt, field)
                        for field in envelope.receipt.__dataclass_fields__},
            "signature_b64": envelope.signature_b64}


def execute():
    try:
        req = _decode()
        witness = AuthenticatedWitnessLAB(
            witness_dir=req["directory"], ledger_id=req["ledger_id"],
        )
        op = req["operation"]
        if op == "challenge":
            if set(req) != {"operation", "directory", "ledger_id"}:
                raise A149Denied("invalid_challenge_shape")
            result = {"challenge": witness.issue_challenge()}
        elif op == "head":
            if set(req) != {"operation", "directory", "ledger_id"}:
                raise A149Denied("invalid_head_shape")
            signed = witness.read_signed_head()
            result = {"head": {"ledger_id": signed.anchor.ledger_id,
                               "sequence": signed.anchor.sequence,
                               "history_digest": signed.anchor.history_digest,
                               "key_id": signed.key_id,
                               "signature_b64": signed.signature_b64}}
        elif op == "receipt":
            if set(req) != {"operation", "directory", "ledger_id", "request_id"}:
                raise A149Denied("invalid_receipt_shape")
            result = {"publication_receipt": _receipt_json(
                witness.read_receipt(req["request_id"])
            )}
        elif op == "publish":
            required = {"operation", "directory", "ledger_id", "request", "signature_b64"}
            if set(req) not in (required, required | {"fault"}):
                raise A149Denied("invalid_publish_shape")
            payload = req["request"]
            if (type(payload) is not dict
                    or set(payload) != set(PublishRequest.__dataclass_fields__)):
                raise A149Denied("invalid_signed_request_shape")
            signed = SignedPublishRequest(
                PublishRequest(**payload), req["signature_b64"],
            )
            result = {"publication_receipt": _receipt_json(
                witness.publish(envelope=signed, fault=req.get("fault"))
            )}
        else:
            raise A149Denied("unsupported_operation")
        print(json.dumps({"marker": LAB_ONLY, **result}, sort_keys=True), flush=True)
        return 0
    except (A149Denied, KeyError, TypeError, OSError, ValueError) as exc:
        print(json.dumps({"marker": LAB_ONLY, "error": str(exc)},
                         sort_keys=True), flush=True)
        return 2


if __name__ == "__main__":
    sys.exit(execute())
