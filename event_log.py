import json
import os
from typing import Any, Dict, List

PATH = os.environ.get("PN_EVENTS", "events.log.jsonl")


def append_event(ev: Dict[str, Any]) -> None:
    try:
        with open(PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    except Exception:
        # MVP: 失敗は握りつぶす（本番ではロギング推奨）
        pass


def tail(n: int = 100) -> List[Dict[str, Any]]:
    if not os.path.exists(PATH):
        return []
    try:
        with open(PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()[-n:]
        out = []
        for line in lines:
            try:
                out.append(json.loads(line))
            except Exception:
                pass
        return out
    except Exception:
        return []
