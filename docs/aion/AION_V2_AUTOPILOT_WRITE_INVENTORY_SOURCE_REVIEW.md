# AION: source-only inventory of 12 generic Autopilot writes

Separate audit lane for issue #1163, based on Draft PR #1162. The tool
only parses source AST and lists all direct gh_put_json/csv calls in main.
A new, removed, duplicated or dynamic callsite triggers inventory drift.

It also records specific SOURCE shapes: generic 200/201 success
without post-PUT GET, the legacy Twelve Data 409/422 return-False retry
shape (absent in this isolated consolidation based on #1156), and main's
possible zero exit after logging persistence errors. These are source
findings, NOT proof of remote effect.

The isolated consolidation already includes Draft #1156's fix preventing
409/422 from authorizing a second PUT. The auditor test now requires
that legacy retry shape to remain absent. This does not prove remote
persistence, trusted receipts or safety across process restarts.
Other sinks need classification by exact effects, identity, CAS and
readback semantics. A replaceable snapshot is not an append-only journal.

A zero exit from this inventory script means only a complete known
inventory. It NEVER certifies safe deployment, independent custody,
remote durability, restored state or cross-process CAS.

No runtime application code is changed. No new network connection, host
access, physical device, provider, merge or deploy is authorized.
#1117 remains HARD NO-GO.

Commands:
- python -B atlasquant_aion_v2_autopilot_write_inventory_audit.py
- python -B -m unittest discover -s tests -p test_atlasquant_aion_v2_autopilot_write_inventory_audit.py
