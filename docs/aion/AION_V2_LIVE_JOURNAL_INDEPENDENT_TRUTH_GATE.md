# AION Live Journal — fail-closed continuity claim

The AION event journal's calculated 24h heartbeat coverage is only an
observation. It does not prove independent remote custody, monotonic
durability, or read-after-write verification. The legacy overlay copied
a self-reported continuous_24h_confirmed=True into a client-facing
continuous_runtime_confirmed=True.

This Draft changes the overlay and the real Autopilot status paths so
the operational confirmed flags are always False until a separately
reviewed durable receipt protocol exists. The calculated candidate
remains visible through separate explicitly advisory fields; the old
CONTINUOUS_24H label becomes UNVERIFIED_REMOTE_HISTORY to avoid
misleading operators. It does not modify the candidate computation.

The inherited journal test previously expected the permissive behavior.
That single expectation is tightened, while coverage mathematics tests
stay unchanged. Synthetic adversarial tests cover forged owner status,
self-generated digest, no heartbeat data, missing journal and true
calculated coverage without independent evidence.

The generic GitHub writer's accepted HTTP 200/201 and legacy
journal status persisted flag remain separate concerns under issue
#1163. This Draft does not resolve old uncertain writes or permit
retry, merge, deploy, Worker, spending, hardware or Core V1 changes.
Checkpoint #1117 remains HARD NO-GO. Codex integration work remains
on its own branch.
