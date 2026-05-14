"""광역 17 × 2013–2024 KOSIS 사회·인구 패널 빌더.

기본 변수: 총인구, 65세 이상 인구, 기초생활보장 수급자.
변수 정의는 catalog.DEFAULT_VARS 또는 외부 YAML/JSON 으로 교체 가능.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from lgstats.common.io import write_panel_xlsx
from lgstats.common.sido import SIDO, YEARS_DEFAULT
from lgstats.sources.kosis.catalog import DEFAULT_VARS, KosisVar
from lgstats.sources.kosis.client import fetch_var_for_sido, get_client


def load_vars(config: Path | None) -> list[KosisVar]:
    if config is None:
        return DEFAULT_VARS
    raw = config.read_text(encoding="utf-8")
    if config.suffix.lower() in {".yml", ".yaml"}:
        import yaml
        data = yaml.safe_load(raw)
    else:
        data = json.loads(raw)
    return [KosisVar(**d) for d in data]


def build_panel(vars_: list[KosisVar]) -> pd.DataFrame:
    client = get_client()
    rows = []
    for s in SIDO:
        merged = pd.DataFrame({"year": YEARS_DEFAULT})
        for v in vars_:
            try:
                series = fetch_var_for_sido(
                    client, v, s.kosis_code, YEARS_DEFAULT[0], YEARS_DEFAULT[-1]
                )
            except Exception as e:
                print(f"[warn] {s.name} {v.var_name}: {e}")
                series = pd.DataFrame(columns=["year", v.var_name])
            merged = merged.merge(series, on="year", how="left")
        merged.insert(0, "sido", s.name)
        merged.insert(0, "sido_code", s.adm_code)
        rows.append(merged)
        print(f"  ✓ {s.name}")
    return pd.concat(rows, ignore_index=True)


def run(config: Path | None, out: Path) -> None:
    vars_ = load_vars(config)
    print(f"변수 {len(vars_)}개 수집 (대상 {len(SIDO)} 시도)")
    panel = build_panel(vars_)

    columns = ["sido_code", "sido", "year"] + [v.var_name for v in vars_]
    headers = {"sido_code": "시도코드", "sido": "시도명", "year": "연도",
               **{v.var_name: v.label_kr for v in vars_}}
    readme = [
        ("대상", f"광역 17개 × {YEARS_DEFAULT[0]}~{YEARS_DEFAULT[-1]}"),
        ("출처", "KOSIS 공유서비스 Open API"),
    ] + [(v.label_kr, f"orgId={v.org_id} tblId={v.tbl_id} itmId={v.itm_id} | {v.notes}")
         for v in vars_]
    write_panel_xlsx(
        panel, out,
        headers_kr=headers,
        column_order=columns,
        readme_rows=readme,
        column_widths=[10, 18, 10] + [22] * len(vars_),
    )
    print(f"\n작성 완료: {out}")
    for v in vars_:
        miss = panel[v.var_name].isna().mean() * 100
        print(f"  {v.var_name:35s} 결측 {miss:5.1f}%")
