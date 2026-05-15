"""전략 추상 베이스. SL/RL/LLM/Ensemble이 구현."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class Signal:
    symbol: str
    action: str           # "buy" | "sell" | "hold"
    strength: float       # 0..1 — 진입 강도
    size_pct: float = 0.0  # 자본 대비 진입 비중 (0..1)
    rationale: str = ""


class Strategy(ABC):
    @abstractmethod
    def generate(self, market_state: dict[str, Any]) -> list[Signal]:
        """현재 시장 상태(가격·피처·뉴스 등)로부터 종목별 시그널 생성."""
