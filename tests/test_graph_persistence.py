import importlib
import os
import sqlite3

from fastapi.testclient import TestClient

os.environ.pop("GARDENER_TOKEN", None)
os.environ["PN_DB"] = "test_graph.db"

app_module = importlib.import_module("synapse_app")
app = getattr(app_module, "app")
client = TestClient(app)


def test_graph_persisted_to_sqlite(tmp_path):
    p = {
        "type": "Paper",
        "id": "urn:pn:paper:g1",
        "title": "G1",
        "claims": [{"id": "urn:pn:claim:G", "text": "G", "topic": "graph"}],
        "graphPatch": [{"op": "add", "triple": ["urn:pn:claim:G", "supports", "urn:pn:claim:G"]}],
        "provenance": {"source": "test", "license": "internal"},
    }
    assert client.post("/publish", json=p).status_code == 202
    # approvals to pass threshold
    client.post(
        "/review",
        json={
            "paper_id": p["id"],
            "reviewer": {"id": "did:pn:1"},
            "vote": "approve",
            "topic": "graph",
        },
    )
    client.post(
        "/review",
        json={
            "paper_id": p["id"],
            "reviewer": {"id": "did:pn:2"},
            "vote": "approve",
            "topic": "graph",
        },
    )
    client.post(
        "/review",
        json={
            "paper_id": p["id"],
            "reviewer": {"id": "did:pn:3"},
            "vote": "approve",
            "topic": "graph",
        },
    )
    r = client.post(f"/integrate/{p['id']}")
    assert r.status_code == 200

    # Check the DB
    db = os.environ["PN_DB"]
    con = sqlite3.connect(db)
    cur = con.execute("SELECT COUNT(*) FROM edges")
    n = cur.fetchone()[0]
    assert n >= 1
