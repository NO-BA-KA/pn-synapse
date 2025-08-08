import importlib

from fastapi.testclient import TestClient

app_module = importlib.import_module("synapse_app")
app = getattr(app_module, "app")
client = TestClient(app)


def test_review_threshold_and_integrate():
    paper = {
        "type": "Paper",
        "id": "urn:pn:paper:unittest",
        "title": "UnitTest",
        "claims": [{"id": "urn:pn:claim:X", "text": "X", "topic": "demo"}],
        "graphPatch": [{"op": "add", "triple": ["urn:pn:claim:X", "supports", "urn:pn:claim:X"]}],
        "provenance": {"source": "test", "license": "internal"},
    }
    r = client.post("/publish", json=paper)
    assert r.status_code == 202

    for i in range(3):
        rv = {
            "paper_id": paper["id"],
            "reviewer": {"id": f"did:pn:axon:{i}"},
            "vote": "approve",
        }
        r = client.post("/review", json=rv)
        assert r.status_code == 200

    r = client.post(f"/integrate/{paper['id']}")
    assert r.status_code == 200
    assert r.json()["integrated"] is True
