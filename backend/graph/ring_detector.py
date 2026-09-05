# backend/graph/ring_detector.py
# Detect abuse rings (clusters of buyers sharing devices, IPs, or card BINs) using community detection.

from __future__ import annotations

import logging
from typing import List, Set, Tuple

import networkx as nx
import community as community_louvain

logger = logging.getLogger(__name__)


def detect_rings(g: nx.Graph, min_buyers: int = 3) -> List[Set[str]]:
    """Detect rings (communities) in the bipartite entity graph.

    Args:
        g: Undirected NetworkX graph where buyer nodes are prefixed with "b:".
        min_buyers: Minimum number of buyer nodes in a community to qualify as a ring.

    Returns:
        List of sets of buyer IDs (without the "b:" prefix) representing each detected ring.
    """
    if g.number_of_nodes() == 0:
        return []

    # Louvain community detection works on undirected graphs.
    partition = community_louvain.best_partition(g)
    # Invert the partition mapping: community_id -> set of nodes
    communities: dict[int, Set[str]] = {}
    for node, comm_id in partition.items():
        communities.setdefault(comm_id, set()).add(node)

    rings: List[Set[str]] = []
    for nodes in communities.values():
        # Extract buyer nodes only
        buyers = {n[2:] for n in nodes if n.startswith("b:")}
        if len(buyers) >= min_buyers:
            rings.append(buyers)
    logger.info(f"Detected {len(rings)} rings (communities with >= {min_buyers} buyers)")
    return rings
