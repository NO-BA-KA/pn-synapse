import os

from fastapi.testclient import TestClient

import synapse_app

# Force RBAC to require the key regardless of import timing
os.environ["PN_DB"] = "test_rbac.db"

app = synapse_app.app
client = TestClient(app)


def test_integrate_requires_api_key():
    synapse_app.GARDENER_TOKEN_OVERRIDE = "test-secret"
    p = {
        "type": "Paper",
        "id": "urn:pn:paper:rbac",
        "title": "RBAC",
        "claims": [{"id": "urn:pn:claim:A", "text": "A", "topic": "rbac"}],
        "graphPatch": [{"op": "add", "triple": ["urn:pn:claim:A", "supports", "urn:pn:claim:A"]}],
        "provenance": {"source": "test", "license": "internal"},
    }
    assert client.post("/publish", json=p).status_code == 202
    for i in range(3):
        assert (
            client.post(
                "/review",
                json={
                    "paper_id": p["id"],
                    "reviewer": {"id": f"did:pn:{i}"},
                    "vote": "approve",
                    "topic": "rbac",
                },
            ).status_code
            == 200
        )

    # No key -> 401
    r = client.post(f"/integrate/{p['id']}")
    assert r.status_code == 401

    # Correct key -> 200
    r = client.post(f"/integrate/{p['id']}", headers={"X-API-Key": "test-secret"})
    assert r.status_code == 200
    assert r.json()["integrated"] is True
