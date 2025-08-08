import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Local graph store for persistence
import graph_store

app = FastAPI(title="PN Synapse Alpha", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class DID(BaseModel):
    id: str
    pubkey: Optional[str] = None


class Claim(BaseModel):
    id: str
    text: str
    topic: Optional[str] = None


class Evidence(BaseModel):
    url: Optional[str] = None
    hash: Optional[str] = None
    license: Optional[str] = None


class Repro(BaseModel):
    code_hash: Optional[str] = None
    data_hash: Optional[str] = None
    runner: Optional[str] = None


class GraphPatch(BaseModel):
    op: str
    triple: List[str]


class Paper(BaseModel):
    type: Literal["Paper"] = "Paper"
    id: str
    title: str
    abstract: Optional[str] = None
    authors: Optional[List[DID]] = None
    claims: List[Claim]
    evidence: Optional[List[Evidence]] = None
    graphPatch: Optional[List[GraphPatch]] = None
    repro: Optional[Repro] = None
    provenance: Dict[str, Any]


class Review(BaseModel):
    paper_id: str
    reviewer: DID
    vote: str
    weight: Optional[float] = None
    notes: Optional[str] = None
    topic: Optional[str] = None


class PublishAck(BaseModel):
    paper_id: str
    status: str


class ReviewAck(BaseModel):
    paper_id: str
    accepted: bool
    tally: Dict[str, float]


class BroadcastEvent(BaseModel):
    id: str
    kind: str
    payload: Dict[str, Any]
    created_at: datetime


class IntegrationResult(BaseModel):
    paper_id: str
    integrated: bool
    broadcast_event_id: Optional[str]


# --- In-memory state (events + papers + reviews) ---
db_papers: Dict[str, Paper] = {}
db_reviews: Dict[str, List[Review]] = {}
db_events: List[BroadcastEvent] = []


def approvals_for(reviewer_id: str, topic: Optional[str]) -> int:
    # Count previous APPROVE votes by this reviewer (optionally per topic).
    count = 0
    for _pid, revs in db_reviews.items():
        for r in revs:
            if r.reviewer.id == reviewer_id and r.vote == "approve":
                if topic is None or r.topic == topic or topic == r.topic:
                    count += 1
    return count


def weight_for(did: DID, topic: Optional[str]) -> float:
    """
    Heuristic trust weighting (MVP):
      - Base = 1.0
      - If topic is provided: +0.3
      - Past approves by this reviewer on same topic: +0.1 each (cap total at 2.0)
    """
    base = 1.0
    topic_bonus = 0.3 if topic else 0.0
    prev = approvals_for(did.id, topic)
    hist_bonus = min(prev * 0.1, 0.7)  # cap so base(1.0)+topic(0.3)+hist(0.7) <= 2.0
    return min(base + topic_bonus + hist_bonus, 2.0)


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/publish", response_model=PublishAck, status_code=202)
def publish(paper: Paper):
    if paper.id in db_papers:
        raise HTTPException(409, "paper already exists")
    db_papers[paper.id] = paper
    db_reviews[paper.id] = []
    return PublishAck(paper_id=paper.id, status="queued")


@app.post("/review", response_model=ReviewAck)
def review(r: Review):
    if r.paper_id not in db_papers:
        raise HTTPException(404, "paper not found")
    if r.weight is None:
        # Compute BEFORE appending -> counts only previous approvals
        topic = r.topic or (
            db_papers[r.paper_id].claims[0].topic if db_papers[r.paper_id].claims else None
        )
        r.weight = weight_for(r.reviewer, topic)
    db_reviews[r.paper_id].append(r)
    tally = {"approve": 0.0, "reject": 0.0, "request_changes": 0.0}
    for rev in db_reviews[r.paper_id]:
        tally[rev.vote] += rev.weight or 0.0
    accepted = tally["approve"] >= 3.0 and tally["reject"] < 1.5
    return ReviewAck(paper_id=r.paper_id, accepted=accepted, tally=tally)


def _gardener_ok(api_key: Optional[str]) -> bool:
    secret = GARDENER_TOKEN_OVERRIDE or os.environ.get("GARDENER_TOKEN")
    if not secret:
        return True
    return api_key == secret


@app.post("/integrate/{paper_id}", response_model=IntegrationResult)
def integrate(paper_id: str, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    if not _gardener_ok(x_api_key):
        raise HTTPException(status_code=401, detail="unauthorized: invalid or missing X-API-Key")

    if paper_id not in db_papers:
        raise HTTPException(404, "paper not found")

    tally = {"approve": 0.0, "reject": 0.0, "request_changes": 0.0}
    for rev in db_reviews.get(paper_id, []):
        tally[rev.vote] += rev.weight or 0.0
    if not (tally["approve"] >= 3.0 and tally["reject"] < 1.5):
        raise HTTPException(400, "threshold not reached")

    # Persist graph (apply patches)
    patches = [gp.model_dump() for gp in (db_papers[paper_id].graphPatch or [])]
    if patches:
        graph_store.apply_patches(patches, db_papers[paper_id])

    evt = BroadcastEvent(
        id=os.urandom(8).hex(),
        kind="graph_patch",
        payload={"paper_id": paper_id, "graphPatch": patches},
        created_at=datetime.now(timezone.utc),
    )
    db_events.append(evt)
    return IntegrationResult(paper_id=paper_id, integrated=True, broadcast_event_id=evt.id)


@app.post("/broadcast")
def broadcast(evt: BroadcastEvent):
    db_events.append(evt)
    return {"queued": True, "id": evt.id}


@app.get("/sync")
def sync(since: Optional[str] = None):
    if since:
        try:
            t = datetime.fromisoformat(since)
        except Exception:
            raise HTTPException(400, "bad timestamp")
        events = [e for e in db_events if e.created_at > t]
    else:
        events = db_events
    return {"events": [e.model_dump() for e in events]}
