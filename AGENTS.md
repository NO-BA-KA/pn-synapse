
# AGENTS.md — Guide for Codex Agents (pn-synapse)

## Project overview
PN Synapse Alpha: centralized, internal-only knowledge hub with review → integration → broadcast.

### Key entry points
- `synapse_app.py` — FastAPI app: `/publish`, `/review`, `/integrate/{paper_id}`, `/sync`
- `axon_client.py` — demo client
- `schemas/` — JSON Schemas

## Ground rules for Codex
- Python **3.11+**.
- Lint: `ruff` / Tests: `pytest`.
- Do not create new branches; commit to current branch (CI runs).
- Small atomic commits with clear messages.
- If adding deps, update `requirements.txt`.

## Local commands
```bash
make setup      # venv + deps
make dev        # run API
make test       # pytest
make lint       # ruff check
make format     # ruff format
```

## Tests
- `tests/test_health.py` — `/healthz` must return `{"ok": true}`
- `tests/test_review_threshold.py` — approve≥3.0 and reject<1.5 integrates

## Tasks you can take
1) Trust weighting in `weight_for(did, topic)`
2) Graph persistence (Neo4j or file-backed) and apply `graphPatch`
3) Signed requests & RBAC for `/integrate/*`
4) Repro gate policy + `/policy` endpoint
