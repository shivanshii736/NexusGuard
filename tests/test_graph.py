"""P1 tests: no downloads, no osmnx needed."""
import networkx as nx
import pytest
from nexusguard.network.build_graph import add_peak_time, largest_scc, validate_graph
from tests.toy_graph import make_toy


def test_toy_graph_satisfies_contract():
    G, _, _ = make_toy()
    assert validate_graph(G)["nodes"] == 49


def test_peak_time_handles_list_link_and_unknown_highway():
    G = nx.MultiDiGraph()
    for i in range(3):
        G.add_node(i, x=77.0, y=12.0)
    G.add_edge(0, 1, 0, length=100, travel_time=10.0, highway=["primary", "secondary"])
    G.add_edge(1, 2, 0, length=100, travel_time=10.0, highway="primary_link")
    G.add_edge(2, 0, 0, length=100, travel_time=10.0, highway="weird_new_tag")
    add_peak_time(G)
    assert G[0][1][0]["peak_time"] == pytest.approx(22.0)   # primary x2.2
    assert G[1][2][0]["peak_time"] == pytest.approx(22.0)   # _link stripped
    assert G[2][0][0]["peak_time"] == pytest.approx(20.0)   # default x2.0


def test_largest_scc_drops_dead_ends():
    G = nx.MultiDiGraph()
    for i in range(5):
        G.add_node(i, x=77.0, y=12.0)
    for u, v in [(0, 1), (1, 2), (2, 0), (3, 0)]:           # 3 only has an outgoing edge; 4 is isolated
        G.add_edge(u, v, 0, length=1, travel_time=1.0, peak_time=2.0)
    H = largest_scc(G)
    assert set(H.nodes) == {0, 1, 2}
    assert nx.is_strongly_connected(H)
