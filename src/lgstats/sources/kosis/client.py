"""KOSIS Open API 박형 래퍼."""

from __future__ import annotations

import os
import sys

import pandas as pd

try:
    import PublicDataReader as pdr
except ImportError:
    sys.exit("PublicDataReader 가 필요합니다: pip install PublicDataReader")

from lgstats.sources.kosis.catalog import KosisVar


def get_client():
    key = os.environ.get("KOSIS_API_KEY")
    if not key:
        sys.exit(
            "환경변수 KOSIS_API_KEY 가 비어 있습니다.\n"
            "  export KOSIS_API_KEY='발급받은_키'  후 재실행하세요."
        )
    return pdr.Kosis(service_key=key)


def fetch_var_for_sido(client, v: KosisVar, sido_kosis_code: str,
                       start_year: int, end_year: int) -> pd.DataFrame:
    """단일 시도 × 단일 변수 시계열 → (year, <var_name>)."""
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

    year_col = next((c for c in df.columns if "수록" in c or "시점" in c), None)
    val_col = next((c for c in df.columns if c in ("수치값", "DT")), None)
    if year_col is None or val_col is None:
        return pd.DataFrame(columns=["year", v.var_name])

    out = df[[year_col, val_col]].copy()
    out.columns = ["year", v.var_name]
    out["year"] = pd.to_numeric(out["year"], errors="coerce").astype("Int64")
    out[v.var_name] = pd.to_numeric(out[v.var_name], errors="coerce")
    return out.dropna(subset=["year"])


def discover(keyword: str, start: int = 1, limit: int = 20) -> pd.DataFrame | None:
    client = get_client()
    return client.get_data(
        "KOSIS통합검색",
        searchNm=keyword,
        startCount=str(start),
        resultCount=str(limit),
    )
