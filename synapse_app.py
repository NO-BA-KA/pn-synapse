
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime, timezone
import uuid

app = FastAPI(title="PN Synapse Alpha", version="0.1.0")

from fastapi.middleware.cors import CORSMiddleware
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

db_papers: Dict[str, Paper] = {}
db_reviews: Dict[str, List[Review]] = {}
db_events: List[BroadcastEvent] = []

def weight_for(did: DID, topic: Optional[str]) -> float:
    return 1.0

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
        r.weight = weight_for(r.reviewer, r.topic)
    db_reviews[r.paper_id].append(r)
    tally = {"approve":0.0,"reject":0.0,"request_changes":0.0}
    for rev in db_reviews[r.paper_id]:
        tally[rev.vote] += rev.weight or 0.0
    accepted = tally["approve"] >= 3.0 and tally["reject"] < 1.5
    return ReviewAck(paper_id=r.paper_id, accepted=accepted, tally=tally)

@app.post("/integrate/{paper_id}", response_model=IntegrationResult)
def integrate(paper_id: str):
    if paper_id not in db_papers:
        raise HTTPException(404, "paper not found")
    tally = {"approve":0.0,"reject":0.0,"request_changes":0.0}
    for rev in db_reviews.get(paper_id, []):
        tally[rev.vote] += rev.weight or 0.0
    if not (tally["approve"] >= 3.0 and tally["reject"] < 1.5):
        raise HTTPException(400, "threshold not reached")
    evt = BroadcastEvent(
        id=str(uuid.uuid4()),
        kind="graph_patch",
        payload={"paper_id": paper_id, "graphPatch": [gp.dict() for gp in (db_papers[paper_id].graphPatch or [])]},
        created_at=datetime.now(timezone.utc)
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
    return {"events": [e.dict() for e in events]}
