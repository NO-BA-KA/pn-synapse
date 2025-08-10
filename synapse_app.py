from __future__ import annotations

import hashlib as _hashlib
import hmac as _hmac
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import event_log  # 追加
import graph_store  # type: ignore

# ---- 設定（デフォルト） ----
CONFIG: Dict[str, float] = {
    "base_weight": 1.0,
    "topic_bonus": 0.3,
    "history_bonus": 0.1,
    "max_weight": 2.0,
    "approve_threshold": 3.0,
    "reject_cap": 1.5,
}

# RBAC override（テスト・開発用）
GARDENER_TOKEN_OVERRIDE: Optional[str] = None

app = FastAPI(title="PN Synapse Alpha (JA)", version="0.3.1")

# CORS（ローカルUI想定）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- モデル ----
class Claim(BaseModel):
    id: str
    text: Optional[str] = None
    topic: Optional[str] = None


class Paper(BaseModel):
    type: Literal["Paper"] = "Paper"
    id: str
    title: Optional[str] = None
    claims: List[Claim] = []
    graphPatch: List[Dict[str, Any]] = []
    provenance: Dict[str, Any] = {}


class Reviewer(BaseModel):
    id: str


class ReviewIn(BaseModel):
    paper_id: str
    reviewer: Reviewer
    vote: Literal["approve", "reject", "request_changes"]
    topic: Optional[str] = None
    weight: Optional[float] = None  # 明示指定があれば優先（MVP）


class ReviewRecord(BaseModel):
    reviewer: Reviewer
    vote: Literal["approve", "reject", "request_changes"]
    topic: Optional[str] = None
    weight: float
    at: datetime


# ---- 疑似DB（メモリ）----
db_papers: Dict[str, Paper] = {}
db_reviews: Dict[str, List[ReviewRecord]] = {}
events: List[Dict[str, Any]] = []


# ---- ユーティリティ ----
def approvals_for(reviewer_id: str, topic: Optional[str]) -> int:
    if not topic:
        return 0
    n = 0
    for revs in db_reviews.values():
        for r in revs:
            if r.reviewer.id == reviewer_id and r.topic == topic and r.vote == "approve":
                n += 1
    return n


def weight_for(reviewer_id: str, topic: Optional[str]) -> float:
    base = CONFIG["base_weight"]
    bonus = 0.0
    if topic:
        bonus += CONFIG["topic_bonus"]
        bonus += approvals_for(reviewer_id, topic) * CONFIG["history_bonus"]
    w = min(base + bonus, CONFIG["max_weight"])
    return float(w)


def _gardener_ok(api_key: Optional[str]) -> bool:
    secret = globals().get("GARDENER_TOKEN_OVERRIDE") or os.environ.get("GARDENER_TOKEN")
    if not secret:
        return True
    return api_key == secret


def _verify_hmac_if_required(raw_body: bytes, x_sig: Optional[str]) -> None:
    secret = os.environ.get("SIGNING_SECRET")
    if not secret:
        return
    if not x_sig:
        raise HTTPException(status_code=401, detail="署名が必要です（X-Sig ヘッダがありません）")
    mac = _hmac.new(secret.encode("utf-8"), raw_body, _hashlib.sha256).hexdigest()
    if not _hmac.compare_digest(mac, x_sig):
        raise HTTPException(status_code=401, detail="署名が不正です（X-Sig 不一致）")


def _tally(paper_id: str) -> Dict[str, float]:
    tally = {"approve": 0.0, "reject": 0.0, "request_changes": 0.0}
    for r in db_reviews.get(paper_id, []):
        tally[r.vote] += r.weight
    return tally


# ---- エンドポイント ----
@app.post("/publish", status_code=202)
async def publish(request: Request, x_sig: Optional[str] = Header(default=None, alias="X-Sig")):
    raw = await request.body()
    _verify_hmac_if_required(raw, x_sig)
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSONが読み込めませんでした")
    try:
        paper = Paper.model_validate(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Paperの形式が不正: {e}")
    db_papers[paper.id] = paper
    return {"paper_id": paper.id, "status": "queued"}


@app.post("/review")
async def review(request: Request, x_sig: Optional[str] = Header(default=None, alias="X-Sig")):
    raw = await request.body()
    _verify_hmac_if_required(raw, x_sig)
    data = await request.json()
    try:
        r_in = ReviewIn.model_validate(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Reviewの形式が不正: {e}")
    w = r_in.weight if r_in.weight is not None else weight_for(r_in.reviewer.id, r_in.topic)
    rec = ReviewRecord(
        reviewer=r_in.reviewer,
        vote=r_in.vote,
        topic=r_in.topic,
        weight=w,
        at=datetime.now(timezone.utc),
    )
    db_reviews.setdefault(r_in.paper_id, []).append(rec)
    tally = _tally(r_in.paper_id)
    accepted = (
        tally["approve"] >= CONFIG["approve_threshold"] and tally["reject"] < CONFIG["reject_cap"]
    )
    return {"paper_id": r_in.paper_id, "accepted": accepted, "tally": tally}


@app.post("/integrate/{paper_id}")
async def integrate(
    paper_id: str, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")
):
    if not _gardener_ok(x_api_key):
        raise HTTPException(status_code=401, detail="unauthorized: invalid or missing X-API-Key")

    paper = db_papers.get(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paperが見つかりません")
    tally = _tally(paper_id)
    if not (
        tally["approve"] >= CONFIG["approve_threshold"] and tally["reject"] < CONFIG["reject_cap"]
    ):
        raise HTTPException(status_code=400, detail="閾値未達のため統合できません")

    # グラフ永続化
    graph_store.apply_patches(paper.graphPatch or [], paper)  # type: ignore

    # イベント生成＆永続化
    ev = {
        "id": _hashlib.sha256(
            f"{paper_id}{datetime.now(timezone.utc).isoformat()}".encode("utf-8")
        ).hexdigest()[:16],
        "kind": "graph_patch",
        "payload": {"paper_id": paper_id, "graphPatch": paper.graphPatch},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    events.append(ev)
    event_log.append_event(ev)

    return {"paper_id": paper_id, "integrated": True, "broadcast_event_id": ev["id"]}


@app.get("/sync")
def sync(since: Optional[str] = None):
    # MVP: sinceは未使用で全件返す
    return {"events": events}


# ★ ここから可視化用エンドポイント
@app.get("/tally/{paper_id}")
def tally_api(paper_id: str):
    return {"paper_id": paper_id, "tally": _tally(paper_id)}


@app.get("/graph/edges")
def graph_edges():
    return {"edges": graph_store.list_edges()}


@app.get("/graph/claims")
def graph_claims():
    return {"claims": graph_store.list_claims()}


@app.get("/debug/db")
def debug_db():
    return graph_store.debug_info()


@app.get("/events")
def events_tail(n: int = 100):
    return {"events": event_log.tail(n)}


# 管理系
class ConfigIn(BaseModel):
    base_weight: Optional[float] = None
    topic_bonus: Optional[float] = None
    history_bonus: Optional[float] = None
    max_weight: Optional[float] = None
    approve_threshold: Optional[float] = None
    reject_cap: Optional[float] = None


@app.get("/admin/config")
def get_config(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    if not _gardener_ok(x_api_key):
        raise HTTPException(status_code=401, detail="unauthorized")
    return {"config": CONFIG}


@app.post("/admin/config")
def set_config(body: ConfigIn, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    if not _gardener_ok(x_api_key):
        raise HTTPException(status_code=401, detail="unauthorized")
    for k, v in body.model_dump(exclude_none=True).items():
        if not isinstance(v, (int, float)):
            raise HTTPException(status_code=400, detail=f"{k} は数値で指定してください")
        CONFIG[k] = float(v)
    return {"config": CONFIG}


# ヘルス
@app.get("/health")
def health():
    return {"ok": True, "time": datetime.now(timezone.utc).isoformat()}


@app.get("/healthz")
def healthz():
    return health()
