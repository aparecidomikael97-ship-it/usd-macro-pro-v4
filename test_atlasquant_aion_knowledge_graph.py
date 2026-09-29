from __future__ import annotations
import unittest

from atlasquant_aion_knowledge_graph import (
    MAX_DERIVE_RECORDS_PER_SOURCE, MAX_EDGES, MAX_NODES,
    derive_graph, graph_neighborhood, knowledge_graph_summary, new_edge,
    new_node, normalize_edges, normalize_nodes, synchronize_knowledge_graph,
    _append_edge, _upsert_node,
)


class AtlasQuantAionKnowledgeGraphTests(unittest.TestCase):
    def test_confirmed_causality_requires_evidence(self):
        with self.assertRaises(ValueError):
            new_edge(
                "episode:abc","CAUSED_BY","cause:def",
                truth_state="CONFIRMED",evidence_refs=[],
            )

    def test_any_confirmed_relationship_requires_evidence(self):
        with self.assertRaises(ValueError):
            new_edge(
                "lesson:abc","CONTRADICTS","lesson:def",
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


    def test_node_and_edge_iterables_stop_at_explicit_prefix_bounds(self):
        node_consumed={"count":0}
        def nodes():
            for index in range(MAX_NODES*2+1):
                if index>=MAX_NODES*2:
                    raise AssertionError("node iterable consumed past bound")
                node_consumed["count"]+=1
                yield {}
        self.assertEqual(normalize_nodes(nodes()),[])
        self.assertEqual(node_consumed["count"],MAX_NODES*2)

        edge_consumed={"count":0}
        def edges():
            for index in range(MAX_EDGES*2+1):
                if index>=MAX_EDGES*2:
                    raise AssertionError("edge iterable consumed past bound")
                edge_consumed["count"]+=1
                yield {}
        self.assertEqual(normalize_edges(edges()),[])
        self.assertEqual(edge_consumed["count"],MAX_EDGES*2)

    def test_derive_source_generator_is_not_consumed_past_source_cap(self):
        consumed={"count":0}
        def wisdom():
            for index in range(MAX_DERIVE_RECORDS_PER_SOURCE+1):
                if index>=MAX_DERIVE_RECORDS_PER_SOURCE:
                    raise AssertionError("derive source consumed past bound")
                consumed["count"]+=1
                yield {}
        graph=derive_graph(wisdom_entries=wisdom())
        self.assertEqual(graph["nodes"],[])
        self.assertEqual(graph["edges"],[])
        self.assertEqual(consumed["count"],MAX_DERIVE_RECORDS_PER_SOURCE)

    def test_graph_accumulators_refuse_growth_past_declared_caps(self):
        nodes=[
            {"node_id":f"component:n{index}"}
            for index in range(MAX_NODES)
        ]
        _upsert_node(
            nodes,
            {"node_id":"component:overflow"},
        )
        self.assertEqual(len(nodes),MAX_NODES)
        self.assertFalse(
            any(x["node_id"]=="component:overflow" for x in nodes)
        )

        edges=[
            {"edge_id":f"edge:{index}"}
            for index in range(MAX_EDGES)
        ]
        _append_edge(
            edges,
            {"edge_id":"edge:overflow"},
        )
        self.assertEqual(len(edges),MAX_EDGES)
        self.assertFalse(
            any(x["edge_id"]=="edge:overflow" for x in edges)
        )


if __name__=="__main__":
    unittest.main()
