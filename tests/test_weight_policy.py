import importlib
import os

from fastapi.testclient import TestClient

# Ensure a clean env per test run
os.environ.pop("GARDENER_TOKEN", None)
os.environ["PN_DB"] = "test_weight.db"

app_module = importlib.import_module("synapse_app")
app = getattr(app_module, "app")
client = TestClient(app)


def test_weight_policy_topic_and_history(tmp_path):
    # Paper 1, first approval by R on topic "demo" -> expected 1.3
    p1 = {
        "type": "Paper",
        "id": "urn:pn:paper:t1",
        "title": "T1",
        "claims": [{"id": "urn:pn:claim:X1", "text": "X1", "topic": "demo"}],
        "graphPatch": [{"op": "add", "triple": ["urn:pn:claim:X1", "supports", "urn:pn:claim:X1"]}],
        "provenance": {"source": "test", "license": "internal"},
    }
    r = client.post("/publish", json=p1)
    assert r.status_code == 202
    r = client.post(
        "/review",
        json={
            "paper_id": p1["id"],
            "reviewer": {"id": "did:pn:R"},
            "vote": "approve",
            "topic": "demo",
        },
    )
    assert r.status_code == 200
    tally = r.json()["tally"]
    assert 1.29 < tally["approve"] < 1.31

    # Paper 2, same reviewer on same topic -> expected 1.4 (prev approvals=1 adds +0.1)
    p2 = {
        "type": "Paper",
        "id": "urn:pn:paper:t2",
        "title": "T2",
        "claims": [{"id": "urn:pn:claim:X2", "text": "X2", "topic": "demo"}],
        "graphPatch": [{"op": "add", "triple": ["urn:pn:claim:X2", "supports", "urn:pn:claim:X2"]}],
        "provenance": {"source": "test", "license": "internal"},
    }
    r = client.post("/publish", json=p2)
    assert r.status_code == 202
    r = client.post(
        "/review",
        json={
            "paper_id": p2["id"],
            "reviewer": {"id": "did:pn:R"},
            "vote": "approve",
            "topic": "demo",
        },
    )
    assert r.status_code == 200
    tally2 = r.json()["tally"]
    assert 1.39 < tally2["approve"] < 1.41
