"""AION Chat: disposable SQLite nonce + worst-case budget HOLD reference V1.

This deliberately NEVER authorizes a provider, owner identity or any payment.
A valid signed payload from #1121 is mathematical only, not enrolled trust.
The SQLite ledger can be restored together with the chat DB: this code offers
NO hardware antirollback, no remote witness, no FX/billing settlement, and no
real security against a privileged operator overwriting the reference DB.

No provider calls, network connections, process creation, key generation,
real TPM, trusted-clock or any production-database integration.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Mapping

from aion_chat.models import Scope
from atlasquant_aion_chat_signed_turn_review_v1 import (
    CANDIDATE, review_signed_pending_model_turn,
)

SCHEMA = "ATLASQUANT_AION_CHAT_REFERENCE_NONCE_BUDGET_HOLD_V1"
REFERENCE_HELD = "REFERENCE_HELD_UNTRUSTED"
REFERENCE_REPLAY = "REFERENCE_ALREADY_HELD_UNTRUSTED"
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_PERIOD = re.compile(r"20[0-9]{2}-(0[1-9]|1[0-2])\Z")
_FALSE = {
    "signed_owner_identity_enrolled": False,
    "trusted_human_owner_consent": False,
    "separate_approval_ceremony_verified": False,
    "independent_witness_protected": False,
    "hardware_antirollback_verified": False,
    "trusted_clock_verified": False,
    "monthly_budget_production_enforced": False,
    "current_pricing_verified": False,
    "real_usd_brl_fx_verified": False,
    "real_budget_reserved": False,
    "real_billing_authorized": False,
    "provider_called": False,
    "network_called": False,
    "model_invocation_authorized": False,
    "model_invocation_executed": False,
    "model_output_generated": False,
    "model_output_persisted": False,
    "external_action_executed": False,
    "production_store_activated": False,
    "installer_authorized": False,
    "safe_to_resume": False,
}


def _strict_int(value: Any, low: int, high: int) -> bool:
    return type(value) is int and low <= value <= high


def _sha_str(value: Any) -> str:
    if type(value) is not str:
        raise ValueError("invalid canonical text")
    return sha256(value.encode("utf-8")).hexdigest()


def _pin_digest(pin: Mapping[str, Any]) -> str:
    if (type(pin) is not dict or set(pin) != {"key_id", "public_key_hex"}
        or type(pin["key_id"]) is not str or not pin["key_id"]
        or type(pin["public_key_hex"]) is not str
        or not _HEX64.fullmatch(pin["public_key_hex"])):
        raise ValueError("host public pin is not an exact input")
    return sha256(json.dumps(
        pin, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")).hexdigest()


def _result(state: str, reason: str, *, nonce: str = "",
            digest: str = "", amount: int = 0,
            held_total: int = 0) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": state, "reason": reason,
        "nonce_hex": nonce if state in {REFERENCE_HELD,REFERENCE_REPLAY} else "",
        "signed_intent_sha256": digest if state in {REFERENCE_HELD,REFERENCE_REPLAY} else "",
        "reference_hold_micro_usd": amount if state in {REFERENCE_HELD,REFERENCE_REPLAY} else 0,
        "reference_total_held_micro_usd": held_total if state in {REFERENCE_HELD,REFERENCE_REPLAY} else 0,
        "single_use_inside_one_sqlite_reference": state in {REFERENCE_HELD,REFERENCE_REPLAY},
        "reference_store_only": True,
        "per_turn_external_execution_authority": False,
        "no_automatic_refunds_or_period_rollover": True,
        **_FALSE,
    }


class ReferenceNonceBudgetLedger:
    """One immutable-config sqlite file, serialized holds (no actual spending).

    Not a safe independent trust anchor. The creator controls path, config,
    public pin and database bytes. NEVER use its decision to set the paid
    provider's request_approved boolean. No automatic ledger rollover.
    """

    def __init__(
        self, path: str | Path, *, scope: Scope,
        period_id: str, policy_generation: int,
        owner_public_pin: Mapping[str, Any], limit_micro_usd: int,
    ) -> None:
        if not isinstance(scope, Scope):
            raise TypeError("Scope required")
        if type(period_id) is not str or not _PERIOD.fullmatch(period_id):
            raise ValueError("host supplied reference period invalid")
        if not _strict_int(policy_generation, 1, 2**31-1):
            raise ValueError("policy generation invalid")
        if not _strict_int(limit_micro_usd, 1, 2_000_000_000):
            raise ValueError("reference limit invalid")
        pin_digest = _pin_digest(owner_public_pin)
        self.scope = scope
        self.period_id = period_id
        self.policy_generation = policy_generation
        self.limit_micro_usd = limit_micro_usd
        self.pin_digest = pin_digest
        # Local path is supplied by the disposable caller. This is not a
        # remote service, privileged installation, key vault or owner host.
        self.db = sqlite3.connect(str(path), timeout=5, isolation_level=None)
        try:
            self.db.row_factory = sqlite3.Row
            self.db.execute("PRAGMA busy_timeout=5000")
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS reference_config (
                  singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                  owner_id TEXT NOT NULL, tenant_id TEXT NOT NULL,
                  workspace_id TEXT NOT NULL, period_id TEXT NOT NULL,
                  policy_generation INTEGER NOT NULL,
                  pin_sha256 TEXT NOT NULL, limit_micro_usd INTEGER NOT NULL,
                  held_total_micro_usd INTEGER NOT NULL DEFAULT 0,
                  hold_count INTEGER NOT NULL DEFAULT 0
                )
            """)
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS reference_holds (
                  nonce_hex TEXT PRIMARY KEY,
                  scope_owner TEXT NOT NULL, scope_tenant TEXT NOT NULL,
                  scope_workspace TEXT NOT NULL, conversation_id TEXT NOT NULL,
                  message_id TEXT NOT NULL, signed_intent_sha256 TEXT NOT NULL UNIQUE,
                  amount_micro_usd INTEGER NOT NULL CHECK(amount_micro_usd>0),
                  policy_generation INTEGER NOT NULL, period_id TEXT NOT NULL,
                  UNIQUE(scope_owner,scope_tenant,scope_workspace,conversation_id,message_id)
                )
            """)
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute(
                "SELECT * FROM reference_config WHERE singleton=1"
            ).fetchone()
            if row is None:
                self.db.execute("""
                    INSERT INTO reference_config (
                      singleton,owner_id,tenant_id,workspace_id,period_id,
                      policy_generation,pin_sha256,limit_micro_usd
                    ) VALUES (1,?,?,?,?,?,?,?)
                """, (scope.owner_id,scope.tenant_id,scope.workspace_id,
                      period_id,policy_generation,pin_digest,limit_micro_usd))
            else:
                self._verify_config(row)
            self._verify_internal_consistency()
            self.db.commit()
        except Exception:
            self.db.rollback()
            self.db.close()
            raise

    def _verify_config(self, row: sqlite3.Row) -> None:
        expected = (
            self.scope.owner_id,self.scope.tenant_id,self.scope.workspace_id,
            self.period_id,self.policy_generation,self.pin_digest,self.limit_micro_usd,
        )
        observed = tuple(row[k] for k in (
            "owner_id","tenant_id","workspace_id","period_id",
            "policy_generation","pin_sha256","limit_micro_usd",
        ))
        if observed != expected:
            raise ValueError("reference ledger config/pin mismatch; NO reset")

    def _verify_internal_consistency(self) -> sqlite3.Row:
        row = self.db.execute(
            "SELECT * FROM reference_config WHERE singleton=1"
        ).fetchone()
        if row is None:
            raise ValueError("reference config missing")
        self._verify_config(row)
        if self.db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("reference database integrity failure")
        sums = self.db.execute(
            "SELECT count(*) AS n,coalesce(sum(amount_micro_usd),0) AS total FROM reference_holds"
        ).fetchone()
        if (type(row["held_total_micro_usd"]) is not int
            or type(row["hold_count"]) is not int
            or sums["n"] != row["hold_count"]
            or sums["total"] != row["held_total_micro_usd"]
            or not 0 <= row["held_total_micro_usd"] <= self.limit_micro_usd):
            raise ValueError("reference ledger totals inconsistent")
        return row

    def hold_reference_only(
        self, chat_store: Any, access: Mapping[str, Any] | None,
        *,
        conversation_id: str, message_id: str, final_prompt: str,
        envelope: Any, host_public_pin: Any,
        host_quote_micro_usd: Any,
    ) -> dict[str, Any]:
        """Reserve at most one reference hold per nonce AND pending message.

        Recomputes #1121 mathematical review, doesn't accept a supplied
        'verified' flag. Holds the entire SIGNED maximum, not a low quote.
        A repeated request can observe its old hold, never recreate it.
        """
        if (not _strict_int(host_quote_micro_usd,1,2_000_000_000)
            or _pin_digest(host_public_pin) != self.pin_digest):
            return _result("BLOCKED","TRUSTED_REFERENCE_PIN_OR_QUOTE_INVALID")
        review = review_signed_pending_model_turn(
            chat_store,self.scope,access,
            conversation_id=conversation_id,message_id=message_id,
            final_prompt=final_prompt,envelope=envelope,
            host_public_pin=host_public_pin,
            expected_policy_generation=self.policy_generation,
        )
        if review["state"] != CANDIDATE:
            return _result("BLOCKED","SIGNED_TURN_OR_STORED_MESSAGE_NOT_VALIDATED")
        payload = envelope["payload"]
        signed_cap = payload["max_cost_micro_usd"]
        if host_quote_micro_usd > signed_cap:
            return _result("BLOCKED","HOST_QUOTE_EXCEEDS_SIGNED_CAP")
        nonce = payload["nonce_hex"]
        intent = review["signed_payload_sha256"]
        try:
            self.db.execute("BEGIN IMMEDIATE")
            config = self._verify_internal_consistency()
            old = self.db.execute(
                "SELECT * FROM reference_holds WHERE nonce_hex=?", (nonce,)
            ).fetchone()
            if old is not None:
                if (old["signed_intent_sha256"] == intent
                    and old["conversation_id"] == conversation_id
                    and old["message_id"] == message_id
                    and old["amount_micro_usd"] == signed_cap):
                    result = _result(
                        REFERENCE_REPLAY,"SAME_UNTRUSTED_HOLD_READ_ONLY",
                        nonce=nonce,digest=intent,amount=signed_cap,
                        held_total=config["held_total_micro_usd"],
                    )
                else:
                    result = _result("BLOCKED","NONCE_ALREADY_BOUND_DIFFERENTLY")
            else:
                message_old = self.db.execute(
                    """SELECT nonce_hex FROM reference_holds
                       WHERE scope_owner=? AND scope_tenant=? AND scope_workspace=?
                         AND conversation_id=? AND message_id=?""",
                    (self.scope.owner_id,self.scope.tenant_id,
                     self.scope.workspace_id,conversation_id,message_id),
                ).fetchone()
                if message_old is not None:
                    result = _result("BLOCKED","MESSAGE_ALREADY_HAS_REFERENCE_HOLD")
                elif self.db.execute(
                    "SELECT 1 FROM reference_holds WHERE signed_intent_sha256=?", (intent,)
                ).fetchone() is not None:
                    result = _result("BLOCKED","SIGNED_INTENT_REPLAY")
                elif config["held_total_micro_usd"] + signed_cap > self.limit_micro_usd:
                    result = _result("BLOCKED","REFERENCE_BUDGET_EXCEEDED")
                else:
                    self.db.execute("""
                      INSERT INTO reference_holds(
                        nonce_hex,scope_owner,scope_tenant,scope_workspace,
                        conversation_id,message_id,signed_intent_sha256,
                        amount_micro_usd,policy_generation,period_id
                      ) VALUES (?,?,?,?,?,?,?,?,?,?)
                    """, (
                        nonce,self.scope.owner_id,self.scope.tenant_id,
                        self.scope.workspace_id,conversation_id,message_id,
                        intent,signed_cap,self.policy_generation,self.period_id,
                    ))
                    self.db.execute("""
                       UPDATE reference_config
                          SET held_total_micro_usd=held_total_micro_usd+?,
                              hold_count=hold_count+1 WHERE singleton=1
                    """,(signed_cap,))
                    self._verify_internal_consistency()
                    result = _result(
                        REFERENCE_HELD,"SIMULATED_NONCE_AND_MAX_COST_HOLD_ONLY",
                        nonce=nonce,digest=intent,amount=signed_cap,
                        held_total=config["held_total_micro_usd"]+signed_cap,
                    )
            self.db.commit()
            return result
        except (sqlite3.DatabaseError,ValueError,TypeError,OverflowError):
            self.db.rollback()
            return _result("BLOCKED","REFERENCE_STORAGE_UNAVAILABLE_OR_INCONSISTENT")

    def reference_snapshot(self) -> dict[str, Any]:
        try:
            config = self._verify_internal_consistency()
            return {
                "schema":SCHEMA,
                "held_micro_usd":config["held_total_micro_usd"],
                "hold_count":config["hold_count"],
                "max_micro_usd":self.limit_micro_usd,
                "period_id":self.period_id,
                **_FALSE,
            }
        except (sqlite3.DatabaseError,ValueError):
            return _result("BLOCKED","REFERENCE_STORAGE_UNAVAILABLE_OR_INCONSISTENT")

    def close(self) -> None:
        self.db.close()


__all__ = [
    "SCHEMA","REFERENCE_HELD","REFERENCE_REPLAY",
    "ReferenceNonceBudgetLedger",
]
