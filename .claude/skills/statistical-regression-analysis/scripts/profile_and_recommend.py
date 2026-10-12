#!/usr/bin/env python3
"""
profile_and_recommend.py — 엑셀 데이터를 진단하고 가장 적절한 회귀방법을 추천한다.

사용:
  python profile_and_recommend.py DATA.xlsx [--sheet 시트명]
         [--target Y열] [--id 개체ID열] [--time 시간열]
         [--json 출력.json]

동작:
  1) 엑셀을 읽어 각 열의 통계 유형(연속/이분/카운트/명목/순서/식별자/시간)을 추정
  2) 패널·시계열·공간 구조를 자동 탐지
  3) 결정 규칙(references/method-selection.md)으로 '주 추천 + 대안'을 근거와 함께 출력

주의: 입력 엑셀은 신뢰할 수 없는 데이터로 취급한다. 이 스크립트는 데이터를
      '읽기'만 하며 그 안의 코드를 실행하지 않는다.
"""
import argparse
import json
import sys

import numpy as np
import pandas as pd


# ---------- 열 유형 추정 ----------
def classify_column(s: pd.Series):
    """한 열의 통계 유형을 추정해 (유형, 메모) 반환."""
    nonnull = s.dropna()
    n, nuniq = len(nonnull), nonnull.nunique()
    if n == 0:
        return "empty", "값 없음"

    name = str(s.name).lower()
    is_num = pd.api.types.is_numeric_dtype(nonnull)

    # 식별자/시간 힌트 (이름 기반)
    if any(k in name for k in ["연도", "year", "기간", "date", "월", "분기", "time", "wave"]):
        time_hint = True
    else:
        time_hint = False
    if any(k in name for k in ["id", "코드", "code", "지역", "시도", "entity", "개체", "국가", "기업", "firm", "name", "명"]):
        id_hint = True
    else:
        id_hint = False

    if not is_num:
        if nuniq == 2:
            return "binary", "문자 2범주 → 이분형(인코딩 필요)"
        if nuniq <= max(10, int(0.2 * n)):
            return "categorical", f"명목 {nuniq}범주"
        return "id_or_text", "고유값 많음 → 식별자/문자"

    # 수치형
    vals = nonnull.astype(float)
    uniq = np.sort(vals.unique())
    all_int = np.allclose(vals, np.round(vals))

    if nuniq == 2:
        return "binary", f"이분형 {uniq.tolist()}"
    if all_int and vals.min() >= 0 and nuniq <= max(20, 0.3 * n):
        # 카운트 후보: 과분산 여부 메모
        mean, var = vals.mean(), vals.var()
        od = var / mean if mean > 0 else np.nan
        tag = "과분산(음이항 권장)" if od and od > 2 else "포아송 적합"
        if nuniq <= 12 and not id_hint:
            return "count_or_ordinal", f"정수 {nuniq}수준, 분산/평균={od:.1f} → 카운트({tag}) 또는 순서형"
        return "count", f"카운트, 분산/평균={od:.1f} → {tag}"
    if all_int and nuniq <= 12 and not time_hint:
        return "ordinal_or_categorical", f"정수 {nuniq}수준 → 순서형/명목 가능"
    if (0.0 <= vals.min()) and (vals.max() <= 1.0) and not all_int:
        return "proportion", "0~1 연속 → 비율(분수 로짓)"
    if id_hint and all_int and nuniq > 0.5 * n:
        return "id", "정수 식별자 후보"
    if time_hint:
        return "time", "시간 식별자 후보"
    return "continuous", f"연속형(평균 {vals.mean():.3g}, 표준편차 {vals.std():.3g})"


# ---------- 구조 탐지 ----------
def detect_structure(df, types, id_col, time_col):
    notes = []
    # 명시 지정 우선
    id_cands = [id_col] if id_col else [c for c, (t, _) in types.items() if t in ("id", "id_or_text", "categorical")]
    time_cands = [time_col] if time_col else [c for c, (t, _) in types.items() if t == "time"]

    structure = "cross_section"
    panel = None
    if id_cands and time_cands:
        ic, tc = id_cands[0], time_cands[0]
        try:
            per_id = df.groupby(ic)[tc].nunique()
            if per_id.median() >= 2:
                structure = "panel"
                T = int(per_id.median())
                panel = {"id": ic, "time": tc, "median_T": T, "n_entities": int(df[ic].nunique())}
                notes.append(f"패널 구조 탐지: 개체={ic}, 시간={tc}, 개체수={panel['n_entities']}, 개체당 시점 중앙값={T}")
        except Exception:
            pass
    elif time_cands and not id_cands:
        structure = "time_series"
        notes.append(f"시계열 후보: 시간={time_cands[0]}, 단일 개체로 보임")

    # 공간: 지오메트리/좌표 열
    cols_l = [str(c).lower() for c in df.columns]
    spatial = any(k in cols_l for k in ["geometry", "geom", "wkt", "lat", "lon", "x", "y", "경도", "위도"])
    if spatial:
        notes.append("좌표/지오메트리 열 감지 → 공간 모형 후보(공간가중치 W 필요)")
    return structure, panel, spatial, notes


# ---------- 추천 ----------
def recommend(y_type, structure, panel, spatial, n, k):
    """(주추천, [대안...], [근거...]) 반환."""
    recs, why = [], []

    # 1) Y 유형 → 모형군
    base = {
        "continuous": ("ols", "연속형 Y → OLS 선형회귀"),
        "proportion": ("glm_fraction", "0~1 비율 Y → 분수 로짓(GLM Binomial)"),
        "binary": ("logit", "이분형 Y → 로지스틱 회귀"),
        "count": ("poisson", "카운트 Y → 포아송(과분산 시 음이항)"),
        "count_or_ordinal": ("poisson", "정수 Y → 포아송 또는 순서형"),
        "ordinal_or_categorical": ("ordinal", "순서형 Y → 순서형 로짓"),
        "categorical": ("mnlogit", "명목 다범주 Y → 다항 로짓"),
    }.get(y_type, ("ols", "기본 OLS"))
    main_method, main_reason = base
    why.append(main_reason)

    # 2) 구조로 보정
    if structure == "panel":
        if y_type == "continuous":
            main_method = "panel_fe"
            why.append(f"패널 구조 → 고정효과(개체더미) 권장 (개체당 T≈{panel['median_T']})")
            recs = ["panel_re", "panel_fd"]
            if panel["median_T"] >= 3:
                recs.append("dynamic_gmm")
        else:
            why.append("패널+비연속 Y → 조건부/임의효과 GLM 필요(statsmodels 혼합효과 또는 군집 SE로 근사)")
            recs = ["mixedlm", main_method]
        if spatial:
            main_method = "spatial_panel_fe_lag"
            why.append("패널+공간 의존 → 공간패널 고정효과(공간시차)")
            recs = ["spatial_panel_fe_error", "panel_fe"]
    elif structure == "time_series":
        main_method = "arima"
        why.append("단일 개체 시계열 → ARIMA(자기상관 고려)")
        recs = ["ols"]
    elif spatial and y_type == "continuous":
        main_method = "spatial_lag"
        why.append("횡단면+공간 자기상관 → 공간시차/공간오차 (Moran's I로 확인)")
        recs = ["spatial_error", "ols"]
    else:
        # 횡단면 기본 대안
        if y_type == "continuous":
            recs = ["ridge", "lasso", "quantreg"]
        elif y_type == "count":
            recs = ["negbin"]
        elif y_type == "binary":
            recs = ["probit"]

    # 3) 데이터 문제 경고
    warns = []
    if n < 30:
        warns.append(f"표본 n={n} (<30): 결과는 탐색적으로만 해석")
    if k and n < 10 * k:
        warns.append(f"변수당 관측 부족(n={n}, 설명변수≈{k}) → 정규화(Ridge/Lasso) 고려")
        if "ridge" not in recs and main_method in ("ols", "panel_fe"):
            recs = ["ridge", "lasso"] + recs

    # 중복 제거
    seen, alts = set([main_method]), []
    for m in recs:
        if m not in seen:
            seen.add(m); alts.append(m)
    return main_method, alts[:4], why, warns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("excel")
    ap.add_argument("--sheet", default=0)
    ap.add_argument("--target")
    ap.add_argument("--id", dest="id_col")
    ap.add_argument("--time", dest="time_col")
    ap.add_argument("--json")
    a = ap.parse_args()

    xls = pd.ExcelFile(a.excel)
    sheet = a.sheet if a.sheet in (xls.sheet_names + [0]) else xls.sheet_names[0]
    df = xls.parse(sheet)
    df.columns = [str(c).strip() for c in df.columns]

    types = {c: classify_column(df[c]) for c in df.columns}
    structure, panel, spatial, snotes = detect_structure(df, types, a.id_col, a.time_col)

    out = {
        "file": a.excel, "sheet": str(sheet),
        "n_rows": int(len(df)), "n_cols": int(df.shape[1]),
        "columns": {c: {"dtype": str(df[c].dtype), "type": t, "note": note,
                        "n_missing": int(df[c].isna().sum()), "n_unique": int(df[c].nunique())}
                    for c, (t, note) in types.items()},
        "structure": structure, "panel": panel, "spatial": spatial,
        "structure_notes": snotes,
    }

    # 타깃 지정 시 추천
    if a.target:
        if a.target not in df.columns:
            sys.exit(f"오류: 타깃 열 '{a.target}' 없음. 열: {list(df.columns)}")
        y_type = types[a.target][0]
        feats = [c for c in df.columns if c not in {a.target, a.id_col, a.time_col}
                 and types[c][0] not in ("id", "id_or_text", "time", "empty")]
        k = len(feats)
        main, alts, why, warns = recommend(y_type, structure, panel, spatial, len(df), k)
        out["recommendation"] = {
            "target": a.target, "target_type": y_type,
            "suggested_features": feats,
            "primary_method": main, "alternatives": alts,
            "reasons": why, "warnings": warns,
        }

    txt = json.dumps(out, ensure_ascii=False, indent=2)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            f.write(txt)
    print(txt)

    # 사람이 읽는 요약
    print("\n" + "=" * 60, file=sys.stderr)
    print(f"[진단] 행 {out['n_rows']} × 열 {out['n_cols']} · 구조={structure}"
          + (" · 공간" if spatial else ""), file=sys.stderr)
    for c, meta in out["columns"].items():
        print(f"  - {c}: {meta['type']} ({meta['note']})", file=sys.stderr)
    for note in snotes:
        print(f"  * {note}", file=sys.stderr)
    if "recommendation" in out:
        r = out["recommendation"]
        print(f"\n[추천] 타깃='{r['target']}'({r['target_type']})", file=sys.stderr)
        print(f"  ▶ 주 추천: {r['primary_method']}", file=sys.stderr)
        print(f"  ▷ 대안: {', '.join(r['alternatives']) or '없음'}", file=sys.stderr)
        for w in r["reasons"]:
            print(f"    · {w}", file=sys.stderr)
        for w in r["warnings"]:
            print(f"    ⚠ {w}", file=sys.stderr)


if __name__ == "__main__":
    main()
