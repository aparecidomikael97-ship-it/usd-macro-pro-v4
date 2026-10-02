import unittest

from atlasquant_aion_library_foundation import ingest_document, review_document
from atlasquant_aion_library_index import (
    empty_library_index,
    index_document,
    search_library_index,
    classification_snapshot,
    document_graph_fragment,
)

def _admin(tenant="tenant:a", workspace="workspace:a"):
    return {
        "tenant_id":tenant,
        "workspace_id":workspace,
        "role":"ADMIN",
        "review_approved":True,
    }

def _validated(state="VALIDATED", tenant="tenant:a", workspace="workspace:a"):
    base=ingest_document(
        tenant_id=tenant,
        workspace_id=workspace,
        title="Manual de Payroll",
        source_reference="file://payroll.pdf",
        checksum="sha256-payroll",
        source_type="INTERNAL_DOCUMENT",
        author="Equipe AION",
        publisher="AtlasQuant",
        published_at="2026-09-01T00:00:00+00:00",
        retrieved_at="2026-10-02T02:00:00+00:00",
        document_version="1",
        rights_status="OWNED",
        summary="Payroll emprego salarios desemprego economia americana.",
        evidence_refs=["EV-PAYROLL-1"],
    )["record"]
    return review_document(
        base,
        trusted_context=_admin(tenant,workspace),
        decision=state,
        evidence_refs=["EV-PAYROLL-1"],
        reason="revisao documental",
    )["record"]

class AionLibraryIndexTests(unittest.TestCase):
    def test_unreviewed_document_cannot_be_indexed(self):
        raw=ingest_document(
            tenant_id="tenant:a",workspace_id="workspace:a",
            title="Rascunho",source_reference="file://draft.pdf",checksum="abc",
        )["record"]
        result=index_document(
            empty_library_index(),raw,
            passages=["conteudo qualquer"],
            trusted_context=_admin(),
        )
        self.assertEqual(result["status"],"BLOCKED")
        self.assertIn("DOCUMENT_NOT_INDEXABLE",result["blockers"])

    def test_validated_document_is_indexed_offline(self):
        result=index_document(
            empty_library_index(),_validated(),
            passages=["Payroll mede a variacao do emprego fora do setor agricola."],
            trusted_context=_admin(),
        )
        self.assertEqual(result["status"],"INDEXED")
        self.assertEqual(result["indexed_passages"],1)
        self.assertFalse(result["external_persisted"])
        self.assertFalse(result["memory_promoted"])
        self.assertFalse(result["execution_authorized"])

    def test_search_returns_provenance_and_no_semantic_claim(self):
        indexed=index_document(
            empty_library_index(),_validated(),
            passages=[
                "Payroll mede empregos criados fora do setor agricola.",
                "Average Hourly Earnings acompanha salarios medios.",
            ],
            trusted_context=_admin(),
        )["index"]
        result=search_library_index(
            indexed,"payroll empregos",
            trusted_context=_admin(),
        )
        self.assertEqual(result["status"],"RESULTS")
        self.assertTrue(result["hits"])
        self.assertTrue(result["hits"][0]["provenance_id"])
        self.assertFalse(result["semantic_search"])
        self.assertFalse(result["provider_called"])

    def test_cross_tenant_search_returns_no_hits(self):
        indexed=index_document(
            empty_library_index(),_validated(),
            passages=["Payroll mede empregos criados."],
            trusted_context=_admin(),
        )["index"]
        result=search_library_index(
            indexed,"payroll",
            trusted_context=_admin("tenant:b","workspace:b"),
        )
        self.assertEqual(result["status"],"NO_RESULTS")
        self.assertEqual(result["hits"],[])

    def test_workspace_isolation_applies_with_same_tenant(self):
        indexed=index_document(
            empty_library_index(),_validated(),
            passages=["Payroll mede empregos criados."],
            trusted_context=_admin(),
        )["index"]
        result=search_library_index(
            indexed,"payroll",
            trusted_context=_admin("tenant:a","workspace:b"),
        )
        self.assertEqual(result["hits"],[])

    def test_conflicting_document_keeps_unknown_truth(self):
        doc=_validated("CONFLICTING")
        indexed=index_document(
            empty_library_index(),doc,
            passages=["Fonte A diverge da fonte B sobre payroll."],
            trusted_context=_admin(),
        )["index"]
        hit=search_library_index(indexed,"payroll",trusted_context=_admin())["hits"][0]
        self.assertEqual(hit["document_state"],"CONFLICTING")
        self.assertEqual(hit["truth_state"],"UNKNOWN")

    def test_stale_document_remains_indexable_but_unknown(self):
        doc=_validated("STALE")
        indexed=index_document(
            empty_library_index(),doc,
            passages=["Regra antiga de interpretacao do payroll."],
            trusted_context=_admin(),
        )["index"]
        snap=classification_snapshot(indexed)
        self.assertEqual(snap["by_state"]["STALE"],1)
        hit=search_library_index(indexed,"payroll",trusted_context=_admin())["hits"][0]
        self.assertEqual(hit["truth_state"],"UNKNOWN")

    def test_reindex_replaces_document_passages_deterministically(self):
        doc=_validated()
        first=index_document(
            empty_library_index(),doc,
            passages=["Payroll primeira versao."],
            trusted_context=_admin(),
        )["index"]
        second=index_document(
            first,doc,
            passages=["Payroll segunda versao."],
            trusted_context=_admin(),
        )["index"]
        self.assertEqual(len(second["documents"]),1)
        self.assertEqual(len(second["passages"]),1)
        self.assertIn("segunda",second["passages"][0]["text"].lower())

    def test_graph_fragment_only_builds_explicit_support_relation(self):
        fragment=document_graph_fragment(_validated())
        self.assertEqual(fragment["status"],"FRAGMENT")
        self.assertEqual(len(fragment["nodes"]),2)
        self.assertEqual(len(fragment["edges"]),1)
        self.assertEqual(fragment["edges"][0]["relation"],"SUPPORTED_BY")
        self.assertFalse(fragment["semantic_inference_automatic"])
        self.assertFalse(fragment["causality_inferred_automatically"])

    def test_empty_query_fails_closed(self):
        result=search_library_index(
            empty_library_index(),"",
            trusted_context=_admin(),
        )
        self.assertEqual(result["status"],"BLOCKED")

if __name__=="__main__":
    unittest.main()
