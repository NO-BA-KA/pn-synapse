import os

import pytest

import synapse_app

# 既定の重み・閾値
_DEFAULT_CONFIG = {
    "base_weight": 1.0,
    "topic_bonus": 0.3,
    "history_bonus": 0.1,
    "max_weight": 2.0,
    "approve_threshold": 3.0,
    "reject_cap": 1.5,
}


@pytest.fixture(autouse=True)
def reset_config():
    """各テストの開始時に既定の係数へ戻す。"""
    synapse_app.CONFIG.update(_DEFAULT_CONFIG)
    yield


@pytest.fixture(autouse=True)
def clear_gardener_token():
    """RBAC鍵を毎テスト初期化（テスト間の状態漏れ防止）。"""
    synapse_app.GARDENER_TOKEN_OVERRIDE = None
    os.environ.pop("GARDENER_TOKEN", None)
    yield
