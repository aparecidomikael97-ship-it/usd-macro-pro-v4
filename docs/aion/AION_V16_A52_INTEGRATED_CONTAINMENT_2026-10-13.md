# A.52 - integrated A50/A51 containment, LAB only

Parent A49 c1c7f5940eef913d60ff2f77e3bc1de3181db2f2. Sibling inputs A50 87b4b2726c9de50860df0da313565ac105d967bc and A51 8062a5912312bca842e7e05eef77863ece844344 preserved. New isolated checkout AQ_LAB_A52_INTEGRATED_20261013;1672tracked source hashes recorded. No main/CoreV1/A50LAB changes.

Preserves seven A50 tests and Saga plan/genesis integrity patch, three A51 tests and both autonomous direct executor denials. Both mandatory Security steps precede historical adversarial suite; Quality retains A50 registration and existing A51 test module. Add only A49 to PR branch filters for stacked exact-HEAD CI, no temporary main retarget or manual dispatch. No permission or feature flag enabled.

RED evidence: A50 tests-only SHA1e343ef40739a3e331d4c7ba2cd1716ffb8e9ddb, Security38489672243:2PASS5FAIL. A51 tests-only SHAa361873feff35683c1f41b6a299459cc01eb3265, Security38488428311:1PASS2FAIL. Existing evidence, not new executions.

Windows Python3.11.9 targeted10:7A50PASS,3A51importERROR (cryptography absent through tenant_crypto),exit1,zero skips. No installation or dependency mocks. AST and diffcheckPASS. All18previous executor tests AST-identical; A51 adds only3. Original copied files preserve source blob bytes.

Expected historical RED, to measure on A52 exact HEAD: A49 Quality6247/31ERROR+21FAIL; A50 adds7PASS; A51 Quality6250/32ERROR+32FAIL adds3PASS plus1inflightERROR+11legacyFAIL. Original23OutboxERROR+8SagaERROR+21WorkerFAIL remain open; no waiver/xfail/assert changes. No productive worker/producer/CAS execution path released.

Local integrity hashes do not prove independent source, latest-head antirollback, owner enrollment or causal COMMITTED_EFFECT/NO_EFFECT_FENCED receipts. 0/6P0 homologated;20/20FIRST_INSTALL HARD_NO_GO. Cloud1263 ZIP investigation untouched. No merge/deploy/Worker/Render/flags/host installation/TPM/enrollment/keys/signature/expenses. Exact CI results must be read; no global green claim.
