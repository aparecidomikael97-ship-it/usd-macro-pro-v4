"""A322 LAB — prepare and compare claimed out-of-band genesis pin handoffs.

Generates only PUBLIC manifest fingerprints. The same host creates every
synthetic receipt, so even matching custody copies cannot establish real
off-host control, independent first bootstrap, immutable high-water, or P0.
No network, secret keys, wallet/order/provider calls, Worker or deployment.
"""
from labs.a317_detached_signed_intent_anchor_lab import encode, sha
from labs.a319_offline_root_continuity_lab import _manifest_valid, IDENTIFIER

SCHEMA = "ATLASQUANT_AION_A322_GENESIS_HANDOFF_LAB_V1"
CARD_FIELDS = frozenset((
    "schema", "ceremony_id", "manifest_sha256", "root_generation",
    "incident_epoch", "high_water_sequence", "high_water_sha256",
    "root_key_sha256", "fingerprint", "decision",
))
COPY_FIELDS = frozenset((
    "card_sha256", "copy_id", "claimed_custodian_id",
    "claimed_admin_domain", "claimed_account_id", "claimed_device_id",
    "claimed_recovery_domain", "claimed_delivery_channel",
    "claimed_retained_at", "decision",
))
GENESIS_PROFILE = (
    "two_human_offline_custodians",
    "two_separately_administered_append_only_witnesses",
    "same_owner_cloud_or_local_copies",
)


def _valid_identifier(value):
    return type(value) is str and IDENTIFIER.fullmatch(value) is not None


def _nonnegative(value):
    return type(value) is int and value >= 0


def _fingerprint(full_hash):
    # Short visual check is for convenient manual comparison only.
    # Always verify the entire 256-bit digest programmatically.
    return "-".join(full_hash[i:i + 4] for i in range(0, 32, 4))


def generate_genesis_card(*, public_manifest, ceremony_id):
    """Produce a deterministic paper-friendly public reference, never a pin."""
    if not _manifest_valid(public_manifest, candidate=False):
        raise ValueError("A322 requires one strictly validated PUBLIC A319 root manifest")
    if not _valid_identifier(ceremony_id):
        raise ValueError("A322 ceremony id invalid")
    digest = sha(encode(public_manifest))
    roots_digest = sha(encode(public_manifest["roots"]))
    return {
        "schema": SCHEMA, "ceremony_id": ceremony_id,
        "manifest_sha256": digest,
        "root_generation": public_manifest["generation"],
        "incident_epoch": public_manifest["incident_epoch"],
        "high_water_sequence": public_manifest["high_water_sequence"],
        "high_water_sha256": public_manifest["high_water_sha256"],
        "root_key_sha256": roots_digest,
        "fingerprint": _fingerprint(digest),
        "decision": "HOLD_ONLY",
    }


def _card_valid(card):
    return (
        type(card) is dict and set(card) == CARD_FIELDS
        and card["schema"] == SCHEMA
        and _valid_identifier(card["ceremony_id"])
        and all(type(card[field]) is str and len(card[field]) == 64
                and all(c in "0123456789abcdef" for c in card[field])
                for field in (
                    "manifest_sha256", "high_water_sha256",
                    "root_key_sha256",
                ))
        and all(_nonnegative(card[field]) for field in (
            "root_generation", "incident_epoch", "high_water_sequence",
        ))
        and type(card["fingerprint"]) is str
        and card["fingerprint"] == _fingerprint(card["manifest_sha256"])
        and card["decision"] == "HOLD_ONLY"
    )


def _copy_valid(copy):
    return (
        type(copy) is dict and set(copy) == COPY_FIELDS
        and type(copy["card_sha256"]) is str
        and len(copy["card_sha256"]) == 64
        and all(c in "0123456789abcdef" for c in copy["card_sha256"])
        and all(_valid_identifier(copy[field]) for field in (
            "copy_id", "claimed_custodian_id",
            "claimed_admin_domain", "claimed_account_id",
            "claimed_device_id", "claimed_recovery_domain",
            "claimed_delivery_channel",
        ))
        and _nonnegative(copy["claimed_retained_at"])
        and copy["decision"] == "OBSERVED_ONLY"
    )


def hold(status, issues, *, matched=0, topology_consistent=False):
    return {
        "schema": SCHEMA, "status": status,
        "issues": sorted(set(issues)), "matched_copies": matched,
        "two_claimed_separate_custody_paths_consistent": topology_consistent,
        "full_manifest_digest_compared": status == "LAB_HANDOFF_COPIES_MATCH_UNATTESTED",
        "research_only": True, "synthetic_only": True,
        "bootstrap_independently_authenticated": False,
        "actual_custodian_identities_authenticated": False,
        "actual_admin_domain_separation_verified": False,
        "out_of_band_delivery_verified": False,
        "off_host_immutable_high_water_verified": False,
        "real_external_source_consulted": False,
        "external_provider_ack_verified": False,
        "automatic_effect_reconciliation_verified": False,
        "can_authorize_real_effect": False, "can_resume": False,
        "can_resend": False, "can_auto_retry": False,
        "automatic_retries": 0, "zero_auto_resend": True,
        "hard_no_go": True, "p0_homologated": 0,
        "no_worker_deploy_provider_orders": True,
        "new_paid_services": False,
    }


def verify_declared_genesis_handoff(
    *, public_manifest, genesis_card, custody_copies,
):
    """Detect mismatching receipts and declared shared failure domains.

    Names of admins, accounts, devices and channels are still text the host
    itself could fabricate; the result NEVER authenticates independence.
    """
    if not _manifest_valid(public_manifest, candidate=False):
        return hold("LAB_GENESIS_HANDOFF_VETO", ["ROOT_MANIFEST_NOT_CANONICAL"])
    if not _card_valid(genesis_card):
        return hold("LAB_GENESIS_HANDOFF_VETO", ["GENESIS_CARD_NOT_CANONICAL"])
    if (
        type(custody_copies) not in (list, tuple)
        or len(custody_copies) != 2
    ):
        return hold("LAB_GENESIS_HANDOFF_VETO", ["TWO_CUSTODY_COPIES_REQUIRED"])
    expected = generate_genesis_card(
        public_manifest=public_manifest,
        ceremony_id=genesis_card["ceremony_id"],
    )
    issues = []
    if genesis_card != expected:
        issues.append("CARD_NOT_BOUND_TO_CURRENT_MANIFEST")
    canonical_digest = sha(encode(genesis_card))
    valid = []
    for item in custody_copies:
        if not _copy_valid(item):
            issues.append("CUSTODY_COPY_SHAPE_INVALID")
        else:
            valid.append(item)
            if item["card_sha256"] != canonical_digest:
                issues.append("RETAINED_COPY_DIGEST_MISMATCH")
    if len(valid) == 2:
        pairs = (
            ("copy_id", "COPY_ID_REUSED"),
            ("claimed_custodian_id", "CUSTODIAN_ID_REUSED"),
            ("claimed_admin_domain", "ADMIN_DOMAIN_REUSED"),
            ("claimed_account_id", "ACCOUNT_ID_REUSED"),
            ("claimed_device_id", "DEVICE_ID_REUSED"),
            ("claimed_recovery_domain", "RECOVERY_DOMAIN_REUSED"),
            ("claimed_delivery_channel", "DELIVERY_CHANNEL_REUSED"),
        )
        for field, issue in pairs:
            if valid[0][field] == valid[1][field]:
                issues.append(issue)
    if issues:
        return hold("LAB_GENESIS_HANDOFF_VETO", issues, matched=len(valid))
    return hold(
        "LAB_HANDOFF_COPIES_MATCH_UNATTESTED", [],
        matched=2, topology_consistent=True,
    )


def assess_low_cost_custody_profile(profile):
    """Budget/operability comparison without prices or security claims."""
    if type(profile) is not str or profile not in GENESIS_PROFILE:
        return {
            **hold("LAB_PROFILE_UNKNOWN_VETO", ["PROFILE_UNKNOWN"]),
            "recurring_vendor_required_by_design": None,
            "can_support_unattended_effect_approval": False,
            "recommended_now": False,
            "profile": None,
        }
    if profile == "two_human_offline_custodians":
        status = "LAB_PRACTICAL_OFFLINE_PILOT_NO_AUTOMATION"
        issues = ["MANUAL_ONLY_CANNOT_PROVE_PER_EFFECT_EXTERNAL_CHECK"]
        recurring, suggested = False, True
    elif profile == "two_separately_administered_append_only_witnesses":
        status = "LAB_ARCHITECTURE_CANDIDATE_NOT_PROVISIONED"
        issues = [
            "SEPARATE_ADMINISTRATORS_NOT_PROVEN",
            "APPEND_ONLY_ENFORCEMENT_NOT_TESTED",
            "EXTERNAL_ACK_NOT_INTEGRATED",
            "FUTURE_PRICING_AND_CONTROL_REVIEW_REQUIRED",
        ]
        recurring, suggested = None, False
    else:
        status = "LAB_SHARED_CONTROL_FAILURE_DOMAIN_VETO"
        issues = ["SAME_OWNER_CAN_REPLACE_PIN_AND_HISTORY"]
        recurring, suggested = None, False
    return {
        **hold(status, issues), "profile": profile,
        "recurring_vendor_required_by_design": recurring,
        "can_support_unattended_effect_approval": False,
        "recommended_now": suggested,
    }


__all__ = [
    "SCHEMA", "CARD_FIELDS", "COPY_FIELDS", "GENESIS_PROFILE",
    "generate_genesis_card", "verify_declared_genesis_handoff",
    "assess_low_cost_custody_profile",
]
