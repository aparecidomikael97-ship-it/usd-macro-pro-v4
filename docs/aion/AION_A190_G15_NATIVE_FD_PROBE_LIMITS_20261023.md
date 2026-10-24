# A190 G15 — Native SQLite FD observation, counterexample and architecture gate (LAB)

**Scope:** Stacked on G14 #1501; synthetic local DBs only. No runtime gate/change, no main/merge, deploy, Worker, vendor account, customer, credential, real effects, or new paid service.

## Exact question
G14 closes a same-path ABA when the replacement SQLite has a different local marker. A backup clone preserves the marker, and a SQLite native connection may continue reading the swapped-out clone after the *pathname* is restored. Does scanning Linux `/proc/self/fd` establish which file the **same SQLite connection** actually uses?

## Hypothesis and falsification
G15 reads only process descriptors and identifies plausible SQLite main DB file headers via `fstat` + `pread`. It compares descriptors observed before/after a connection opens.

1. Ordinary fresh connection: the newly observed inode can match the expected on-path SQLite file. This is only a *candidate*.
2. Wrong same-marker clone opened during transient pathname swap: when native FD is freshly opened after the snapshot, the observed inode may mismatch even though SQLite `PRAGMA database_list` continues naming the original filename. Useful diagnosis, **not** proof.
3. **Critical counterexample — RED:** open the wrong SQLite connection before the snapshot; after restoring the pathname, open a legitimate *decoy* connection after the snapshot. The heuristic reports a matching candidate while the wrong live connection still reads the detached clone. Therefore candidate association can be fooled in the same process **without changing the local database marker**.
4. Two new SQLite database descriptors are ambiguous and must never authorize operations.
5. Windows does not provide Linux `/proc/self/fd` semantics; the experiment returns unsupported and cannot be extrapolated.

`Observation.is_native_attestation` is deliberately **always false**, including for a matching inode. No application stores or execution decisions consume these observations.

## Why the original P0 is still open
SQLite's official C interface `sqlite3_file_control(...,SQLITE_FCNTL_FILE_POINTER,...)` returns the SQLite VFS `sqlite3_file` pointer for a given connection. Public Python `sqlite3.Connection` does **not** expose a supported equivalent to identify the underlying VFS handle or OS inode. Native file identity is not obtained by a separate independently-opened `os.open` descriptor or a candidate discovered in `/proc`. WAL and other sidecars are a separate consistency problem.

Official references:
- https://www.sqlite.org/c3ref/file_control.html
- https://www.sqlite.org/fileformat2.html
- https://docs.python.org/3/library/sqlite3.html

## Engineering acceptance gates for a *future* true fix
- A supported SQLite connection/VFS integration that returns the identity of the main DB OS handle **from that exact active connection**, validated on Linux and Windows; reject unset or ambiguous results.
- VFS binding and sidecar identity must survive pre-open, open, read/write, close, restart, duplicate files, same-marker clones, and deliberate same-path ABA, including test doubles/decoys.
- After a write whose result is uncertain, leave it **UNCERTAIN**; never automatically resend.
- Host-controlled marker/identity is not external owner proof, external signed receipt, or independent monotonic rollback custody. Each has its own P0 gate.

## Protocol / immutable gates
Evidence must identify exact tested commit, OS runner and adversarial output; a green CI only validates that this *inability to attest* is reproduced. Do not count observation success as homologation.

**0/6 P0 homologados · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.**
