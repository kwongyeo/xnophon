"""중앙 설정 — 환경변수·기본값·경로 유틸.

env 읽기와 기본값이 여러 모듈에 흩어지지 않도록 한곳에 모은다.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# --- 기본값 ---
DEFAULT_FROM_YEAR = 2020
DEFAULT_PER_COUNTRY = 25
DEFAULT_KCI_COUNT = 20
DEFAULT_MODEL = "claude-opus-4-7"
DEFAULT_OPENALEX_EMAIL = "kwongyeo@gmail.com"

RESULTS_DIR = Path("results")
CACHE_DIRNAME = ".cache"


# --- 환경변수 접근자 ---
def openalex_email() -> str:
    return os.environ.get("OPENALEX_EMAIL", DEFAULT_OPENALEX_EMAIL)


def anthropic_key() -> str | None:
    return os.environ.get("ANTHROPIC_API_KEY")


def kci_key() -> str | None:
    return os.environ.get("KCI_API_KEY")


# --- 경로 유틸 ---
_SLUG_STRIP = re.compile(r"[^\w가-힣]+", re.UNICODE)


def slugify(topic: str) -> str:
    """주제어를 파일시스템 안전한 slug로. 한글은 보존, 공백·기호는 '-'로."""
    s = _SLUG_STRIP.sub("-", (topic or "").strip()).strip("-").lower()
    return s[:60] or "untitled"


def topic_dir(topic: str, base: Path = RESULTS_DIR) -> Path:
    """주제별 작업 디렉터리: results/<slug>/. 여러 주제를 돌려도 덮어쓰지 않는다."""
    return base / slugify(topic)


def cache_dir(base: Path = RESULTS_DIR) -> Path:
    return base / CACHE_DIRNAME


def _repo_root() -> Path:
    # src/literature_review/config.py → 저장소 루트.
    return Path(__file__).resolve().parent.parent.parent


def assets_dir() -> Path:
    return _repo_root() / "assets"


def prompt_path(name: str) -> Path:
    return assets_dir() / "prompts" / name


def load_prompt(name: str, fallback: str = "") -> str:
    """assets/prompts/<name> 을 읽고, 없으면 fallback을 반환."""
    path = prompt_path(name)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return fallback
