import importlib
import importlib.util
import os
import pathlib
import sys

import pytest


def _load_synapse_app():
    """
    CI 等で import 解決がズレた場合でも、リポ直下の synapse_app.py を強制ロードする。
    """
    mod = None
    try:
        mod = importlib.import_module("synapse_app")
    except Exception:
        mod = None

    need_force = mod is None or not hasattr(mod, "app") or not hasattr(mod, "CONFIG")
    if need_force:
        root = pathlib.Path(__file__).resolve().parents[1]
        target = root / "synapse_app.py"
        spec = importlib.util.spec_from_file_location("synapse_app", str(target))
        mod = importlib.util.module_from_spec(spec)  # type: ignore
        sys.modules["synapse_app"] = mod  # type: ignore
        assert spec and spec.loader
        spec.loader.exec_module(mod)  # type: ignore
    return mod


synapse_app = _load_synapse_app()

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
def clear_secrets_and_rbac():
    """毎テストで鍵類を初期化（状態の持ち越し防止）"""
    synapse_app.GARDENER_TOKEN_OVERRIDE = None
    os.environ.pop("GARDENER_TOKEN", None)
    os.environ.pop("SIGNING_SECRET", None)
    yield
