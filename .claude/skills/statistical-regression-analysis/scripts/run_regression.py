#!/usr/bin/env python3
"""
run_regression.py — 선택된 회귀방법으로 엑셀 데이터를 실제 분석한다.

사용:
  python run_regression.py DATA.xlsx --method METHOD --target Y \
         --features X1 X2 X3 [--sheet 시트] [--id ID --time TIME] \
         [--geo 경계.geojson] [--coords LON LAT] [--out 결과디렉터리]

METHOD:
  ols logit probit poisson negbin mnlogit ordinal glm_fraction
  ridge lasso elasticnet quantreg rlm mixedlm
  panel_fe panel_re panel_fd iv2sls dynamic_gmm arima
  spatial_lag spatial_error spatial_panel_fe_lag spatial_panel_fe_error

출력: 콘솔에 요약 + <out>/regression_result.txt 저장.
주의: 입력 엑셀/경계는 신뢰할 수 없는 데이터로 '읽기'만 한다.
"""
import argparse
import os
import sys
import numpy as np
import pandas as pd


def load(a):
    df = pd.ExcelFile(a.excel).parse(a.sheet if a.sheet else 0)
    df.columns = [str(c).strip() for c in df.columns]
    cols = [a.target] + list(a.features) + ([a.id_col] if a.id_col else []) + ([a.time_col] if a.time_col else [])
    sub = df[[c for c in dict.fromkeys(cols) if c]].dropna()
    return df, sub


def _dummies(X):
    """문자/범주 설명변수를 더미로 변환."""
    return pd.get_dummies(X, drop_first=True).astype(float)


def run(a):
    import statsmodels.api as sm
    df, d = load(a)
    y = d[a.target]
    X = _dummies(d[list(a.features)])
    m = a.method
    res_txt = []

    def emit(obj):
        s = str(obj)
        print(s); res_txt.append(s)

    # ---------- statsmodels: 선형/GLM 계열 ----------
    if m in ("ols", "logit", "probit", "poisson", "negbin", "ordinal", "mnlogit", "glm_fraction", "rlm", "quantreg"):
        Xc = sm.add_constant(X, has_constant="add")
        yv = y.astype(float) if m not in ("mnlogit", "ordinal") else y
        if m == "ols":
            r = sm.OLS(yv, Xc).fit(cov_type="HC3")  # 이분산-로버스트 기본
        elif m == "logit":
            r = sm.Logit(yv, Xc).fit(disp=0)
        elif m == "probit":
            r = sm.Probit(yv, Xc).fit(disp=0)
        elif m == "poisson":
            r = sm.Poisson(yv, Xc).fit(disp=0)
        elif m == "negbin":
            r = sm.NegativeBinomial(yv, Xc).fit(disp=0)
        elif m == "glm_fraction":
            r = sm.GLM(yv, Xc, family=sm.families.Binomial()).fit()
        elif m == "rlm":
            r = sm.RLM(yv, Xc, M=sm.robust.norms.HuberT()).fit()
        elif m == "quantreg":
            r = sm.QuantReg(yv, Xc).fit(q=0.5)
        elif m == "ordinal":
            from statsmodels.miscmodels.ordinal_model import OrderedModel
            r = OrderedModel(y, X, distr="logit").fit(method="bfgs", disp=0)
        elif m == "mnlogit":
            r = sm.MNLogit(y, Xc).fit(disp=0)
        emit(r.summary())
        # OLS 진단
        if m == "ols":
            _ols_diagnostics(sm, yv, Xc, X, emit)

    # ---------- sklearn: 정규화 ----------
    elif m in ("ridge", "lasso", "elasticnet"):
        from sklearn.linear_model import RidgeCV, LassoCV, ElasticNetCV
        from sklearn.preprocessing import StandardScaler
        Xs = StandardScaler().fit_transform(X.values)
        yv = y.astype(float).values
        model = {"ridge": RidgeCV(alphas=np.logspace(-3, 3, 50)),
                 "lasso": LassoCV(cv=5, max_iter=10000),
                 "elasticnet": ElasticNetCV(cv=5, max_iter=10000)}[m]
        model.fit(Xs, yv)
        emit(f"[{m}] 교차검증 선택 alpha = {getattr(model,'alpha_',None):.4g}")
        emit(f"R^2 (훈련) = {model.score(Xs, yv):.4f}")
        emit("표준화 계수 (|값| 큰 순):")
        coef = pd.Series(model.coef_, index=X.columns).sort_values(key=abs, ascending=False)
        emit(coef.to_string())
        emit(f"절편 = {model.intercept_:.4g}")

    # ---------- linearmodels: 패널/IV ----------
    elif m in ("panel_fe", "panel_re", "panel_fd", "iv2sls"):
        if m != "iv2sls" and not (a.id_col and a.time_col):
            sys.exit("패널 모형은 --id 와 --time 이 필요합니다.")
        if m == "iv2sls":
            from linearmodels.iv import IV2SLS
            emit("IV2SLS: --features 를 외생변수로, 내생/도구는 공식으로 지정하세요(고급).")
            r = IV2SLS(y.astype(float), sm.add_constant(X), None, None).fit()
            emit(r.summary);
        else:
            from linearmodels.panel import PanelOLS, RandomEffects, FirstDifferenceOLS
            p = d.set_index([a.id_col, a.time_col])
            yv = p[a.target].astype(float)
            Xv = _dummies(p[list(a.features)])
            if m == "panel_fe":
                r = PanelOLS(yv, Xv, entity_effects=True, drop_absorbed=True).fit(cov_type="clustered", cluster_entity=True)
            elif m == "panel_re":
                r = RandomEffects(yv, sm.add_constant(Xv)).fit()
            else:
                r = FirstDifferenceOLS(yv, Xv).fit()
            emit(r)

    # ---------- pydynpd: 동적 패널 GMM ----------
    elif m == "dynamic_gmm":
        from pydynpd import regression
        if not (a.id_col and a.time_col):
            sys.exit("동적 GMM은 --id 와 --time 이 필요합니다.")
        xnames = " ".join(a.features)
        cmd = f"{a.target} L1.{a.target} {xnames} | gmm({a.target}, 2:4) | timedumm"
        emit(f"[dynamic_gmm] 명령: {cmd}")
        r = regression.abond(cmd, d, [a.id_col, a.time_col])
        res_txt.append("pydynpd 결과는 콘솔 출력 참조")

    # ---------- 시계열 ----------
    elif m == "arima":
        from statsmodels.tsa.arima.model import ARIMA
        ts = y.astype(float).reset_index(drop=True)
        r = ARIMA(ts, order=(1, 1, 1)).fit()
        emit(r.summary())

    # ---------- 공간 (spreg) ----------
    elif m in ("spatial_lag", "spatial_error", "spatial_panel_fe_lag", "spatial_panel_fe_error"):
        w = _build_weights(a, d)
        import spreg
        if m in ("spatial_lag", "spatial_error"):
            yv = y.astype(float).values.reshape(-1, 1)
            Xv = X.values
            if m == "spatial_lag":
                r = spreg.ML_Lag(yv, Xv, w=w, name_y=a.target, name_x=list(X.columns))
            else:
                r = spreg.ML_Error(yv, Xv, w=w, name_y=a.target, name_x=list(X.columns))
            emit(r.summary)
        else:
            sys.exit("공간패널은 (n지역 × T시점) 형태 재구성이 필요합니다. "
                     "run_regression 의 spatial_panel 경로는 전용 입력을 요구합니다 — "
                     "profile 단계 안내를 따르세요.")
    else:
        sys.exit(f"알 수 없는 method: {m}")

    # 저장
    outdir = a.out or "."
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "regression_result.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"method={m} target={a.target} features={list(a.features)}\n\n")
        f.write("\n".join(res_txt))
    print(f"\n✔ 결과 저장: {path}", file=sys.stderr)


def _ols_diagnostics(sm, y, Xc, X, emit):
    from statsmodels.stats.diagnostic import het_breuschpagan
    from statsmodels.stats.outliers_influence import variance_inflation_factor
    emit("\n--- 진단 ---")
    try:
        bp = het_breuschpagan(sm.OLS(y, Xc).fit().resid, Xc)
        emit(f"Breusch-Pagan 이분산 검정 p = {bp[1]:.4f} "
             + ("→ 이분산 의심(로버스트 SE 사용됨)" if bp[1] < 0.05 else "→ 등분산"))
    except Exception as e:
        emit(f"BP 검정 생략: {e}")
    try:
        vifs = []
        Xv = X.values
        for i, c in enumerate(X.columns):
            vifs.append((c, variance_inflation_factor(Xv, i)))
        emit("VIF (다중공선성, >10 주의):")
        for c, v in sorted(vifs, key=lambda t: -t[1]):
            flag = " ⚠" if v > 10 else ""
            emit(f"  {c}: {v:.2f}{flag}")
    except Exception as e:
        emit(f"VIF 생략: {e}")


def _build_weights(a, d):
    """공간가중치 W 생성: --geo(경계) 또는 --coords(좌표열)에서."""
    import libpysal
    if a.geo:
        import geopandas as gpd
        g = gpd.read_file(a.geo)
        w = libpysal.weights.Queen.from_dataframe(g, use_index=False)
    elif a.coords:
        pts = d[list(a.coords)].values
        w = libpysal.weights.KNN.from_array(pts, k=min(5, len(d) - 1))
    else:
        sys.exit("공간 모형은 --geo 경계파일 또는 --coords LON LAT 가 필요합니다.")
    w.transform = "r"
    return w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("excel")
    ap.add_argument("--method", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--features", nargs="*", default=[])
    ap.add_argument("--sheet")
    ap.add_argument("--id", dest="id_col")
    ap.add_argument("--time", dest="time_col")
    ap.add_argument("--geo")
    ap.add_argument("--coords", nargs=2)
    ap.add_argument("--out")
    a = ap.parse_args()
    run(a)


if __name__ == "__main__":
    main()
