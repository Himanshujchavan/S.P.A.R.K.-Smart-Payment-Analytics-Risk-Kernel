# backend/graph/edge_builder.py
# Build a bipartite graph linking entities (buyers, devices, IPs, card bins) from transaction data.

from __future__ import annotations

import logging
from typing import List, Tuple

import networkx as nx

from api.core.db import SessionLocal
from ingestion.feature_updater import get_velocity_features
from ml.features.feature_schema import all_feature_names

logger = logging.getLogger(__name__)


def build_entity_graph(limit: int = 10000) -> nx.Graph:
    """Construct an undirected graph where each node is an entity identifier.

    Nodes are prefixed with a type tag:
        - "b:<buyer_id>"
        - "d:<device_id>"
        - "i:<ip_address>"
        - "c:<card_bin>"

    Edges are created for each transaction linking the buyer to its device, IP, and card BIN.
    The function returns a NetworkX Graph suitable for downstream ring detection.
    """
    db = SessionLocal()
    g = nx.Graph()
    try:
        # Pull a sample of recent transactions (lightweight query, no heavy joins)
        query = """
            SELECT txn_id, buyer_id, device_id, ip_address, card_bin
            FROM transactions
            ORDER BY created_at DESC
            LIMIT :limit
        """
        rows = db.execute(query, {"limit": limit}).fetchall()
        for row in rows:
            buyer = f"b:{row['buyer_id']}"
            device = f"d:{row['device_id']}"
            ip = f"i:{row['ip_address']}"
            card = f"c:{row['card_bin']}"
            # Add nodes (NetworkX automatically dedups)
            g.add_node(buyer, type="buyer")
            g.add_node(device, type="device")
            g.add_node(ip, type="ip")
            g.add_node(card, type="bin")
            # Connect buyer to each of its entities
            g.add_edge(buyer, device)
            g.add_edge(buyer, ip)
            g.add_edge(buyer, card)
        logger.info(f"Built graph with {g.number_of_nodes()} nodes and {g.number_of_edges()} edges")
    finally:
        db.close()
    return g
