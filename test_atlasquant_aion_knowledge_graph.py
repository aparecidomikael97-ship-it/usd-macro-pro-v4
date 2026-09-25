from __future__ import annotations
import unittest

from atlasquant_aion_knowledge_graph import (
    derive_graph, graph_neighborhood, knowledge_graph_summary, new_edge,
    new_node, synchronize_knowledge_graph,
)


class AtlasQuantAionKnowledgeGraphTests(unittest.TestCase):
    def test_confirmed_causality_requires_evidence(self):
        with self.assertRaises(ValueError):
            new_edge(
                "episode:abc","CAUSED_BY","cause:def",
                truth_state="CONFIRMED",evidence_refs=[],
            )

    def test_unconfirmed_causality_is_rejected(self):
        with self.assertRaises(ValueError):
            new_edge(
                "episode:abc","CAUSED_BY","cause:def",
                truth_state="HYPOTHESIS",evidence_refs=["evidence:1"],
            )

    def test_structural_graph_derives_explicit_wisdom_links(self):
        graph=derive_graph(
            wisdom_entries=[{
                "wisdom_id":"WIS-1","topic":"Lição","domain":"trading",
                "truth_state":"CONFIRMED","confidence_pct":90,
                "state":"ACTIVE","evidence_refs":["ref:1"],
                "source_episode_ids":["LEARN-1"],"applies_to":["USD"],
            }],
        )
        summary=knowledge_graph_summary(graph)
        self.assertGreaterEqual(summary["nodes"],4)
        relations={x["relation"] for x in graph["edges"]}
        self.assertIn("SUPPORTED_BY",relations)
        self.assertIn("DERIVED_FROM",relations)
        self.assertIn("APPLIES_TO",relations)
        self.assertFalse(summary["causality_inferred_automatically"])

    def test_confirmed_error_cause_without_evidence_does_not_become_causal_edge(self):
        graph=derive_graph(
            learning_episodes=[{
                "episode_id":"LEARN-1","subject":"Erro","domain":"trading",
                "state":"SETTLED","evaluation":"MISMATCH",
                "error_cause":"TIMING","error_cause_truth":"CONFIRMED",
                "evidence_refs":[],
            }]
        )
        self.assertFalse(any(x["relation"]=="CAUSED_BY" for x in graph["edges"]))

    def test_confirmed_error_cause_with_evidence_becomes_causal_edge(self):
        graph=derive_graph(
            learning_episodes=[{
                "episode_id":"LEARN-1","subject":"Erro","domain":"trading",
                "state":"SETTLED","evaluation":"MISMATCH",
                "error_cause":"TIMING","error_cause_truth":"CONFIRMED",
                "evidence_refs":["replay:123"],
            }]
        )
        causal=[x for x in graph["edges"] if x["relation"]=="CAUSED_BY"]
        self.assertEqual(len(causal),1)
        self.assertEqual(causal[0]["truth_state"],"CONFIRMED")

    def test_neighborhood_is_read_only(self):
        graph=derive_graph(
            wisdom_entries=[{
                "wisdom_id":"WIS-X","topic":"Liquidity","domain":"trading",
                "truth_state":"HYPOTHESIS","evidence_refs":[],
                "source_episode_ids":[],"applies_to":[],
            }]
        )
        out=graph_neighborhood(graph,"Liquidity")
        self.assertGreaterEqual(out["matched_nodes"],1)
        self.assertFalse(out["executes_action"])

    def test_synchronize_preserves_manual_nodes_without_inventing_edges(self):
        manual={
            "nodes":[new_node(
                "component:guardian",node_type="COMPONENT",label="Guardian",
                truth_state="UNKNOWN",
            )],
            "edges":[],
        }
        synced=synchronize_knowledge_graph(manual,wisdom_entries=[])
        self.assertTrue(any(x["node_id"]=="component:guardian" for x in synced["nodes"]))
        self.assertEqual(synced["edges"],[])


if __name__=="__main__":
    unittest.main()
