# 회귀분석 방법 카탈로그 (method → 패키지/클래스)

`run_regression.py --method <키>` 에 쓰는 방법 키와 구현 매핑.

## 선형 · GLM (statsmodels)

| 키 | 방법 | 클래스 | 적합 Y |
|---|---|---|---|
| `ols` | 최소제곱 선형회귀(HC3 로버스트 SE) | `OLS` | 연속형 |
| `glm_fraction` | 분수 로짓 | `GLM(Binomial)` | 0~1 비율 |
| `logit` | 로지스틱 | `Logit` | 이분형 |
| `probit` | 프로빗 | `Probit` | 이분형 |
| `poisson` | 포아송 | `Poisson` | 카운트 |
| `negbin` | 음이항(과분산) | `NegativeBinomial` | 카운트 |
| `ordinal` | 순서형 로짓 | `OrderedModel` | 순서형 |
| `mnlogit` | 다항 로짓 | `MNLogit` | 명목 다범주 |
| `quantreg` | 분위회귀(중위) | `QuantReg` | 연속형(분위) |
| `rlm` | 로버스트 회귀(Huber) | `RLM` | 연속형(이상치) |
| `mixedlm` | 선형 혼합효과 | `MixedLM` | 위계/반복측정 |
| `arima` | 시계열 ARIMA | `tsa.ARIMA` | 단일 시계열 |

## 정규화 (scikit-learn, 표준화 후 CV)

| 키 | 방법 | 클래스 |
|---|---|---|
| `ridge` | 릿지(L2) | `RidgeCV` |
| `lasso` | 라쏘(L1, 변수선택) | `LassoCV` |
| `elasticnet` | 엘라스틱넷(L1+L2) | `ElasticNetCV` |

## 패널 · 도구변수 (linearmodels)

| 키 | 방법 | 클래스 | 요구 |
|---|---|---|---|
| `panel_fe` | 고정효과(개체), 군집 SE | `PanelOLS(entity_effects)` | --id --time |
| `panel_re` | 확률효과 | `RandomEffects` | --id --time |
| `panel_fd` | 1차 차분 | `FirstDifferenceOLS` | --id --time |
| `iv2sls` | 2단계 최소제곱(내생성) | `IV2SLS` | 도구변수 |
| `dynamic_gmm` | 차분/시스템 GMM(동적패널) | pydynpd `abond` | --id --time, T≥3 |

## 공간 (spreg + libpysal)

| 키 | 방법 | 클래스 | 요구 |
|---|---|---|---|
| `spatial_lag` | 공간시차(SAR) | `ML_Lag` | --geo 또는 --coords |
| `spatial_error` | 공간오차(SEM) | `ML_Error` | --geo 또는 --coords |
| `spatial_panel_fe_lag` | 공간패널 고정효과·시차 | `Panel_FE_Lag` | 전용 (n지역×T) |
| `spatial_panel_fe_error` | 공간패널 고정효과·오차 | `Panel_FE_Error` | 전용 (n지역×T) |

> 공간 모형은 **공간가중치 W**가 필수다. `--geo 경계.geojson`(Queen 인접) 또는
> `--coords 경도열 위도열`(KNN)로 생성한다. 공간패널은 데이터를 (지역 × 시점)
> 배열로 재구성해야 하므로 별도 스크립트 경로를 사용한다.
