# AION F1 A.57 — real entrypoint negative contracts (LAB only)

Parent A.56 Draft #1275: 77e192477b8c38a123b71021f020806e0750ad67.
Linked: #1178 F1, #1117 first install, #1190 checkpoint, #1274 human-click.
Scope: one test file, one dedicated CI workflow, this document. No runtime edits.

Six focused adversarial and diagnostic assertions against actual imported AION modules:
1. A valid-looking read-only runtime posture can report PASS while Worker tick must BLOCK before CAS/executor without an enrolled independent witness.
2. Caller-provided independent_witness_verified, owner-authorization, witness_head, producer_receipt fields cannot substitute independent enrollment.
3. Direct feature flag enable writer denies before HTTP.
4. Direct HUMAN_CLICK kernel with caller supplied digest and forged witness denies before handler and receipts.
5. Public confirmation=True still permits inert local read/draft, which is NOT a physical HUMAN_OWNER consent proof, and must not enable provider, trading, persistence or autonomy.
6. Feature disabled must make no network runtime GET.

The workflow denies socket.connect in-process, uses existing pinned CI dependency set and exact PR head SHA. Test fixtures intercept handlers and callbacks. No real provider or network effect, no real root, witness, owner, signatures or machine enrollment. Neither fixture results nor a green CI certify independent custody, state freshness, recovery, terminal producer no-effect fence or physical installation.

Design/F1 decisions still open: out-of-band pin and independent custodian, read-current-head and compare-and-advance durable semantics, operator separation, recovery after ACK loss, revocation, offline fail-closed, account controls and all-cost estimate <= R$200 monthly. AION Core V1 frozen and worker feature disabled. Producer receipts COMMITTED_EFFECT and NO_EFFECT_FENCED are independent P0.

NO GO: 0/6 P0 homologated, first install 20/20 HARD NO-GO. No main merge, deploy, spending, credentials, host tests, real worker or external effects.
