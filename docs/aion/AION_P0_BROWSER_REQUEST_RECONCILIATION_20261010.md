# AION P0 — Durable browser request binding and local reconciliation

Base: integrated Draft #1196, HEAD 6088380f043ef546b0eb74d69c79b6f5d89d778f. #1195 e0e249db64c1bef32ff47f0048a9900542dd144a and #1197 diagnostic 51456ee6629348fbc3534511a942b40daa5ee8b6 were read; none of those branches was modified. Core V1, native aion_chat/store.py, staged_store.py and host lifecycle implementation remain unchanged.

## Proven cause and scope
CRITICAL local integrity/correlation gap: browser request_id lived only in a Streamlit set. After reset, continue_product_read_turn recomputed turn_index from the now increased message_count, so one logical browser request obtained new user/assistant IDs. #1197 independently demonstrated 2→4 on Windows/Linux, including real COMMIT then injected native close error.
The #1195 close error correctly reports uncertainty. It is not repaired by hiding the exception, relaxing SQLite thread checks, trusting absence of an exception, or retrying append.

## Minimal application correction
A chat_browser_requests correlation table in the EXISTING staging database binds owner/tenant/workspace/request_id, original/resolved conversation, canonical input digest, credential-context digest, immutable turn_index, turn_id and exact expected message pair.
- Reserve before the existing READ/SEARCH flow. Unique scoped primary key plus BEGIN IMMEDIATE produces one fresh first-attempt permit, not an execution/human approval. New conversation creation and request reservation share one transaction.
- Repeats check the durable row before context resume/tool execution or message writes. Conflict is rejected even if the Streamlit set contains the request.
- A narrowly injected before_append hook persists the verified expected pair BEFORE either append; message objects/timestamps are constructed once. This binds browser identity into message metadata without changing Core receipt or authority semantics.
- Independent mode=ro/query_only connection reads the scoped conversation and both exact rows, roles, IDs, full privacy-normalized payload/metadata/provenance, sequence consistency and bound turn. quick_check/foreign-key validation are required.
- Confirming the correlation state rechecks the same pair under SQLite's write lock; only the request row changes. Replay NEVER appends missing rows or reruns the local tools.
- Complete matching pair returns LOCAL_PAIR_RECONCILED, not CONFIRMED_SUCCESS. Partial/absent/conflicting/unknown binding remains BLOCKED_RECONCILIATION_REQUIRED; retry_authorized=false. No inferred approval, memory promotion or external persistence.
- Pending request also blocks a new request in the same conversation; a verified live no-write preflight can finalize NO_WRITE and allow a different intent. Missing legacy browser binding is not invented: an existing unbound nonempty conversation requires migration evidence.
- Known staged write exceptions report unknown persistence flags rather than false certainty that the message was not saved. Exceptions/latches from #1195 are preserved.

## Existing ExecutionOutbox reviewed
ExecutionOutbox.enqueue records scoped identity/payload with unique intent and aggregate order; dispatch_claimed durably sets UNCERTAIN before send; reconcile requires affirmative evidence and authoritative absence before RETRY. It also owns external action authorization/TTL, worker leases and effect ledger, and requires a live native SQLiteChatStore connection.
It is NOT blindly attached to local browser history: doing so would fabricate external-action authority and enqueue dispatchable actions or share a thread-bound connection. This patch adds only the missing browser→turn correlation; no second execution queue, dispatcher, lease manager, retry worker or approval engine. Outbox source and regression tests stay unchanged. The same fail-closed principle is applied: ambiguous admission/persistence is not authorization to resend.

## Tests and actual evidence
Two #1197 reproductions become security inversions in test_atlasquant_aion_chat_request_reconciliation.py: replay after session reset and after actual assistant commit/close fault must remain 2 messages, never 4. Those run the REAL existing READ/SEARCH product pipeline with SQLite. Initial local attempt could not import pandas in the executor dependency chain; this is a real environment limitation, not a pass. No dependency was installed on owner's machine.
Eighteen additional real SQLite unit/fault tests in tests/test_aion_browser_request_binding_units.py cover partial/absent pairs, concurrent reservation, payload/credential/conversation conflicts, owner/tenant/workspace isolation, corrupt receipt/content, unknown states, no-write finalization, invalid request identity, legacy migration refusal, post-COMMIT timeout, and a real Python process exit before/after assistant commit with WAL recovery.
Local Windows: 85 tests passed (request binding, preserved lifecycle/host/resilience, unchanged execution outbox, supply-chain and mandatory inventory), 6.932s. WSL is not installed; no installation attempted. Full two product inversions and Windows/Linux acceptance are performed in the dedicated exact-HEAD GitHub CI with repository-pinned dependencies, socket connects forbidden, no credentials or deployment. Final real results belong in the Draft PR description; no initial claim of CI success.
The existing UI replay expectation is strengthened from volatile IDEMPOTENT_REQUEST to LOCAL_PAIR_RECONCILED plus no-write/no-retry assertions; its 2-row invariant remains. Root test and unit suite are added to mandatory quality inventory. No existing assertion or security test was removed to hide a failure.

## Risks / blocked proof
Local SQLite readback establishes local record observation only. It does NOT establish physical host enrollment, externally signed request identity, cryptographic integrity of a maliciously edited/rolled-back database, remote effect success or a trusted generation/witness. Those production/physical claims remain BLOCKED; first installation HARD NO-GO.
Legacy outstanding requests cannot be reconstructed from unbound history without original operation/request/conversation/content evidence and owner-approved migration. Credential rotation/scope drift does not silently reinterpret old requests.
An ADMITTED request interrupted before expected-pair capture and a partially committed pair remain quarantined; no automated completion/absence-based retry is provided. Recovery decision and operator workflow are separate work.
Additional correlation/readback connections and verification have overhead; no performance SLO claimed. Queue-wide/distributed execution assurance is not expanded. Native SQLite thread affinity, WAL and existing backup/restore remain intact. Preserved #1195 file-identity protection is not replaced with a cryptographic anchor.

## Review gate
Exact candidate SHA, Win/Linux safety inversions and relevant legacy contracts must pass; characterize-before/fix-after counts must be explicit. Reconcile only matching scoped evidence; no new pair on replay. Review legacy fail-stop UX and registration changes. Draft only: NO MERGE / NO DEPLOY / NO WORKER / NO OWNER INSTALL / NO PAYMENT / NO PRODUCTION DATA OR CREDENTIALS. First installation HARD NO-GO.
