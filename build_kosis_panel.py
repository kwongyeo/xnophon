"""
KOSIS 기반 광역자치단체 사회·인구 패널 빌더.

수집 변수 (config 블록에서 자유롭게 추가/수정 가능)
- 총인구 (주민등록인구)
- 65세 이상 노인인구
- 기초생활보장 수급자 수

대상: 광역자치단체 17개 × 2013~2024년
출처: KOSIS 공유서비스 Open API (https://kosis.kr/openapi)

사용 전 준비
------------
1. https://kosis.kr 회원가입 → 마이페이지 > Open API 신청 → 활용 키 발급
2. 환경변수 설정:
       export KOSIS_API_KEY="발급받은_키"

사용법
------
# (1) 키워드로 통계표 검색 — tblId, orgId 확인용
python build_kosis_panel.py discover --keyword "주민등록인구"

# (2) 기본 변수 3종 패널 빌드
python build_kosis_panel.py build --out kosis_panel.xlsx

# (3) 설정 파일로 변수 추가/교체
python build_kosis_panel.py build --config kosis_vars.json --out kosis_panel.xlsx

설계 메모
---------
- KOSIS 「통계자료」 서비스는 (orgId, tblId, objL1=시도코드, itmId, prdSe, startPrdDe, endPrdDe)
  파라미터로 호출. 시도 코드 체계는 행정표준코드와 다름 — 본 스크립트의 KOSIS_SIDO 표 참조.
- 통계표마다 분류·항목 코드가 다르므로, 새 변수를 추가하려면 먼저 discover 로 구조 확인 권장.
- 본 스크립트는 결과를 long → wide 패널(시도×연도, 변수별 컬럼)로 정리해 xlsx 출력.
- 숫자값을 절대 추정·생성하지 않음. API가 빈 결과를 반환하면 해당 셀은 비어 있음.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

import pandas as pd

try:
    import PublicDataReader as pdr
except ImportError:
    sys.exit("PublicDataReader 가 필요합니다: pip install PublicDataReader")

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


# 행정표준코드(좌) ↔ KOSIS objL1 시도코드(우)
KOSIS_SIDO = [
    ("11", "11", "서울특별시"),
    ("26", "21", "부산광역시"),
    ("27", "22", "대구광역시"),
    ("28", "23", "인천광역시"),
    ("29", "24", "광주광역시"),
    ("30", "25", "대전광역시"),
    ("31", "26", "울산광역시"),
    ("36", "29", "세종특별자치시"),
    ("41", "31", "경기도"),
    ("42", "32", "강원특별자치도"),
    ("43", "33", "충청북도"),
    ("44", "34", "충청남도"),
    ("45", "35", "전북특별자치도"),
    ("46", "36", "전라남도"),
    ("47", "37", "경상북도"),
    ("48", "38", "경상남도"),
    ("50", "39", "제주특별자치도"),
]
YEARS = list(range(2013, 2025))


@dataclass
class KosisVar:
    """하나의 KOSIS 통계표에서 한 변수(=하나의 컬럼)를 가져오기 위한 설정."""

    var_name: str          # 패널 컬럼명 (영문 권장)
    label_kr: str          # 엑셀 헤더 한글 라벨
    org_id: str            # 통계기관 코드 (101=통계청, 117=보건복지부 등)
    tbl_id: str            # 통계표 ID
    itm_id: str            # 항목 코드
    prd_se: str = "Y"      # 수록주기: Y(연), Q(분기), M(월)
    obj_l2: str | None = None  # 분류2 (연령 등)
    obj_l3: str | None = None
    notes: str = ""


# 기본 변수 3종.  ⚠️ tbl_id / itm_id 는 KOSIS 운영상 변경될 수 있어 1회 discover 로 검증 권장.
DEFAULT_VARS: list[KosisVar] = [
    KosisVar(
        var_name="pop_total",
        label_kr="총인구(주민등록, 명)",
        org_id="101",
        tbl_id="DT_1B040A3",     # 행정구역(시군구)별/성별 인구 — 연말기준
        itm_id="T20",            # 총인구 (성별=계)
        prd_se="Y",
        notes="행정안전부 주민등록인구통계. 연말 기준.",
    ),
    KosisVar(
        var_name="pop_elderly_65plus",
        label_kr="65세 이상 인구(명)",
        org_id="101",
        tbl_id="DT_1B040A3",
        itm_id="T20",
        prd_se="Y",
        obj_l2="65PLUS",         # ※ 실제 연령 분류 코드는 discover 로 확인 후 교체
        notes="동일 표에서 65+ 분류 합산. obj_l2 코드 검증 필요.",
    ),
    KosisVar(
        var_name="basic_livelihood_recipients",
        label_kr="기초생활보장 수급자(명)",
        org_id="117",
        tbl_id="DT_117N_A0021",  # 시도별 기초생활보장 수급 가구·인원
        itm_id="T1",
        prd_se="Y",
        notes="보건복지부. 표 ID는 연도별 개편 가능 — discover 권장.",
    ),
]


def _client() -> "pdr.Kosis":
    key = os.environ.get("KOSIS_API_KEY")
    if not key:
        sys.exit(
            "환경변수 KOSIS_API_KEY 가 비어 있습니다.\n"
            "  export KOSIS_API_KEY='발급받은_키'  후 재실행하세요."
        )
    return pdr.Kosis(service_key=key)


def cmd_discover(args: argparse.Namespace) -> None:
    """키워드로 KOSIS 통계표 검색해 (orgId, tblId, 통계표명) 확인."""
    k = _client()
    df = k.get_data(
        "KOSIS통합검색",
        searchNm=args.keyword,
        startCount=str(args.start),
        resultCount=str(args.limit),
    )
    if df is None or df.empty:
        print("검색 결과 없음.")
        return
    keep = [c for c in df.columns if any(t in c for t in
            ["기관", "통계표", "표명", "ID", "코드", "분류", "수록", "주기"])]
    cols = keep or list(df.columns)
    print(df[cols].to_string(index=False, max_rows=args.limit))


def fetch_var(client: "pdr.Kosis", v: KosisVar, sido_kosis_code: str,
              start_year: int, end_year: int) -> pd.DataFrame:
    """단일 시도 × 단일 변수 시계열 조회."""
    params = dict(
        orgId=v.org_id,
        tblId=v.tbl_id,
        objL1=sido_kosis_code,
        itmId=v.itm_id,
        prdSe=v.prd_se,
        startPrdDe=str(start_year),
        endPrdDe=str(end_year),
    )
    if v.obj_l2:
        params["objL2"] = v.obj_l2
    if v.obj_l3:
        params["objL3"] = v.obj_l3
    df = client.get_data("통계자료", **params)
    if df is None or df.empty:
        return pd.DataFrame(columns=["year", v.var_name])
    # PublicDataReader 가 한글 컬럼명으로 번역 → '수록시점', '수치값' 표준 컬럼
    year_col = next((c for c in df.columns if "수록" in c or "시점" in c), None)
    val_col = next((c for c in df.columns if c in ("수치값", "DT")), None)
    if year_col is None or val_col is None:
        return pd.DataFrame(columns=["year", v.var_name])
    out = df[[year_col, val_col]].copy()
    out.columns = ["year", v.var_name]
    out["year"] = pd.to_numeric(out["year"], errors="coerce").astype("Int64")
    out[v.var_name] = pd.to_numeric(out[v.var_name], errors="coerce")
    return out.dropna(subset=["year"])


def build_panel(vars_: list[KosisVar]) -> pd.DataFrame:
    client = _client()
    rows = []
    for adm_code, kosis_code, name in KOSIS_SIDO:
        merged = pd.DataFrame({"year": YEARS})
        for v in vars_:
            try:
                series = fetch_var(client, v, kosis_code, YEARS[0], YEARS[-1])
            except Exception as e:
                print(f"[warn] {name} {v.var_name}: {e}")
                series = pd.DataFrame(columns=["year", v.var_name])
            merged = merged.merge(series, on="year", how="left")
        merged.insert(0, "sido", name)
        merged.insert(0, "sido_code", adm_code)
        rows.append(merged)
        print(f"  ✓ {name}")
    return pd.concat(rows, ignore_index=True)


def write_excel(panel: pd.DataFrame, vars_: list[KosisVar], out: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "panel"
    fill = PatternFill("solid", fgColor="1F4E78")
    font = Font(bold=True, color="FFFFFF")
    center = Alignment(horizontal="center", vertical="center")

    headers = ["시도코드", "시도명", "회계연도"] + [v.label_kr for v in vars_]
    for j, h in enumerate(headers, start=1):
        c = ws.cell(row=1, column=j, value=h)
        c.fill, c.font, c.alignment = fill, font, center

    for i, row in enumerate(panel.itertuples(index=False), start=2):
        ws.cell(row=i, column=1, value=row.sido_code).alignment = center
        ws.cell(row=i, column=2, value=row.sido)
        ws.cell(row=i, column=3, value=int(row.year)).alignment = center
        for j, v in enumerate(vars_, start=4):
            val = getattr(row, v.var_name, None)
            if pd.notna(val):
                ws.cell(row=i, column=j, value=float(val)).number_format = "#,##0"

    widths = [10, 18, 10] + [22] * len(vars_)
    for j, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = "A2"

    meta = wb.create_sheet("README")
    info = [
        ["항목", "내용"],
        ["대상", f"광역자치단체 17개 × {YEARS[0]}~{YEARS[-1]} (총 {17*len(YEARS)}행)"],
        ["출처", "KOSIS 공유서비스 Open API"],
        ["주의", "강원특별자치도(2023.6) / 전북특별자치도(2024.1) 출범 — 명칭 통일 표기."],
        ["주의", "세종(2012.7 출범) — 일부 표 결측 가능."],
        ["변수 목록", ""],
    ]
    for v in vars_:
        info.append([v.label_kr, f"orgId={v.org_id} tblId={v.tbl_id} itmId={v.itm_id} | {v.notes}"])
    for r, row in enumerate(info, start=1):
        for c, val in enumerate(row, start=1):
            cell = meta.cell(row=r, column=c, value=val)
            if r == 1:
                cell.fill, cell.font = fill, font
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    meta.column_dimensions["A"].width = 28
    meta.column_dimensions["B"].width = 90
    wb.save(out)


def cmd_build(args: argparse.Namespace) -> None:
    if args.config:
        raw = json.loads(Path(args.config).read_text(encoding="utf-8"))
        vars_ = [KosisVar(**d) for d in raw]
    else:
        vars_ = DEFAULT_VARS

    print(f"변수 {len(vars_)}개 수집 시작 (대상 {len(KOSIS_SIDO)} 시도)")
    panel = build_panel(vars_)
    write_excel(panel, vars_, Path(args.out))
    filled_cols = [v.var_name for v in vars_]
    print(f"\n작성 완료: {args.out}")
    print("결측률(%):")
    for c in filled_cols:
        miss = panel[c].isna().mean() * 100 if c in panel.columns else 100.0
        print(f"  {c:35s} {miss:5.1f}%")


def cmd_export_config(args: argparse.Namespace) -> None:
    """기본 변수 설정을 JSON 으로 내보내 — 사용자가 편집해 --config 로 재투입."""
    Path(args.out).write_text(
        json.dumps([asdict(v) for v in DEFAULT_VARS], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"기본 설정 내보냄: {args.out}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    pd_ = sub.add_parser("discover", help="키워드로 KOSIS 통계표 검색")
    pd_.add_argument("--keyword", required=True)
    pd_.add_argument("--start", type=int, default=1)
    pd_.add_argument("--limit", type=int, default=20)
    pd_.set_defaults(func=cmd_discover)

    pb = sub.add_parser("build", help="패널 데이터셋 생성")
    pb.add_argument("--out", default="kosis_panel.xlsx")
    pb.add_argument("--config", default=None, help="변수 정의 JSON")
    pb.set_defaults(func=cmd_build)

    pe = sub.add_parser("export-config", help="기본 변수 정의를 JSON 으로 추출")
    pe.add_argument("--out", default="kosis_vars.json")
    pe.set_defaults(func=cmd_export_config)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
