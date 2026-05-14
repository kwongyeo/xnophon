"""광역자치단체 17개 코드 매핑.

하나의 진실 소스로, 행정표준코드(adm)와 KOSIS objL1 코드를 함께 보관한다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Sido:
    adm_code: str    # 행정표준코드 (lofin·jumin 사용)
    kosis_code: str  # KOSIS objL1
    name: str        # 정식 명칭(2024 기준 — 강원·전북 특별자치도 반영)


SIDO: list[Sido] = [
    Sido("11", "11", "서울특별시"),
    Sido("26", "21", "부산광역시"),
    Sido("27", "22", "대구광역시"),
    Sido("28", "23", "인천광역시"),
    Sido("29", "24", "광주광역시"),
    Sido("30", "25", "대전광역시"),
    Sido("31", "26", "울산광역시"),
    Sido("36", "29", "세종특별자치시"),
    Sido("41", "31", "경기도"),
    Sido("42", "32", "강원특별자치도"),
    Sido("43", "33", "충청북도"),
    Sido("44", "34", "충청남도"),
    Sido("45", "35", "전북특별자치도"),
    Sido("46", "36", "전라남도"),
    Sido("47", "37", "경상북도"),
    Sido("48", "38", "경상남도"),
    Sido("50", "39", "제주특별자치도"),
]


def by_adm(code: str) -> Sido | None:
    return next((s for s in SIDO if s.adm_code == code), None)


def match_name(raw: str) -> Sido | None:
    """원자료 텍스트에서 시도 매칭.  '서울', '서울특별시', '서울시' 등 변형 허용."""
    raw = str(raw).strip()
    for s in SIDO:
        if s.name in raw or raw in s.name or raw.startswith(s.name[:2]):
            return s
    return None


YEARS_DEFAULT = list(range(2013, 2025))
