"""config.yaml 로더.

모든 모듈은 여기서 설정을 읽어 동작을 결정한다.
설정을 코드에 하드코딩하지 말 것 — 재현성과 실험 추적을 위해 항상 config 경유.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "config" / "config.yaml"


def load_config(path: str | Path = DEFAULT_PATH) -> dict[str, Any]:
    """YAML 설정을 dict로 로드한다."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
