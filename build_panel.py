"""
광역자치단체 산업진흥비 패널 데이터셋 빌더.

산업진흥비 = 분야 090(산업·중소기업 및 에너지) + 분야 120(과학기술)
회계 범위: 일반회계 + 특별회계 (기금 제외)
값:        결산액 (집행액), 명목 (단위: 천원)
대상:      광역자치단체 17개, 2013~2024년 (12개년)

사용법
------
1) 빈 템플릿만 생성 (숫자는 사용자가 채움):
       python build_panel.py --template-only

2) lofin 원자료(연도별 CSV/XLSX)를 ./raw/ 에 두고 자동 채움:
       python build_panel.py --raw-dir ./raw --out industry_promotion_panel.xlsx

   원자료에 기대하는 컬럼(헤더 자동 매핑):
       자치단체명 | 회계구분 | 분야코드 또는 분야명 | 결산액
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

SIDO = [
    ("11", "서울특별시"),
    ("26", "부산광역시"),
    ("27", "대구광역시"),
    ("28", "인천광역시"),
    ("29", "광주광역시"),
    ("30", "대전광역시"),
    ("31", "울산광역시"),
    ("36", "세종특별자치시"),
    ("41", "경기도"),
    ("42", "강원특별자치도"),
    ("43", "충청북도"),
    ("44", "충청남도"),
    ("45", "전북특별자치도"),
    ("46", "전라남도"),
    ("47", "경상북도"),
    ("48", "경상남도"),
    ("50", "제주특별자치도"),
]
YEARS = list(range(2013, 2025))

COLUMNS = [
    "sido_code",
    "sido",
    "year",
    "expn_090_industry_sme_energy",
    "expn_120_science_technology",
    "industry_promotion_total",
]
COLUMN_LABELS_KR = {
    "sido_code": "시도코드",
    "sido": "시도명",
    "year": "회계연도",
    "expn_090_industry_sme_energy": "090 산업·중소기업 및 에너지(천원)",
    "expn_120_science_technology": "120 과학기술(천원)",
    "industry_promotion_total": "산업진흥비 합계(천원)",
}


def build_skeleton() -> pd.DataFrame:
    rows = [
        {"sido_code": code, "sido": name, "year": y}
        for code, name in SIDO
        for y in YEARS
    ]
    df = pd.DataFrame(rows)
    df["expn_090_industry_sme_energy"] = pd.NA
    df["expn_120_science_technology"] = pd.NA
    df["industry_promotion_total"] = pd.NA
    return df[COLUMNS]


_FIELD_CODE_RE = re.compile(r"\b(0?\d{2,3})\b")


def _normalize_field_code(value) -> str | None:
    if pd.isna(value):
        return None
    s = str(value).strip()
    m = _FIELD_CODE_RE.search(s)
    if m:
        return m.group(1).zfill(3)
    if "산업" in s and "에너지" in s:
        return "090"
    if "과학기술" in s:
        return "120"
    return None


def _detect_column(df: pd.DataFrame, *needles: str) -> str | None:
    for col in df.columns:
        name = str(col)
        if all(n in name for n in needles):
            return col
    return None


def ingest_raw(raw_dir: Path) -> pd.DataFrame:
    """Read every CSV/XLSX in raw_dir and return long-form (sido, year, code, value)."""
    frames = []
    files = sorted(
        [p for p in raw_dir.iterdir() if p.suffix.lower() in {".csv", ".xlsx", ".xls"}]
    )
    if not files:
        raise SystemExit(f"원자료 파일이 {raw_dir} 에 없습니다.")
    for fp in files:
        year_match = re.search(r"(20\d{2})", fp.name)
        if not year_match:
            print(f"[skip] 파일명에서 연도를 못 찾음: {fp.name}")
            continue
        year = int(year_match.group(1))
        if fp.suffix.lower() == ".csv":
            df = pd.read_csv(fp, dtype=str)
        else:
            df = pd.read_excel(fp, dtype=str)

        col_sido = _detect_column(df, "자치단체") or _detect_column(df, "단체명")
        col_acct = _detect_column(df, "회계")
        col_field = (
            _detect_column(df, "분야", "코드")
            or _detect_column(df, "분야명")
            or _detect_column(df, "분야")
        )
        col_value = (
            _detect_column(df, "결산")
            or _detect_column(df, "집행")
            or _detect_column(df, "지출")
        )
        missing = [
            n
            for n, v in [
                ("자치단체", col_sido),
                ("분야", col_field),
                ("결산액", col_value),
            ]
            if v is None
        ]
        if missing:
            print(f"[warn] {fp.name}: 누락 컬럼 {missing} -> 스킵")
            continue

        sub = df[[col_sido, col_field, col_value] + ([col_acct] if col_acct else [])].copy()
        sub.columns = ["sido_raw", "field_raw", "value_raw"] + (["acct"] if col_acct else [])
        sub["field_code"] = sub["field_raw"].map(_normalize_field_code)
        sub = sub[sub["field_code"].isin(["090", "120"])].copy()
        if col_acct:
            sub = sub[sub["acct"].astype(str).str.contains("일반|특별", na=False)]
            sub = sub[~sub["acct"].astype(str).str.contains("기금", na=False)]
        sub["value"] = (
            sub["value_raw"].astype(str).str.replace(",", "", regex=False).str.strip()
        )
        sub["value"] = pd.to_numeric(sub["value"], errors="coerce")
        sub["year"] = year
        frames.append(sub[["sido_raw", "year", "field_code", "value"]])

    long = pd.concat(frames, ignore_index=True)
    long = long.dropna(subset=["value"])
    agg = (
        long.groupby(["sido_raw", "year", "field_code"], as_index=False)["value"]
        .sum()
    )
    return agg


def merge_to_panel(skeleton: pd.DataFrame, agg: pd.DataFrame) -> pd.DataFrame:
    name_to_code = {name: code for code, name in SIDO}

    def match_code(raw: str) -> str | None:
        for full, code in name_to_code.items():
            if full in str(raw) or str(raw) in full:
                return code
            short = full[:2]
            if str(raw).startswith(short):
                return code
        return None

    agg = agg.copy()
    agg["sido_code"] = agg["sido_raw"].map(match_code)
    agg = agg.dropna(subset=["sido_code"])

    wide = agg.pivot_table(
        index=["sido_code", "year"],
        columns="field_code",
        values="value",
        aggfunc="sum",
    ).reset_index()
    wide.columns.name = None
    wide = wide.rename(
        columns={
            "090": "expn_090_industry_sme_energy",
            "120": "expn_120_science_technology",
        }
    )

    panel = skeleton.drop(
        columns=[
            "expn_090_industry_sme_energy",
            "expn_120_science_technology",
            "industry_promotion_total",
        ]
    ).merge(wide, on=["sido_code", "year"], how="left")
    panel["industry_promotion_total"] = panel[
        ["expn_090_industry_sme_energy", "expn_120_science_technology"]
    ].sum(axis=1, min_count=1)
    return panel[COLUMNS]


def write_excel(panel: pd.DataFrame, out_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "panel"

    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(bold=True, color="FFFFFF")
    center = Alignment(horizontal="center", vertical="center")

    for j, col in enumerate(COLUMNS, start=1):
        c = ws.cell(row=1, column=j, value=COLUMN_LABELS_KR[col])
        c.fill = header_fill
        c.font = header_font
        c.alignment = center

    for i, row in enumerate(panel.itertuples(index=False), start=2):
        ws.cell(row=i, column=1, value=row.sido_code).alignment = center
        ws.cell(row=i, column=2, value=row.sido)
        ws.cell(row=i, column=3, value=int(row.year)).alignment = center
        v090 = row.expn_090_industry_sme_energy
        v120 = row.expn_120_science_technology
        if pd.notna(v090):
            ws.cell(row=i, column=4, value=float(v090)).number_format = "#,##0"
        if pd.notna(v120):
            ws.cell(row=i, column=5, value=float(v120)).number_format = "#,##0"
        # 합계는 엑셀 수식으로 — 두 열을 사용자가 수정해도 자동 갱신
        ws.cell(
            row=i,
            column=6,
            value=f"=IFERROR(D{i}+E{i},\"\")",
        ).number_format = "#,##0"

    widths = [10, 18, 10, 28, 22, 22]
    for j, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = "A2"

    meta = wb.create_sheet("README")
    notes = [
        ["항목", "내용"],
        ["대상", "광역자치단체 17개 × 2013~2024 (총 204행)"],
        ["변수", "산업진흥비 = 090 산업·중소기업 및 에너지 + 120 과학기술"],
        ["회계 범위", "일반회계 + 특별회계 (기금 제외)"],
        ["값 종류", "결산액(집행액), 명목, 단위 천원"],
        ["1차 출처", "지방재정365 (https://lofin.mois.go.kr) 「세출예산 분야별 현황」"],
        ["보조 출처", "행안부 「지방자치단체 예산개요」 / KOSIS / 자치단체 세입세출예산서"],
        ["주의 - 행정구역", "강원특별자치도 2023.6 출범, 전북특별자치도 2024.1 출범."
            " 본 패널은 출범 이후 명칭으로 12개년을 통일 표기함."],
        ["주의 - 세종시", "2012.7 출범 이후 자료. 결측 가능성 있음."],
        ["주의 - 실질화", "GDP 디플레이터 적용 시 기준연도 명시 필요. 본 파일은 명목값."],
        ["합계 셀", "F열은 D+E 엑셀 수식. D 또는 E를 수정하면 자동 재계산."],
    ]
    for r, row in enumerate(notes, start=1):
        for c, val in enumerate(row, start=1):
            cell = meta.cell(row=r, column=c, value=val)
            if r == 1:
                cell.fill = header_fill
                cell.font = header_font
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    meta.column_dimensions["A"].width = 18
    meta.column_dimensions["B"].width = 80

    wb.save(out_path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", type=Path, default=None)
    ap.add_argument(
        "--out", type=Path, default=Path("industry_promotion_panel.xlsx")
    )
    ap.add_argument("--template-only", action="store_true")
    args = ap.parse_args()

    panel = build_skeleton()
    if args.raw_dir and not args.template_only:
        agg = ingest_raw(args.raw_dir)
        panel = merge_to_panel(panel, agg)
        filled = panel["expn_090_industry_sme_energy"].notna().sum()
        print(f"채워진 (시도×연도) 셀: {filled}/{len(panel)}")
    write_excel(panel, args.out)
    print(f"작성 완료: {args.out}")


if __name__ == "__main__":
    main()
