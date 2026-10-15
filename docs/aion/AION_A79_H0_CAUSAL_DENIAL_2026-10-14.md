# A79 H0 — causal producer boundaries, not external authority

Base: A78 `977f4480f23aed3d9741ee8886bdcb756946adf5`, parent A76
`092eb60bd9b4f6f66035d1f71ee6ee8add9441cd`. A77 is a sibling on
A75 and is NOT integrated. All references below describe this immutable base.
Only a new test, LAB workflow and this report are proposed. No runtime fix is
claimed: the inspected effect boundaries already deny independently of claims.

## Three proofs that cannot replace one another

1. COMMITTED_EFFECT: independent authenticated producer/account testimony bound
   to the exact operation, actual durable effect and attempt. HTTP201, SENT,
   CONFIRMED DTO, self-hash and local ledger do not establish this.
2. NO_EFFECT_FENCED: authenticated terminal producer fence that also excludes
   late/asynchronous effects for the same attempt. 404, empty/no row, timeout,
   cancellation, policy revocation and local FAILED do not establish this.
3. F1/T1: independently custodied source identity/current head and durable
   monotonic history against rollback, including restore. It cannot prove the
   producer committed or fenced the business effect. No such root is enrolled.

All remain BLOCKED_EXTERNAL_PROOF_UNAVAILABLE; syntactic tests are not H0.

## Actual call graph / state and scope

`ExecutionOutbox(store, Scope)` -> `_ensure_schema` (outbox.py:108-173), local
SQLite only. Scope covers owner/tenant/workspace, not host/account/epoch.
`enqueue` (:237-412) validates bounded local policy references and authority
window; derives SHA idempotency from scope+intent/action/aggregate/payload and
budget fields; commits decision+PENDING together (or SAVEPOINT under Saga).
`grants_authority=False`. Different intent content collides rather than silently
changing an existing intent. No external operation is attempted by enqueue.

`claim_next` (:433-488) -> `release_expired_claims` (:414-431): local lease
CLAIMED, attempts increment. Expiration can make CLAIMED become RETRY; that
only permits another local claim, not another producer send. A45 permits only
aggregate ordinal1; predecessor deletion/forged local terminal cannot release
ordinal2+. Whole-database/ordinal rewriting is not detected independently.

`dispatch_claimed` (:575-732) reads scoped row; checks state/lease/worker/time;
`_authorization_gate` (:490-528) checks expiry, actor, tenant/workspace, policy,
approval reference and optional reauth. Budget and authorization callbacks are
local executable dependencies, never causal producer evidence. It rechecks
authorization/time and persisted lease/deadline, then uses scoped CAS to store
BLOCKED_PRODUCER. It raises INDEPENDENT_PRODUCER_NOT_ENROLLED before even
evaluating adapter.send. The old adapter/send/UNCERTAIN code after :736 is
unreachable today. A79 never enables or mocks that gate.

`reconcile` (:845-867) accepts only SENT/UNCERTAIN and immediately raises before
adapter.reconcile/property or authorization callback. UNKNOWN stays uncertain;
no retry, ledger insertion or compensation. Historical adapter statuses below
this raise are unreachable. `_confirm` (:557-573) always denies local positive
receipt admission. `effect_count` (:906) only counts mutable local rows; it
does not authenticate them. `get/list` return local projections, not testimony.

Saga: `enqueue_next` (saga.py:455) atomically binds planned step, intent and
budget. `sync_forward_outcome` (:534-563) rejects local CONFIRMED, FAILED,
REVOKED and BLOCKED_REAPPROVAL as independent effect/no-effect proof; later
local consistency/locked snapshot checks do not establish root custody.
`prepare_compensation` (:698-727) and `enqueue_next_compensation` (:765)
retain independent-proof denials. `sync_compensation_outcome` (:834-861)
rejects all effect admission before ledger/budget or Saga promotion. An undo
is another external operation needing new human/producer authorization.

## Receipt contracts and consumers inspected

`inspect_untrusted_receipt_shape` (producer precheck:60-132) accepts only exact
builtin primitive shapes and 14 bindings: owner,tenant,workspace,host,producer
issuer/account,action,intent digest,idempotency,attempt,epoch,witness sequence/
head,nonce. Counter bools and dynamic keys/values are rejected. A 128hex
claimed signature, future/past UTC timestamp or huge matching int can still
be syntactically matching, but EVERY authority boolean remains False. No
current-time freshness, cryptographic verification or external lookup occurs.
Search of versioned non-test Python found only this helper's definition/export,
not an Outbox admission caller. No helper output is connected to send/retry.

ActionReceipt `seal_action_receipt` (:100) and `validate_action_receipt` (:153)
use fingerprints, reference callbacks and context; result stays UNKNOWN,
authorization NONE, INFORMATION_ONLY or INVALID, digest_is_signature=False.
`seal_executor_receipt_envelope` (bridge:17) is an informational envelope,
external_persisted=False. Verifier callbacks are not enrolled independent
producer roots; do not use them to grant H0.

B2B `build_external_effect_outcome_receipt_contract` (:207) and
`build_real_receipt_authenticator_contract` (:143) are design builders. `_result`
forces FALSE_FIELDS False. Their design READY states specify requirements, not
authentication or actual provider reconciliation. Non-test search found their
definitions/export, not production Outbox callers. Other signature-related
modules found by broad search were not globally certified by this audit.

## Executable new evidence and honest limits

64 unique A79 tests:14 exact binding mismatches;16 primitive/forged positive or
negative claims;9 callback-result variants inaccessible behind hard stop;
10 recovery/restore/idempotency cases including four spawned processes on
PENDING and four on UNCERTAIN; contradictory positive/negative untrusted claims;
5 policy scope mismatches;7 Saga forward/compensation local-forgery denials;
first-enqueue rollback and concurrent reconcile/dispatch on UNCERTAIN.
All are NEGATIVE_CHARACTERIZATION, not RED->GREEN production fixes.

Fixtures use disposable SQLite only. RawSQL staging of UNCERTAIN/SENT/terminal
states and SQLite backup restoration are labelled inputs, not real crash or
provider evidence. Four spawned processes prove one local claim and no adapter
getter/send, not cross-host exactly-once. Reconcile/dispatch concurrency on
UNKNOWN stays denied. No untrusted adapter getter is invoked.

H0/H1 after first local rollback/no row remain indistinguishable without an
independent intent/attempt anchor; local enqueue can retry, but send is denied.
Restoring a pre-denial DB can restore CLAIMED and its attempts; rollback is NOT
detected. The hard stop denies again. A local effects row inserted by privileged
SQL can make effect_count nonzero: this is an explicit trust limit, not a
producer receipt. Original FIFO/Saga tests exercise these fixtures unchanged.

No crash after an actual producer send is reproduced because there is no
authorized send path. Provider outages, real terminal fence, two-host witness
custody and external account identity remain UNTESTED_REQUIRED_EXTERNAL.
No fresh V5 or A12/A16 original evidence; original45 remain unavailable.

## Required future independent trial (not executed)

Before any enabling change, owner must separately approve custodian/provider,
test account, exact cost/privacy and a bounded reversible operation. No price,
subscription or real provider choice is authorized here. Bind owner/tenant/
workspace/host,issuer/account,operation class,digest,idempotency,attempt,epoch,
nonce and signed previous/current witness head+sequence out of band.

Collect independently: durable pre-effect admission/CAS receipt, producer
COMMITTED_EFFECT or terminal NO_EFFECT_FENCED with late-effect exclusion,
signed current readback, freshness/revocation results and monotonic high-water
history. Keep records with a custodian outside the worker/SQLite/host domain;
local copies remain evidence caches only. Simulated keys cannot satisfy this.

Inject power/process/ACK loss before/after each durable transition; test two
hosts racing under fencing, lease expiry without resend, ABA, stale epochs,
revocation during readback, restored old host/witness snapshots, contradictory
positive/negative receipts and attempted undo. UNKNOWN/conflict must quarantine
without send/auto retry. Missing row/404 never proves terminal absence.
Acceptance requires zero duplicate effects, independent proof of commit OR
terminal exclusion of late effects, and independent recovery after restore.
Availability loss/custodian outage must remain explicit; no silent local bypass.

## Delivery gates

CI reports exact source HEAD, each OS, errors and callbacks. Original Outbox,
Saga, receipt/B2B tests run separately and may remain RED; no assertions changed.
Full Quality/Security NOT RUN for A79; previous counts are historical only.
No main/runtime branch, Core V1, Render/deploy, Worker code, A75/F1T1, provider
adapter or keys changed. No installation on the owner's Windows. No real
producer, network dispatch, witness, signature, account or spend. 0/6 P0;
20/20 first-install HARD NO-GO. Stop after A79, no autonomous next mission.
