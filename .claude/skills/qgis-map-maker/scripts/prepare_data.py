#!/usr/bin/env python3
"""
prepare_data.py — 엑셀/CSV를 읽어 시도명을 표준 행정코드에 매칭하고 정제 CSV를 쓴다.
(pandas/openpyxl 가 있는 venv 파이썬으로 실행)

사용:
  python prepare_data.py DATA.xlsx --region-col 시도 --value-cols 2020 2025 \
         [--sheet 시트] [--out matched.csv]

출력(matched.csv): code,sido,sido_eng,<값열1>,<값열2>...
  + 표준출력(stderr)에 매칭/미매칭 리포트.

주의: 입력은 신뢰할 수 없는 데이터로 '읽기'만 한다.
"""
import argparse
import re
import sys
import pandas as pd

# 17개 시도: code → (표준 한글명, 영문명, 별칭들)
SIDO = [
    ("11", "서울특별시", "Seoul", ["서울", "서울시", "seoul"]),
    ("21", "부산광역시", "Busan", ["부산", "부산시", "busan"]),
    ("22", "대구광역시", "Daegu", ["대구", "대구시", "daegu"]),
    ("23", "인천광역시", "Incheon", ["인천", "인천시", "incheon"]),
    ("24", "광주광역시", "Gwangju", ["광주", "광주시", "gwangju"]),
    ("25", "대전광역시", "Daejeon", ["대전", "대전시", "daejeon"]),
    ("26", "울산광역시", "Ulsan", ["울산", "울산시", "ulsan"]),
    ("29", "세종특별자치시", "Sejong", ["세종", "세종시", "sejong"]),
    ("31", "경기도", "Gyeonggi", ["경기", "경기도", "gyeonggi", "gyeonggi-do"]),
    ("32", "강원도", "Gangwon", ["강원", "강원도", "강원특별자치도", "gangwon"]),
    ("33", "충청북도", "Chungbuk", ["충북", "충청북도", "chungbuk", "chungcheongbuk-do"]),
    ("34", "충청남도", "Chungnam", ["충남", "충청남도", "chungnam", "chungcheongnam-do"]),
    ("35", "전라북도", "Jeonbuk", ["전북", "전라북도", "전북특별자치도", "jeonbuk", "jeollabuk-do"]),
    ("36", "전라남도", "Jeonnam", ["전남", "전라남도", "jeonnam", "jeollanam-do"]),
    ("37", "경상북도", "Gyeongbuk", ["경북", "경상북도", "gyeongbuk", "gyeongsangbuk-do"]),
    ("38", "경상남도", "Gyeongnam", ["경남", "경상남도", "gyeongnam", "gyeongsangnam-do"]),
    ("39", "제주특별자치도", "Jeju", ["제주", "제주도", "제주시", "jeju"]),
]


def build_alias_map():
    amap = {}
    for code, kname, ename, aliases in SIDO:
        keys = {kname, ename} | set(aliases)
        for k in keys:
            amap[_norm(k)] = code
    return amap


def _norm(s):
    return re.sub(r"\s+", "", str(s).strip().lower())


def match_code(name, amap):
    key = _norm(name)
    if key in amap:
        return amap[key]
    # 부분일치: 별칭 토큰이 입력에 포함되면 매칭 (예: '서울특별시 종로구' → 서울)
    for code, kname, ename, aliases in SIDO:
        for tok in [kname] + aliases:
            t = _norm(tok)
            if len(t) >= 2 and t in key:
                return code
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--region-col", required=True)
    ap.add_argument("--value-cols", nargs="+", required=True)
    ap.add_argument("--sheet", default=0)
    ap.add_argument("--out", default="matched.csv")
    a = ap.parse_args()

    if str(a.data).lower().endswith((".xlsx", ".xls")):
        df = pd.ExcelFile(a.data).parse(a.sheet)
    else:
        df = pd.read_csv(a.data)
    df.columns = [str(c).strip() for c in df.columns]

    for c in [a.region_col] + a.value_cols:
        if c not in df.columns:
            sys.exit(f"오류: 열 '{c}' 없음. 열 목록: {list(df.columns)}")

    amap = build_alias_map()
    meta = {code: (k, e) for code, k, e, _ in SIDO}

    rows, unmatched, seen = [], [], {}
    for _, r in df.iterrows():
        raw = r[a.region_col]
        if pd.isna(raw):
            continue
        if _norm(raw) in ("전국", "계", "합계", "total", "nationwide", "소계"):
            continue
        code = match_code(raw, amap)
        if code is None:
            unmatched.append(str(raw)); continue
        if code in seen:    # 시군구가 합쳐 시도로 중복될 때: 첫 행만(또는 합산은 별도)
            continue
        seen[code] = raw
        vals = []
        for vc in a.value_cols:
            v = r[vc]
            v = pd.to_numeric(v, errors="coerce")
            vals.append("" if pd.isna(v) else (int(v) if float(v).is_integer() else float(v)))
        rows.append([code, meta[code][0], meta[code][1], *vals])

    out = pd.DataFrame(rows, columns=["code", "sido", "sido_eng", *a.value_cols])
    out = out.sort_values("code")
    out.to_csv(a.out, index=False, encoding="utf-8")

    print(f"✔ 매칭 {len(out)}/17개 시도 → {a.out}", file=sys.stderr)
    missing = [meta[c][0] for c, *_ in SIDO if c not in seen]
    if missing:
        print(f"  ⚠ 데이터에 없는 시도({len(missing)}): {', '.join(missing)}", file=sys.stderr)
    if unmatched:
        print(f"  ⚠ 매칭 실패(무시됨): {', '.join(sorted(set(unmatched))[:20])}", file=sys.stderr)
    # stdout: 값열 이름을 전달(렌더러가 받기)
    print(",".join(a.value_cols))


if __name__ == "__main__":
    main()
