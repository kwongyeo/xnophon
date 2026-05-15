"""브로커 추상 인터페이스. paper_broker / kis_broker가 구현."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Order:
    symbol: str
    side: str                  # "buy" | "sell"
    quantity: int
    order_type: str = "market"  # "market" | "limit"
    limit_price: float | None = None
    market: str = "kr"          # "kr" | "us"


@dataclass
class Fill:
    order: Order
    fill_price: float
    fill_quantity: int
    timestamp: str
    commission: float = 0.0


class Broker(ABC):
    @abstractmethod
    def submit(self, order: Order) -> Fill:
        """주문 제출 후 체결 결과 반환."""

    @abstractmethod
    def cash(self) -> dict[str, float]:
        """통화별 현금 잔고. 예: {'KRW': 5_000_000, 'USD': 3_200}."""

    @abstractmethod
    def positions(self) -> dict[str, int]:
        """심볼별 보유 수량."""

    @abstractmethod
    def cancel(self, order_id: str) -> bool:
        """미체결 주문 취소."""
