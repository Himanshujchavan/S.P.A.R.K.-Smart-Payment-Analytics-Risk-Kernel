# backend/graph/ring_scorer.py
# Compute ring‑related risk features for a buyer using the graph built by edge_builder.

from __future__ import annotations

import logging
from typing import Dict, Set, List

import networkx as nx

from .edge_builder import build_entity_graph
from .ring_detector import detect_rings

logger = logging.getLogger(__name__)

# Cache the latest graph and rings to avoid rebuilding on every call.
_GRAPH_CACHE: nx.Graph | None = None
_RINGS_CACHE: List[Set[str]] = []


def _ensure_graph(limit: int = 10000) -> nx.Graph:
    """Build or retrieve a cached entity graph.

    The graph is built from the most recent ``limit`` transactions. For production
    you would refresh this cache periodically (e.g. a daily batch job). Here we
    lazily rebuild when the cache is empty.
    """
    global _GRAPH_CACHE
    if _GRAPH_CACHE is None:
        logger.info("Building entity graph for ring scoring (limit=%s)", limit)
        _GRAPH_CACHE = build_entity_graph(limit=limit)
    return _GRAPH_CACHE


def _ensure_rings(limit: int = 10000, min_buyers: int = 3) -> List[Set[str]]:
    """Detect rings (communities) and cache the result.

    Returns a list of buyer‑ID sets (without the ``b:`` prefix).
    """
    global _RINGS_CACHE
    if not _RINGS_CACHE:
        g = _ensure_graph(limit)
        _RINGS_CACHE = detect_rings(g, min_buyers=min_buyers)
    return _RINGS_CACHE


def get_ring_features(buyer_id: str, limit: int = 10000, min_buyers: int = 3) -> Dict[str, int | float]:
    """Return ring‑derived features for a given buyer.

    The features match the schema entries defined in ``feature_schema.py``:
        - ``ring_member_count`` – total number of distinct buyers in the ring.
        - ``ring_density`` – proportion of possible edges that actually exist
          within the sub‑graph of the ring (0‑1).
        - ``ring_flagged_amount`` – placeholder (set to 0) – in a full system this
          would aggregate the sum of flagged transaction amounts for the ring.
        - ``on_ring_shared_device`` – 1 if the buyer shares a device with any other
          buyer in the same ring.
        - ``on_ring_shared_ip`` – 1 if the buyer shares an IP with any other buyer
          in the same ring.
        - ``on_ring_shared_bin`` – 1 if the buyer shares a card BIN with any other
          buyer in the same ring.
    """
    rings = _ensure_rings(limit=limit, min_buyers=min_buyers)
    # Find the ring that contains this buyer (if any)
    buyer_ring: Set[str] | None = None
    for ring in rings:
        if buyer_id in ring:
            buyer_ring = ring
            break

    if not buyer_ring:
        # Buyer not part of any detected ring – return zeroed defaults.
        return {
            "ring_member_count": 0,
            "ring_density": 0.0,
            "ring_flagged_amount": 0.0,
            "on_ring_shared_device": 0,
            "on_ring_shared_ip": 0,
            "on_ring_shared_bin": 0,
        }

    # Build subgraph of the ring (buyers + their linked entities)
    g = _ensure_graph(limit=limit)
    # Extract nodes belonging to the ring (buyer nodes)
    buyer_nodes = {f"b:{b}" for b in buyer_ring}
    # Also include any neighbor nodes connected to those buyers – these are the
    # devices, IPs and card BINs that define the ring structure.
    sub_nodes = set(buyer_nodes)
    for b in buyer_nodes:
        sub_nodes.update(g.neighbors(b))
    subgraph = g.subgraph(sub_nodes)

    # Compute density: number of edges / possible edges in the undirected subgraph
    possible_edges = len(subgraph.nodes()) * (len(subgraph.nodes()) - 1) / 2
    density = subgraph.number_of_edges() / possible_edges if possible_edges > 0 else 0.0

    # Determine shared‑entity flags for the target buyer.
    buyer_node = f"b:{buyer_id}"
    neighbors = set(g.neighbors(buyer_node))
    shared_device = any(n.startswith("d:") for n in neighbors if any(other.startswith("d:") for other in g.neighbors(buyer_node) if other != n))
    # Simpler heuristic: if the buyer has any device node that connects to another buyer in the ring.
    shared_device = any(
        any(other.startswith("b:") for other in g.neighbors(dev))
        for dev in neighbors if dev.startswith("d:")
    )
    shared_ip = any(
        any(other.startswith("b:") for other in g.neighbors(ip))
        for ip in neighbors if ip.startswith("i:")
    )
    shared_bin = any(
        any(other.startswith("b:") for other in g.neighbors(bin_))
        for bin_ in neighbors if bin_.startswith("c:")
    )

    return {
        "ring_member_count": len(buyer_ring),
        "ring_density": round(density, 4),
        "ring_flagged_amount": 0.0,  # placeholder – would be sum of flagged txn amounts in production
        "on_ring_shared_device": int(shared_device),
        "on_ring_shared_ip": int(shared_ip),
        "on_ring_shared_bin": int(shared_bin),
    }
