# 패널회귀 · 공간패널회귀 — 알고리즘 & 설치 권장안

GitHub에서 검증한, **패널 데이터 회귀(panel regression)**와 **공간 패널회귀
(spatial panel regression)**를 위한 라이브러리 권장안. Python 스택은 이 저장소
컨테이너에서 **실제 설치·임포트까지 검증**했다.

---

## TL;DR — 무엇을 깔면 되나

| 목적 | 권장 (Python) | 권장 (R, 학계 표준) |
|---|---|---|
| 정적 패널회귀(FE/RE) | **linearmodels** | **plm**, **fixest** |
| 동적 패널 GMM | **pydynpd** | **plm**(pgmm) |
| 공간 패널회귀 | **spreg**(PySAL) | **splm** |
| 공간가중치 행렬 | **libpysal** | **spdep** |
| 공간 진단(Moran's I) | **esda** | **spdep** |

```bash
# Python 한 줄 설치 (검증된 스택)
python3 -m venv .venv
.venv/bin/pip install -r econometrics/requirements.txt
```

---

## 1) 패널회귀 (Panel Regression)

### Python — `linearmodels` ⭐ 권장
- GitHub: [bashtage/linearmodels](https://github.com/bashtage/linearmodels) · PyPI `linearmodels`
- 모형: `PanelOLS`(고정효과, 양방향 FE, 군집표준오차), `RandomEffects`,
  `BetweenOLS`, `FirstDifferenceOLS`, `PooledOLS`, `FamaMacBeth`.
- statsmodels를 확장한 사실상의 Python 패널 표준. R `plm`에 대응.

### Python — `pydynpd` (동적 패널)
- GitHub: [dazhwu/pydynpd](https://github.com/dazhwu/pydynpd) · PyPI `pydynpd`
- **차분/시스템 GMM**(Arellano-Bond, Blundell-Bond). 종속변수 시차항이
  설명변수일 때(동적 패널). Stata `xtabond2`, R `plm::pgmm`에 대응.

### R — `plm` / `fixest` (학계 표준)
- [plm](https://cran.r-project.org/package=plm): 패널 계량경제의 표준. FE/RE,
  Hausman 검정, pgmm(동적), 공적분 등 종합.
- [fixest](https://github.com/lrberge/fixest): **초고속 고정효과**(다수 FE,
  군집 SE). 대규모 패널에서 plm보다 훨씬 빠름.

---

## 2) 공간 패널회귀 (Spatial Panel Regression)

공간 의존성(이웃 지역 간 상호작용)을 패널에 결합한 모형. **공간시차(SAR)**·
**공간오차(SEM)** 모형을 고정효과/확률효과와 함께 추정한다.

### Python — `spreg` (PySAL) ⭐ 권장
- GitHub: [pysal/spreg](https://github.com/pysal/spreg) · 문서 [pysal.org/spreg](https://pysal.org/spreg/)
- 공간 패널 클래스:
  - `Panel_FE_Lag` — 고정효과 **공간시차** 모형 (ML)
  - `Panel_FE_Error` — 고정효과 **공간오차** 모형 (ML)
  - `Panel_RE_Lag` — 확률효과 공간시차 모형
  - `Panel_RE_Error` — 확률효과 공간오차 모형
- 그 외 단면 공간회귀: `ML_Lag`, `ML_Error`, `GM_Lag`, `GMM_Error`, `GM_Combo`.

### R — `splm` (학계 표준)
- [splm](https://cran.r-project.org/package=splm): 공간 패널의 표준. `spml()`로
  SAR/SEM × FE/RE 조합, `spgm()`(GM 추정), Hausman·LM 검정 일체.
- 보조: [spatialreg](https://cran.r-project.org/package=spatialreg)(단면 공간회귀),
  [spdep](https://cran.r-project.org/package=spdep)(공간가중치·Moran).

---

## 3) 공간가중치(W) & 진단 — 공간모형의 전제

| 도구 | 역할 | GitHub/CRAN |
|---|---|---|
| **libpysal** | 인접(Queen/Rook)·KNN·거리 기반 가중치 행렬 생성 | [pysal/libpysal](https://github.com/pysal/libpysal) |
| **esda** | Moran's I, LISA 등 공간자기상관 진단 → 공간모형 필요성 판단 | [pysal/esda](https://github.com/pysal/esda) |
| **geopandas** | shapefile/GeoPackage 등 경계 데이터 로드 | [geopandas/geopandas](https://github.com/geopandas/geopandas) |
| (R) **spdep** | 가중치 + Moran/LM 검정 | CRAN |

> 워크플로: **경계 로드(geopandas) → W 생성(libpysal) → 공간자기상관 검정
> (esda Moran's I) → 유의하면 공간패널(spreg) 추정**.

---

## 4) Python vs R — 선택 가이드

- **Python(spreg/linearmodels)**: 기존 데이터 파이프라인이 Python(이 저장소,
  PyQGIS, geopandas)일 때. 공간 패널은 FE만 필요하면 충분히 견고.
- **R(splm/plm)**: 공간 패널의 **모형 선택 검정(Hausman, LM-lag/error,
  로버스트 LM)**과 RE/GM 추정이 풍부. 계량경제 논문 재현엔 R이 사실상 표준.
- **실무 권장**: 데이터 가공·지도는 Python, 최종 공간패널 추정·검정은 R `splm`
  으로 교차검증하면 가장 안전하다.

---

## 5) 설치 방법

### Python (권장: venv + pip)
```bash
python3 -m venv .venv
.venv/bin/pip install -r econometrics/requirements.txt
```
또는 conda:
```bash
conda install -c conda-forge linearmodels spreg libpysal esda geopandas
pip install pydynpd            # conda-forge에 없을 경우
```

### R (이 컨테이너엔 미설치 — 필요 시 설치)
```bash
sudo apt-get install -y r-base           # Ubuntu
Rscript -e 'install.packages(c("plm","fixest","splm","spatialreg","spdep"), repos="https://cloud.r-project.org")'
```

---

## 6) 설치 검증 결과 (이 컨테이너)

`econometrics/requirements.txt`를 venv에 설치하여 임포트 + **추정 런타임**까지 확인:

| 패키지 | 버전 | 검증 |
|---|---|---|
| linearmodels | 7.0 | `PanelOLS`(FE) 추정 OK — 합성데이터 계수 2.14≈참값 2.0, N=120 ✔ |
| spreg | 1.9.0 | `Panel_FE_Lag`(공간시차 FE) 추정 OK — Rook 4×5 격자 W ✔ |
| libpysal | 4.14.1 | `Queen`, `Rook`, `KNN`, `lat2W` ✔ |
| pydynpd | 0.2.2 | 차분/시스템 GMM 임포트 ✔ |
| geopandas | 1.1.3 | 경계 로드 ✔ |

> R(plm/splm)은 이 컨테이너에 **미설치**. 위 apt 명령으로 추가할 수 있으나,
> `cloud.r-project.org` 등 CRAN 미러가 egress 정책상 차단될 수 있다(설치 전
> 접근성 확인 필요).

---

## 7) 용도별 권장 스택

- **일반 패널(FE/RE)만** → `linearmodels` 단독
- **동적 패널(시차 종속변수)** → `linearmodels` + `pydynpd`
- **공간 패널(지역 데이터)** → `geopandas` + `libpysal` + `esda` + `spreg`
- **논문 재현·검정 엄밀성** → R `plm` + `splm`(+ Python으로 교차검증)

## 출처

- [linearmodels (PyPI)](https://pypi.org/project/linearmodels/) · [bashtage/linearmodels](https://github.com/bashtage/linearmodels)
- [pysal/spreg](https://github.com/pysal/spreg) · [spreg 공간패널 문서](https://pysal.org/spreg/notebooks/Panel_FE_example.html)
- [pysal/libpysal](https://github.com/pysal/libpysal) · [pysal/esda](https://github.com/pysal/esda)
- [dazhwu/pydynpd](https://github.com/dazhwu/pydynpd)
- R: [plm](https://cran.r-project.org/package=plm) · [splm](https://cran.r-project.org/package=splm) · [fixest](https://github.com/lrberge/fixest)
