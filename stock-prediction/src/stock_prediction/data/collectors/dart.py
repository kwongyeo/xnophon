"""한국 재무·공시 수집기 (OpenDART).

두 경로:
- fetch_financials : 운영 경로. OpenDART REST API 직접 호출(DART_API_KEY 필요).
- normalize_financials : 이미 받은 원본 JSON(MCP opendart 또는 REST 응답)을 표준 스키마로 변환.

공시 "접수일(rcept_no 앞 8자리)"을 disclosed_at 으로 기록 — point-in-time 정렬에 사용.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from ..schema import FUNDAMENTAL_COLUMNS

REPORT_CODES = {"annual": "11011", "q1": "11013", "half": "11012", "q3": "11014"}

# OpenDART 계정명(account_nm) → 표준 컬럼. 삼성전자 연결 기준 한국어 계정명.
_ACCOUNT_MAP = {
    "수익(매출액)": "revenue",
    "매출액": "revenue",
    "영업이익": "operating_income",
    "당기순이익": "net_income",
    "자산총계": "total_assets",
    "자본총계": "total_equity",
    "부채총계": "total_debt",
}
# 손익 항목은 IS에서, 재무상태 항목은 BS에서만 취한다(중복 계정명 충돌 방지).
_PREFERRED_SJ = {
    "revenue": "IS", "operating_income": "IS", "net_income": "IS",
    "total_assets": "BS", "total_equity": "BS", "total_debt": "BS",
}


# ---------------------------------------------------------------- 운영 경로
def fetch_financials(corp_code: str, year: int, report: str = "annual",
                     fs_div: str = "CFS") -> pd.DataFrame:
    """OpenDART REST API로 전체 재무제표를 받아 표준 스키마로 변환."""
    import requests  # 지연 import

    key = os.environ.get("DART_API_KEY")
    if not key:
        raise RuntimeError("DART_API_KEY 미설정 — .env 참조 (https://opendart.fss.or.kr)")
    url = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
    params = {
        "crtfc_key": key, "corp_code": corp_code, "bsns_year": str(year),
        "reprt_code": REPORT_CODES[report], "fs_div": fs_div,
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return normalize_financials(resp.json(), ticker=corp_code)


# ---------------------------------------------------------------- 원본 정규화
def _unwrap(raw: str | dict) -> dict:
    if isinstance(raw, str):
        raw = json.loads(raw)
    if "result" in raw and isinstance(raw["result"], str):
        raw = json.loads(raw["result"])
    return raw


def normalize_financials(raw: str | dict, ticker: str) -> pd.DataFrame:
    """OpenDART fnlttSinglAcntAll 응답을 FUNDAMENTAL_COLUMNS로 변환.

    당기(thstrm)·전기(frmtrm) 금액을 각각 한 행으로 만든다.
    disclosed_at 은 rcept_no(접수번호) 앞 8자리(YYYYMMDD)에서 추출.
    """
    obj = _unwrap(raw)
    items = obj.get("list", [])
    if not items:
        return pd.DataFrame(columns=FUNDAMENTAL_COLUMNS)

    meta = items[0]
    rcept = str(meta.get("rcept_no", ""))
    disclosed = (f"{rcept[0:4]}-{rcept[4:6]}-{rcept[6:8]}" if len(rcept) >= 8 else None)
    year = int(meta.get("bsns_year", 0))

    def pick(amount_field: str) -> dict:
        out: dict = {}
        for it in items:
            std = _ACCOUNT_MAP.get(it.get("account_nm"))
            if std and it.get("sj_div") == _PREFERRED_SJ[std] and std not in out:
                val = str(it.get(amount_field, "")).replace(",", "").strip()
                out[std] = int(val) if val.lstrip("-").isdigit() else None
        return out

    rows = []
    # 당기(thstrm) = 해당 연도, 전기(frmtrm) = 전년도. 둘 다 보관해 시계열 확보.
    cur = pick("thstrm_amount")
    if cur:
        rows.append({"ticker": ticker, "fiscal_period": f"{year}",
                     "disclosed_at": disclosed, **cur})
    prev = pick("frmtrm_amount")
    if prev:
        rows.append({"ticker": ticker, "fiscal_period": f"{year - 1}",
                     "disclosed_at": None, **prev})  # 전기 공시일은 별도 보고서 필요

    df = pd.DataFrame(rows)
    for col in FUNDAMENTAL_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    return df[FUNDAMENTAL_COLUMNS]


def load_raw(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def fetch_disclosures(corp_code: str, start: str, end: str) -> pd.DataFrame:
    """공시 이벤트(증자/합병 등) 목록. 이벤트 더미 피처로 활용(추후 구현)."""
    raise NotImplementedError
