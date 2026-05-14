"""지방재정365 「세출예산 분야별 현황」 다운로드 파일 파서.

연도별 CSV/XLSX 를 일괄 읽어 (sido_code, year, field_code, value) long-form 으로 변환.
일반회계+특별회계만 합산(기금 제외).
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from stats_collect.common.sido import match_name


_FIELD_CODE_RE = re.compile(r"\b(0?\d{2,3})\b")


def normalize_field_code(value) -> str | None:
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
        if all(n in str(col) for n in needles):
            return col
    return None


def parse_file(path: Path) -> pd.DataFrame:
    """단일 lofin 파일 → (sido_raw, year, field_code, value)."""
    year_match = re.search(r"(20\d{2})", path.name)
    if not year_match:
        return pd.DataFrame(columns=["sido_raw", "year", "field_code", "value"])
    year = int(year_match.group(1))

    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path, dtype=str)
    else:
        df = pd.read_excel(path, dtype=str)

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
    if not (col_sido and col_field and col_value):
        return pd.DataFrame(columns=["sido_raw", "year", "field_code", "value"])

    keep = [col_sido, col_field, col_value] + ([col_acct] if col_acct else [])
    sub = df[keep].copy()
    sub.columns = ["sido_raw", "field_raw", "value_raw"] + (["acct"] if col_acct else [])
    sub["field_code"] = sub["field_raw"].map(normalize_field_code)
    sub = sub[sub["field_code"].notna()].copy()
    if col_acct:
        sub = sub[sub["acct"].astype(str).str.contains("일반|특별", na=False)]
        sub = sub[~sub["acct"].astype(str).str.contains("기금", na=False)]
    sub["value"] = pd.to_numeric(
        sub["value_raw"].astype(str).str.replace(",", "", regex=False).str.strip(),
        errors="coerce",
    )
    sub["year"] = year
    return sub[["sido_raw", "year", "field_code", "value"]].dropna(subset=["value"])


def ingest_dir(raw_dir: Path) -> pd.DataFrame:
    """raw_dir 안의 CSV/XLSX 모두 → (sido_code, year, field_code, value) 집계."""
    files = sorted(
        p for p in raw_dir.iterdir() if p.suffix.lower() in {".csv", ".xlsx", ".xls"}
    )
    if not files:
        raise SystemExit(f"원자료 파일이 {raw_dir} 에 없습니다.")
    frames = [parse_file(p) for p in files]
    long = pd.concat(frames, ignore_index=True)
    long["sido_code"] = long["sido_raw"].map(
        lambda r: (s := match_name(r)) and s.adm_code
    )
    long = long.dropna(subset=["sido_code"])
    return (
        long.groupby(["sido_code", "year", "field_code"], as_index=False)["value"]
        .sum()
    )
