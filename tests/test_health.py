import importlib
from fastapi.testclient import TestClient

app_module = importlib.import_module("synapse_app")
app = getattr(app_module, "app")
client = TestClient(app)


def test_health():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json().get("ok") is True
