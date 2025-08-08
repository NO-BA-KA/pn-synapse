import os
import pytest
import synapse_app

@pytest.fixture(autouse=True)
def reset_guard():
    # 各テストの開始前/終了後にRBACを無効化（開発モード）
    synapse_app.GARDENER_TOKEN_OVERRIDE = None
    os.environ.pop("GARDENER_TOKEN", None)
    yield
    synapse_app.GARDENER_TOKEN_OVERRIDE = None
    os.environ.pop("GARDENER_TOKEN", None)
