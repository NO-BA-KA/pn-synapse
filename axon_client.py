import requests
import json
from datetime import datetime, timezone

SYNAPSE = "http://localhost:8000"


def publish_sample():
    paper = {
        "type": "Paper",
        "id": "urn:pn:paper:demo-001",
        "title": "Demo: A supports B",
        "claims": [
            {"id": "urn:pn:claim:A", "text": "A is true", "topic": "demo"},
            {"id": "urn:pn:claim:B", "text": "B is true", "topic": "demo"},
        ],
        "graphPatch": [
            {"op": "add", "triple": ["urn:pn:claim:A", "supports", "urn:pn:claim:B"]}
        ],
        "provenance": {
            "source": "demo",
            "license": "internal",
            "collected_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    r = requests.post(f"{SYNAPSE}/publish", json=paper)
    r.raise_for_status()
    print("publish:", r.json())


def review(paper_id, reviewer_id, vote, weight=None):
    rev = {"paper_id": paper_id, "reviewer": {"id": reviewer_id}, "vote": vote}
    if weight is not None:
        rev["weight"] = weight
    r = requests.post(f"{SYNAPSE}/review", json=rev)
    r.raise_for_status()
    print("review:", r.json())


def integrate(paper_id):
    r = requests.post(f"{SYNAPSE}/integrate/{paper_id}")
    print("integrate:", r.status_code, r.json())


def sync(since=None):
    params = {"since": since} if since else {}
    r = requests.get(f"{SYNAPSE}/sync", params=params)
    r.raise_for_status()
    print(json.dumps(r.json(), indent=2))


if __name__ == "__main__":
    publish_sample()
    review("urn:pn:paper:demo-001", "did:pn:axon:1", "approve", 1.0)
    review("urn:pn:paper:demo-001", "did:pn:axon:2", "approve", 1.0)
    review("urn:pn:paper:demo-001", "did:pn:axon:3", "approve", 1.0)
    integrate("urn:pn:paper:demo-001")
    sync()
