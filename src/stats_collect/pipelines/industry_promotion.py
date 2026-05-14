"""광역 17 × 2013–2024 산업진흥비 패널 빌더.

산업진흥비 = 분야 090(산업·중소기업 및 에너지) + 분야 120(과학기술)
회계 범위:  일반회계 + 특별회계 (기금 제외)
값:         결산액(집행액), 명목, 단위 천원
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from stats_collect.common.io import write_panel_xlsx
from stats_collect.common.sido import SIDO, YEARS_DEFAULT
from stats_collect.sources.lofin.fields import INDUSTRY_PROMOTION_CODES
from stats_collect.sources.lofin.parser import ingest_dir


COLUMNS = [
    "sido_code",
    "sido",
    "year",
    "expn_090_industry_sme_energy",
    "expn_120_science_technology",
    "industry_promotion_total",
]
HEADERS_KR = {
    "sido_code": "시도코드",
    "sido": "시도명",
    "year": "회계연도",
    "expn_090_industry_sme_energy": "090 산업·중소기업 및 에너지(천원)",
    "expn_120_science_technology": "120 과학기술(천원)",
    "industry_promotion_total": "산업진흥비 합계(천원)",
}


def build_skeleton() -> pd.DataFrame:
    rows = [
        {"sido_code": s.adm_code, "sido": s.name, "year": y}
        for s in SIDO
        for y in YEARS_DEFAULT
    ]
    df = pd.DataFrame(rows)
    df["expn_090_industry_sme_energy"] = pd.NA
    df["expn_120_science_technology"] = pd.NA
    df["industry_promotion_total"] = pd.NA
    return df[COLUMNS]


def merge(skeleton: pd.DataFrame, agg: pd.DataFrame) -> pd.DataFrame:
    agg = agg[agg["field_code"].isin(INDUSTRY_PROMOTION_CODES)]
    wide = agg.pivot_table(
        index=["sido_code", "year"],
        columns="field_code",
        values="value",
        aggfunc="sum",
    ).reset_index()
    wide.columns.name = None
    wide = wide.rename(columns={
        "090": "expn_090_industry_sme_energy",
        "120": "expn_120_science_technology",
    })
    panel = skeleton.drop(columns=[
        "expn_090_industry_sme_energy",
        "expn_120_science_technology",
        "industry_promotion_total",
    ]).merge(wide, on=["sido_code", "year"], how="left")
    panel["industry_promotion_total"] = panel[[
        "expn_090_industry_sme_energy",
        "expn_120_science_technology",
    ]].sum(axis=1, min_count=1)
    return panel[COLUMNS]


def run(raw_dir: Path | None, out: Path) -> None:
    panel = build_skeleton()
    if raw_dir is not None:
        agg = ingest_dir(raw_dir)
        panel = merge(panel, agg)
        filled = panel["expn_090_industry_sme_energy"].notna().sum()
        print(f"채워진 (시도×연도) 셀: {filled}/{len(panel)}")

    readme = [
        ("대상", "광역 17개 × 2013~2024 (204행)"),
        ("정의", "산업진흥비 = 090 산업·중소기업 및 에너지 + 120 과학기술"),
        ("회계 범위", "일반+특별 (기금 제외)"),
        ("값", "결산액(집행액), 명목, 단위 천원"),
        ("출처", "지방재정365 (lofin.mois.go.kr) 「세출예산 분야별 현황」"),
        ("합계 셀", "F열은 D+E 엑셀 수식 — 두 열 수정 시 자동 갱신"),
        ("주의", "강원특별자치도(2023.6) / 전북특별자치도(2024.1) 출범 — 명칭 통일 표기"),
    ]
    write_panel_xlsx(
        panel, out,
        headers_kr=HEADERS_KR,
        column_order=COLUMNS,
        formula_columns={"industry_promotion_total":
                         "=IFERROR(D{r}+E{r},\"\")"},
        readme_rows=readme,
        column_widths=[10, 18, 10, 28, 22, 22],
    )
    print(f"작성 완료: {out}")
