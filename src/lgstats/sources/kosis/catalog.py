"""KOSIS 통계표 변수 정의.

각 KosisVar 는 패널의 한 컬럼이 되며, KOSIS 「통계자료」 API 호출 파라미터를 캡슐화한다.
실제 tbl_id / itm_id 는 운영상 변경될 수 있으므로 사용 전 `lgstats discover` 로 검증 권장.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class KosisVar:
    var_name: str
    label_kr: str
    org_id: str
    tbl_id: str
    itm_id: str
    prd_se: str = "Y"
    obj_l2: str | None = None
    obj_l3: str | None = None
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


DEFAULT_VARS: list[KosisVar] = [
    KosisVar(
        var_name="pop_total",
        label_kr="총인구(주민등록, 명)",
        org_id="101",
        tbl_id="DT_1B040A3",
        itm_id="T20",
        notes="행정안전부 주민등록인구통계, 연말 기준.",
    ),
    KosisVar(
        var_name="pop_elderly_65plus",
        label_kr="65세 이상 인구(명)",
        org_id="101",
        tbl_id="DT_1B040A3",
        itm_id="T20",
        obj_l2="65PLUS",
        notes="동일 표 65+ 분류. obj_l2 코드 검증 필요.",
    ),
    KosisVar(
        var_name="basic_livelihood_recipients",
        label_kr="기초생활보장 수급자(명)",
        org_id="117",
        tbl_id="DT_117N_A0021",
        itm_id="T1",
        notes="보건복지부. 표 ID 연도별 개편 가능 — discover 권장.",
    ),
]
