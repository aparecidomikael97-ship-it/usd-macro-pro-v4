"""Rooted owner signature + device registry + exact UI intent: CI-only trials."""
from __future__ import annotations

import base64
from copy import deepcopy
from dataclasses import replace
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from atlasquant_aion_owner_signed_key_registry_preflight_v1 import (
    SCHEMA as REG_SCHEMA, PURPOSE as REG_PURPOSE, root_signing_message,
)
from atlasquant_aion_trusted_owner_host_crypto_proof_v1 import (
    SCHEMA as PROOF_SCHEMA, PURPOSE as PROOF_PURPOSE,
    SQLiteOwnerNonceRegistry, signing_message,
)
from atlasquant_aion_owner_signed_intent_guard_v1 import (
    SCHEMA as INTENT_SCHEMA, PURPOSE as INTENT_PURPOSE,
    SCOPE_NAV, SCOPE_GREETING, signed_intent_message,
)
from atlasquant_aion_rooted_owner_signed_ui_preflight_v1 import (
    HostEvidence, plan_rooted_owner_greeting, request_rooted_owner_navigation,
)


def digest(raw: bytes) -> str:
    return "sha256:" + sha256(raw).hexdigest()


def pub(signer: Ed25519PrivateKey) -> bytes:
    return signer.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def raw_json(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


class RootedOwnerSignedUIIntegrationTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="aion-ci-rooted-")
        self.addCleanup(self.temp.cleanup)
        self.root = Ed25519PrivateKey.generate()
        self.owner = Ed25519PrivateKey.generate()
        self.successor = Ed25519PrivateKey.generate()
        self.now = 2000000000
        self.session_digest = digest(b"independently-authenticated-ci-session")
        self.device_digest = digest(b"independently-known-ci-desktop")
        self.mobile_digest = digest(b"independently-known-ci-mobile")
        self.nonces = SQLiteOwnerNonceRegistry(str(Path(self.temp.name)/"nonce.sqlite3"))
        self.host = HostEvidence(
            pinned_root_public_key=pub(self.root),
            pinned_root_fingerprint=digest(pub(self.root)),
            registry_id="owner-registry-ci",
            owner_subject="mikael",
            host_issuer="owner-host-ci",
            device_id="desktop-ci",
            device_binding_digest=self.device_digest,
            minimum_registry_epoch=1,
            session_binding_digest=self.session_digest,
            audience="atlasquant-ci",
            device_kind="DESKTOP",
            nonce_registry=self.nonces,
        )
        self.access = {
            "allowed": True, "mode": "AUTHENTICATED", "role": "ADMIN",
            "session": {
                "username": "mikael",
                "role": "ADMIN", "permissions": ["app:read", "aion:admin"],
                "credential_fingerprint": "ci-not-a-credential",
            },
        }
        self.registry = {
            "schema": REG_SCHEMA, "purpose": REG_PURPOSE,
            "registry_id": "owner-registry-ci", "owner_subject": "mikael",
            "host_issuer": "owner-host-ci",
            "epoch": 1, "issued_at": self.now - 500,
            "expires_at": self.now + 3600,
            "owner_keys": [{
                "key_id": "owner-key-1", "public_key_b64": b64(pub(self.owner)),
                "enrolled_epoch": 1, "revoked_epoch": None, "supersedes": None,
            }],
            "devices": [
                {
                    "device_id": "desktop-ci", "binding_digest": self.device_digest,
                    "enrolled_epoch": 1, "revoked_epoch": None,
                },
                {
                    "device_id": "mobile-ci", "binding_digest": self.mobile_digest,
                    "enrolled_epoch": 1, "revoked_epoch": None,
                },
            ],
        }

    def rotated(self):
        changed = deepcopy(self.registry)
        changed["epoch"] = 2
        changed["owner_keys"][0]["revoked_epoch"] = 2
        changed["owner_keys"].append({
            "key_id": "owner-key-2", "public_key_b64": b64(pub(self.successor)),
            "enrolled_epoch": 2, "revoked_epoch": None,
            "supersedes": "owner-key-1",
        })
        return changed

    def make_proof(self, *, signer=None, nonce="c" * 64,
                   subject="mikael", digest_device=None, digest_session=None,
                   issuer="owner-host-ci", audience="atlasquant-ci"):
        s = self.owner if signer is None else signer
        return {
            "schema": PROOF_SCHEMA, "purpose": PROOF_PURPOSE,
            "principal": "HUMAN_OWNER", "subject": subject,
            "issuer": issuer, "audience": audience,
            "session_binding_digest": self.session_digest if digest_session is None else digest_session,
            "device_binding_digest": self.device_digest if digest_device is None else digest_device,
            "key_fingerprint": digest(pub(s)), "nonce": nonce,
            "issued_at": self.now - 10, "expires_at": self.now + 100,
        }

    def make_intent(self, proof, *, text="AION, abre Trader",
                    scope=SCOPE_NAV, device="DESKTOP"):
        return {
            "schema": INTENT_SCHEMA, "purpose": INTENT_PURPOSE,
            "scope": scope, "command": text,
            "proof_digest": digest(signing_message(proof)),
            "session_binding_digest": proof["session_binding_digest"],
            "device_binding_digest": proof["device_binding_digest"],
            "device": device,
            "issuer": proof["issuer"], "audience": proof["audience"],
            "nonce": proof["nonce"], "issued_at": proof["issued_at"],
            "expires_at": proof["expires_at"],
        }

    def proof_sig(self, proof, signer=None):
        return b64((self.owner if signer is None else signer).sign(signing_message(proof)))

    def intent_sig(self, intent, signer=None):
        return b64((self.owner if signer is None else signer).sign(signed_intent_message(intent)))

    def reg_sig(self, registry, signer=None):
        return b64((self.root if signer is None else signer).sign(root_signing_message(registry)))

    def invoke(
        self, *, text="AION, abre Trader", registry=None, reg_sig=None,
        proof=None, proof_sig=None, intent=None, intent_sig=None,
        host=None, access=None, signer=None, kind="nav",
        now_epoch=None, state=None,
    ):
        s = self.owner if signer is None else signer
        reg = self.registry if registry is None else registry
        h = self.host if host is None else host
        p = self.make_proof(signer=s) if proof is None else proof
        command = "" if kind == "greeting" else text
        requested_scope = SCOPE_GREETING if kind == "greeting" else SCOPE_NAV
        signable_command = command if type(command) is str and len(command) <= 160 else "AION, abre Trader"
        intent_obj = self.make_intent(
            p, text=signable_command, scope=requested_scope,
            device=h.device_kind if isinstance(h, HostEvidence) else "DESKTOP",
        ) if intent is None else intent
        root_signature = self.reg_sig(reg) if reg_sig is None else reg_sig
        owner_signature = self.proof_sig(p, signer=s) if proof_sig is None else proof_sig
        intent_signature = self.intent_sig(intent_obj, signer=s) if intent_sig is None else intent_sig
        data = {} if state is None else state
        a = self.access if access is None else access
        now = self.now if now_epoch is None else now_epoch
        if kind == "greeting":
            result = plan_rooted_owner_greeting(
                a, raw_json(reg), root_signature, p, owner_signature,
                intent_obj, intent_signature, host=h, now_epoch=now,
                now=datetime(2026, 10, 8, 9, 0),
                timezone_name="America/Cuiaba",
            )
        else:
            result = request_rooted_owner_navigation(
                data, a, raw_json(reg), root_signature, p, owner_signature,
                intent_obj, intent_signature, host=h, now_epoch=now,
                text=text,
            )
        return data, result

    def blocked(self, state, r, reason=None):
        self.assertEqual(r["state"], "BLOCKED", r)
        if reason is not None:
            self.assertEqual(r["reason"], reason)
        self.assertFalse(r["navigation_requested"])
        self.assertFalse(r["root_signed_registry_verified"])
        self.assertFalse(r["owner_key_resolved"])
        self.assertFalse(r["device_enrolled"])
        self.assertFalse(r["production_authorized"])
        self.assertFalse(r["host_attached"])
        self.assertFalse(r["execution_confirmed"])
        self.assertFalse(r["external_action_authorized"])
        self.assertFalse(r["signed_intent_bound"])
        self.assertEqual(state, {})

    def test_valid_rooted_signed_trader_navigation_is_only_request(self):
        state, r = self.invoke()
        self.assertEqual(r["state"], "INTERNAL_NAVIGATION_REQUESTED", r)
        self.assertTrue(r["signed_intent_bound"])
        self.assertTrue(r["root_signed_registry_verified"])
        self.assertEqual(r["owner_key_id"], "owner-key-1")
        self.assertEqual(r["registry_epoch"], 1)
        self.assertEqual(r["target"], "trader")
        self.assertEqual(state["atlasquant_central_choice"], "trader")
        for field in ("navigation_confirmed", "execution_confirmed",
                      "external_action_authorized", "production_authorized",
                      "host_attached"):
            self.assertFalse(r[field])
        self.assertNotIn("resolved_owner_public_key", r)
        self.assertNotIn("owner_assertion", r)

    def test_valid_signed_greeting_is_display_only(self):
        _, r = self.invoke(kind="greeting")
        self.assertEqual(r["state"], "OWNER_ENTRY_READY", r)
        self.assertTrue(r["root_signed_registry_verified"])
        self.assertTrue(r["greeting_display_only"])
        self.assertFalse(r["greeting_spoken"])
        self.assertFalse(r["microphone_active"])
        self.assertFalse(r["production_authorized"])

    def test_greeting_cannot_reuse_nonce_for_navigation(self):
        _, greeting = self.invoke(kind="greeting")
        self.assertEqual(greeting["state"], "OWNER_ENTRY_READY")
        state, result = self.invoke()
        self.blocked(state, result, "SIGNED_OWNER_INTENT_OR_NAVIGATION_REJECTED")

    def test_navigation_replay_denied(self):
        self.assertEqual(self.invoke()[1]["state"], "INTERNAL_NAVIGATION_REQUESTED")
        state, r = self.invoke()
        self.blocked(state, r)

    def test_valid_new_nonce_after_previous_command(self):
        self.assertEqual(self.invoke()[1]["state"], "INTERNAL_NAVIGATION_REQUESTED")
        p = self.make_proof(nonce="d"*64)
        state, r = self.invoke(proof=p)
        self.assertEqual(r["state"], "INTERNAL_NAVIGATION_REQUESTED", r)

    def test_valid_mobile_uses_registered_mobile_digest(self):
        h = replace(self.host, device_id="mobile-ci",
                    device_binding_digest=self.mobile_digest, device_kind="MOBILE")
        p = self.make_proof(digest_device=self.mobile_digest)
        state, r = self.invoke(host=h, proof=p, text="AION, abre Investimentos")
        self.assertEqual(r["state"], "INTERNAL_NAVIGATION_REQUESTED", r)
        self.assertEqual(r["target"], "investimentos")
        self.assertFalse(r["navigation_confirmed"])

    def test_unregistered_device_denied_before_owner_nonce(self):
        h = replace(self.host, device_id="unknown", device_binding_digest=digest(b"unknown"))
        p = self.make_proof(digest_device=digest(b"unknown"))
        state, r = self.invoke(host=h, proof=p)
        self.blocked(state, r, "ROOT_SIGNED_REGISTRY_REQUIRED")
        self.assertEqual(r["registry_reason"], "DEVICE_NOT_ENROLLED_OR_REVOKED")
        self.assertEqual(self.invoke()[1]["state"], "INTERNAL_NAVIGATION_REQUESTED")

    def test_revoked_desktop_denied_even_with_legitimate_owner_signatures(self):
        reg = deepcopy(self.registry)
        reg["epoch"] = 2
        reg["devices"][0]["revoked_epoch"] = 2
        h = replace(self.host, minimum_registry_epoch=2)
        state, r = self.invoke(registry=reg, host=h)
        self.blocked(state, r, "ROOT_SIGNED_REGISTRY_REQUIRED")
        self.assertEqual(r["registry_reason"], "DEVICE_NOT_ENROLLED_OR_REVOKED")

    def test_revoked_mobile_denied_but_desktop_still_works(self):
        reg = deepcopy(self.registry)
        reg["epoch"] = 2
        reg["devices"][1]["revoked_epoch"] = 2
        mobile = replace(self.host, device_id="mobile-ci",
                         device_binding_digest=self.mobile_digest,
                         device_kind="MOBILE", minimum_registry_epoch=2)
        p = self.make_proof(digest_device=self.mobile_digest)
        state, result = self.invoke(registry=reg, host=mobile, proof=p)
        self.blocked(state, result)
        desktop = replace(self.host, minimum_registry_epoch=2)
        self.assertEqual(self.invoke(registry=reg, host=desktop)[1]["state"],
                         "INTERNAL_NAVIGATION_REQUESTED")

    def test_revoked_old_owner_key_cannot_sign_after_rotation(self):
        reg = self.rotated()
        host = replace(self.host, minimum_registry_epoch=2)
        state, r = self.invoke(registry=reg, host=host)
        self.blocked(state, r, "OWNER_PROOF_NOT_BOUND_TO_ROOTED_REGISTRY")

    def test_successor_key_works_when_root_signed_and_epoch_updated(self):
        reg = self.rotated()
        host = replace(self.host, minimum_registry_epoch=2)
        state, r = self.invoke(registry=reg, host=host, signer=self.successor)
        self.assertEqual(r["state"], "INTERNAL_NAVIGATION_REQUESTED", r)
        self.assertEqual(r["owner_key_id"], "owner-key-2")
        self.assertEqual(r["registry_epoch"], 2)

    def test_stale_registry_rollback_rejected(self):
        h = replace(self.host, minimum_registry_epoch=2)
        state, r = self.invoke(host=h)
        self.blocked(state, r, "ROOT_SIGNED_REGISTRY_REQUIRED")
        self.assertEqual(r["registry_reason"], "ROLLBACK_BELOW_TRUSTED_FLOOR")

    def test_attacker_root_cannot_be_self_pinned(self):
        attacker = Ed25519PrivateKey.generate()
        state, r = self.invoke(
            host=replace(self.host,pinned_root_public_key=pub(attacker)),
            reg_sig=self.reg_sig(self.registry,signer=attacker),
        )
        self.blocked(state, r, "ROOT_SIGNED_REGISTRY_REQUIRED")
        self.assertEqual(r["registry_reason"], "UNPINNED_REGISTRY_ROOT")

    def test_wrong_root_signature_blocks_navigation(self):
        attacker = Ed25519PrivateKey.generate()
        state, r = self.invoke(reg_sig=self.reg_sig(self.registry,signer=attacker))
        self.blocked(state, r, "ROOT_SIGNED_REGISTRY_REQUIRED")
        self.assertEqual(r["registry_reason"], "REGISTRY_SIGNATURE_INVALID")

    def test_changed_registry_without_resigning_fails(self):
        reg = deepcopy(self.registry)
        reg["devices"][1]["revoked_epoch"] = 1
        state, r = self.invoke(registry=reg,reg_sig=self.reg_sig(self.registry))
        self.blocked(state, r, "ROOT_SIGNED_REGISTRY_REQUIRED")

    def test_client_supplied_owner_public_key_fingerprint_denied(self):
        attacker = Ed25519PrivateKey.generate()
        p = self.make_proof(signer=attacker)
        state, r = self.invoke(proof=p, signer=attacker)
        self.blocked(state, r, "OWNER_PROOF_NOT_BOUND_TO_ROOTED_REGISTRY")

    def test_pinned_key_still_requires_authentic_owner_signature(self):
        attacker = Ed25519PrivateKey.generate()
        proof = self.make_proof()
        state, r = self.invoke(proof=proof,proof_sig=self.proof_sig(proof,signer=attacker))
        self.blocked(state, r, "SIGNED_OWNER_INTENT_OR_NAVIGATION_REJECTED")

    def test_pinned_key_still_requires_valid_intent_signature(self):
        attacker = Ed25519PrivateKey.generate()
        p = self.make_proof()
        i = self.make_intent(p)
        state, r = self.invoke(intent_sig=self.intent_sig(i,signer=attacker))
        self.blocked(state, r, "SIGNED_OWNER_INTENT_OR_NAVIGATION_REJECTED")

    def test_signed_command_swap_rejected(self):
        proof = self.make_proof()
        signed_trader_intent = self.make_intent(proof)
        state, r = self.invoke(text="AION, abre Investimentos", intent=signed_trader_intent)
        self.blocked(state, r, "SIGNED_OWNER_INTENT_OR_NAVIGATION_REJECTED")

    def test_greeting_scope_signature_not_usable_for_nav(self):
        p = self.make_proof()
        i = self.make_intent(p,scope=SCOPE_GREETING,text="")
        state, r = self.invoke(intent=i)
        self.blocked(state, r)

    def test_external_and_composite_commands_still_blocked(self):
        for n, cmd in enumerate((
            "AION abre Spotify", "AION abre WhatsApp",
            "AION abre ChatGPT", "AION, abre Trader e paga",
            "AION abre Trader; executa trade",
        )):
            with self.subTest(cmd=cmd):
                p = self.make_proof(nonce=f"{n+1:064x}")
                i = self.make_intent(p, text=cmd)
                state, r = self.invoke(text=cmd,proof=p,intent=i)
                self.blocked(state, r, "SIGNED_OWNER_INTENT_OR_NAVIGATION_REJECTED")

    def test_admin_delegate_denied(self):
        access = {**self.access, "session": {
            **self.access["session"], "username":"delegated-admin",
        }}
        state,r = self.invoke(access=access)
        self.blocked(state,r,"SIGNED_OWNER_INTENT_OR_NAVIGATION_REJECTED")

    def test_anonymous_access_denied(self):
        access = {**self.access, "allowed":False}
        state,r = self.invoke(access=access)
        self.blocked(state,r)

    def test_session_hash_mismatch_rejected(self):
        host = replace(self.host,session_binding_digest=digest(b"other"))
        state,r = self.invoke(host=host)
        self.blocked(state,r,"OWNER_PROOF_NOT_BOUND_TO_ROOTED_REGISTRY")

    def test_wrong_owner_subject_rejected(self):
        host = replace(self.host,owner_subject="delegated-admin")
        state,r = self.invoke(host=host)
        self.blocked(state,r,"ROOT_SIGNED_REGISTRY_REQUIRED")

    def test_wrong_host_issuer_rejected(self):
        host = replace(self.host,host_issuer="attacker")
        state,r = self.invoke(host=host)
        self.blocked(state,r,"ROOT_SIGNED_REGISTRY_REQUIRED")

    def test_wrong_audience_rejected(self):
        host = replace(self.host,audience="wrong-audience")
        state,r = self.invoke(host=host)
        self.blocked(state,r,"OWNER_PROOF_NOT_BOUND_TO_ROOTED_REGISTRY")

    def test_registry_expiration_rejected(self):
        state,r = self.invoke(now_epoch=self.now+4000)
        self.blocked(state,r,"ROOT_SIGNED_REGISTRY_REQUIRED")

    def test_intent_expired_but_registry_current_denied(self):
        state,r = self.invoke(now_epoch=self.now+150)
        self.blocked(state,r,"SIGNED_OWNER_INTENT_OR_NAVIGATION_REJECTED")

    def test_missing_nonce_registry_denied(self):
        h = replace(self.host,nonce_registry=None)
        state,r = self.invoke(host=h)
        self.blocked(state,r,"HOST_DURABLE_NONCE_STORE_REQUIRED")

    def test_unsupported_device_kind_denied(self):
        h = replace(self.host,device_kind="SERVER")
        state,r = self.invoke(host=h)
        self.blocked(state,r,"HOST_DEVICE_KIND_REQUIRED")

    def test_untrusted_host_evidence_type_denied(self):
        state,r = self.invoke(host={"owner_subject":"mikael"})
        self.blocked(state,r,"HOST_EVIDENCE_REQUIRED")

    def test_response_never_exposes_privileged_key_bytes(self):
        _,r=self.invoke()
        self.assertNotIn("resolved_owner_public_key",r)
        self.assertNotIn("pinned_root_public_key",r)
        self.assertNotIn("nonce_registry",r)
        self.assertFalse(r["production_authorized"])
        self.assertFalse(r["host_attached"])

    def test_valid_signed_root_does_not_skip_command_guard(self):
        p=self.make_proof()
        i=self.make_intent(p,text="AION, abre Negócios")
        state,r=self.invoke(proof=p,intent=i,text="AION, abre Trader")
        self.blocked(state,r)

    def test_rooted_host_only_accepts_mutable_session_state(self):
        from types import MappingProxyType
        state=MappingProxyType({})
        r=request_rooted_owner_navigation(
            state,self.access,raw_json(self.registry),self.reg_sig(self.registry),
            self.make_proof(), "", {}, "",host=self.host,now_epoch=self.now,
            text="AION, abre Trader",
        )
        self.assertEqual(r["state"],"BLOCKED")
        self.assertEqual(r["reason"],"TRUSTED_SESSION_STATE_REQUIRED")

    def test_bad_command_type_denied(self):
        for value in (None, 42, True, "", []):
            with self.subTest(value=value):
                state,r=self.invoke(text=value)
                self.blocked(state,r,"EXACT_SINGLE_COMMAND_REQUIRED")
