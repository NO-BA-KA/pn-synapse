import os

import pytest


def _load_synapse_app():
    """
    CI等で import 解決がズレた場合でも、リポ直下の synapse_app.py を強制ロードする。
    ※ import は関数内に閉じ込め、トップの import を最小化（Ruff I001対策）
    """
    import importlib
    import importlib.util
    import pathlib
    import sys

    try:
        mod = importlib.import_module("synapse_app")
    except Exception:
        mod = None

    need_force = mod is None or not hasattr(mod, "app")
    if need_force:
        root = pathlib.Path(__file__).resolve().parents[1]
        target = root / "synapse_app.py"
        spec = importlib.util.spec_from_file_location("synapse_app", str(target))
        mod = importlib.util.module_from_spec(spec)  # type: ignore
        sys.modules["synapse_app"] = mod  # type: ignore
        assert spec and spec.loader
        spec.loader.exec_module(mod)  # type: ignore
    return mod


def _ensure_defaults(mod):
    """CONFIG/GARDENER_TOKEN_OVERRIDE が無くてもテストが回るように既定値を注入。"""
    default_config = {
        "base_weight": 1.0,
        "topic_bonus": 0.3,
        "history_bonus": 0.1,
        "max_weight": 2.0,
        "approve_threshold": 3.0,
        "reject_cap": 1.5,
    }
    if not hasattr(mod, "CONFIG") or not isinstance(getattr(mod, "CONFIG"), dict):
        setattr(mod, "CONFIG", dict(default_config))
    else:
        # 欠けているキーだけ補完
        for k, v in default_config.items():
            mod.CONFIG.setdefault(k, v)

    if not hasattr(mod, "GARDENER_TOKEN_OVERRIDE"):
        mod.GARDENER_TOKEN_OVERRIDE = None

    return default_config


synapse_app = _load_synapse_app()
_DEFAULT_CONFIG = _ensure_defaults(synapse_app)


@pytest.fixture(autouse=True)
def reset_config():
    """各テストの開始時に既定の係数へ戻す。"""
    # 念のため存在保証
    _ensure_defaults(synapse_app)
    synapse_app.CONFIG.update(_DEFAULT_CONFIG)
    yield


@pytest.fixture(autouse=True)
def clear_secrets_and_rbac():
    """毎テストで鍵類を初期化（状態の持ち越し防止）"""
    # 念のため存在保証
    _ensure_defaults(synapse_app)
    synapse_app.GARDENER_TOKEN_OVERRIDE = None
    os.environ.pop("GARDENER_TOKEN", None)
    os.environ.pop("SIGNING_SECRET", None)
    yield
