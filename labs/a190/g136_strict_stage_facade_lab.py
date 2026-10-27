"""G136 controlled staging FACADE — isolated laboratory contract, NOT production.

Direct facade calls cannot skip G135 synthetic original identity and G134
separate-process LOCAL reservation. The REAL ExecutionOutbox still permits
direct enqueue and its SQLite connection remains reachable to the same host;
this is a test demonstrating a future mandatory interface shape, NOT a P0
enforcement boundary. No adapter, network, Worker, external SEND or authority.

Single-use facade: on any authenticated proof attempt we refuse all automatic
retries, even if subprocess acknowledgement or local stage outcome is uncertain.
"""
from copy import deepcopy
from pathlib import Path
import re
import subprocess
import sys
from threading import Lock

from aion_chat.models import Scope
from atlasquant_aion_execution_outbox import ExecutionOutbox
from labs.a190.g135_pinned_original_claim_lab import PinnedOriginalClaimLab
from labs.a190.g134_process_custody_lab import ADMITTED

_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")

DENY_IDENTITY = "DENY_G136_UNVERIFIED_ORIGINAL_NO_STAGE"
DENY_SCOPE = "DENY_G136_UNTRUSTED_SCOPE_NO_STAGE"
DENY_REF = "DENY_G136_INVALID_REFERENCE_NO_STAGE"
DENY_USED = "DENY_G136_SINGLE_USE_UNCERTAIN_NO_AUTO_RETRY"
DENY_UNCERTAIN = "DENY_G136_CUSTODIAN_UNCERTAIN_NO_AUTO_RETRY"
DENY_OUTBOX = "DENY_G136_OUTBOX_STAGE_UNCERTAIN_NO_AUTO_RETRY"
STAGED = "G136_LAB_STAGE_ONLY_NOT_AUTHORITY_NO_SEND"


class G136StrictStagingFacadeLab:
    """Narrow caller-facing LAB-only API. No arbitrary Outbox kwargs exposed."""

    def __init__(self, *, outbox: ExecutionOutbox, claim: PinnedOriginalClaimLab,
                 custody_path: Path):
        if type(outbox) is not ExecutionOutbox:
            raise TypeError("G136_REAL_EXECUTION_OUTBOX_REQUIRED")
        if type(claim) is not PinnedOriginalClaimLab:
            raise TypeError("G136_PINNED_LAB_CLAIM_REQUIRED")
        if not isinstance(custody_path, Path):
            raise TypeError("G136_EXPLICIT_CUSTODY_PATH_REQUIRED")
        if not isinstance(outbox.scope, Scope):
            raise TypeError("G136_TRUSTED_SCOPE_REQUIRED")
        self._outbox = outbox  # NOT a security enclave; Python caller can bypass!
        self._claim = claim
        self._custody_path = custody_path
        self._lock = Lock()
        self._used = False

    def stage(self, *, claimed_original, economic_effect, evidence_query,
              technical_ref):
        """Strict LAB staging interface; result never authorizes actual effect."""
        with self._lock:
            if self._used:
                return DENY_USED, None
            if type(technical_ref) is not str or not _TOKEN.fullmatch(technical_ref):
                return DENY_REF, None
            approved = self._claim.inspect(
                claimed_event=deepcopy(claimed_original),
                proposed_economic_effect=deepcopy(economic_effect),
                evidence_query=evidence_query,
            )
            if approved is None:
                return DENY_IDENTITY, None
            # From this point the outcome could be uncertain. NO second attempt.
            self._used = True
            scope = self._outbox.scope
            if (approved["owner_id"], approved["tenant_id"],
                    approved["workspace_id"]) != (
                    scope.owner_id, scope.tenant_id, scope.workspace_id):
                return DENY_SCOPE, None

            try:
                command = [
                    sys.executable, "-B", "-m", "labs.a190.g134_process_custody_lab",
                    "reserve", str(self._custody_path),
                    approved["tenant_id"], approved["event_id"],
                    approved["original_sha256"], technical_ref,
                ]
                response = subprocess.run(
                    command, capture_output=True, text=True,
                    timeout=12, check=True,
                )
                # stdout must match *exactly* one ACK; never accept a substring.
                if response.stdout.strip() != ADMITTED or response.stderr:
                    return DENY_UNCERTAIN, None
            except (OSError, subprocess.SubprocessError, UnicodeError):
                return DENY_UNCERTAIN, None
            # This is a non-atomic two-storage stage. On failure, custody may
            # already be committed: never retry automatically.
            try:
                effect = deepcopy(economic_effect)
                staged = self._outbox.enqueue(
                    intent_ref=technical_ref,
                    action=effect["action"],
                    payload={"business_event_id": approved["event_id"], **effect},
                    semantic_event_id_lab=approved["event_id"],
                    aggregate_key="g136-lab-economic-stage",
                    policy_version="LAB-G136-NO-REAL-AUTHORITY",
                    authorization_ref="SYNTHETIC-A183-NOT-AUTHENTICATED",
                    created_at="2026-10-27T12:00:00+00:00",
                    valid_until="2026-10-27T12:05:00+00:00",
                )
                if staged["enqueue_state"] != "ENQUEUED":
                    return DENY_OUTBOX, None
                return STAGED, staged
            except Exception:
                return DENY_OUTBOX, None


__all__ = [
    "G136StrictStagingFacadeLab", "DENY_IDENTITY", "DENY_SCOPE",
    "DENY_REF", "DENY_USED", "DENY_UNCERTAIN", "DENY_OUTBOX", "STAGED",
]
