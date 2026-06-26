# QGIS 분석 플러그인 — 권장 설치 목록

GitHub에서 검증한, 공간분석에 유용한 QGIS 플러그인 권장안.
대부분 **QGIS 플러그인 관리자**(플러그인 → 플러그인 관리 및 설치)에서
이름으로 검색해 설치할 수 있고, 소스는 GitHub에 공개되어 있다.

## 설치 방법 3가지

| 방법 | 절차 | 언제 |
|---|---|---|
| **① 플러그인 관리자(권장)** | `플러그인 → 플러그인 관리 및 설치 → 전체` 에서 이름 검색 → 설치 | 공식 저장소에 등록된 대부분의 플러그인 |
| **② ZIP 설치** | GitHub Release에서 `.zip` 다운로드 → `ZIP에서 설치` 탭 → 파일 선택 | 공식 저장소에 없거나 최신/베타 버전 |
| **③ 외부 저장소 URL** | `설정 → 플러그인 저장소 추가` 에 URL 등록 | 기관·개인이 자체 배포하는 경우 |

> 실험적(experimental) 플러그인은 `설정 → 실험적 플러그인도 표시`를 켜야 보인다.

---

## 1) 범용 · 필수

| 플러그인 | 용도 | GitHub |
|---|---|---|
| **QuickOSM** | OpenStreetMap 데이터를 QGIS에서 직접 추출 | `3liz/QuickOSM` |
| **QuickMapServices** | 위성·OSM 등 배경지도 손쉽게 추가 | `nextgis/quickmapservices` |
| **DataPlotly** | Plotly 기반 인터랙티브 차트(산점도·히스토그램·시계열) | [ghtmtt/DataPlotly](https://github.com/ghtmtt/DataPlotly) |
| **mmqgis** | 벡터 결합·지오코딩·도형 처리 도구 모음 | `michaelminn/mmqgis` |

## 2) 공간통계 · 패턴 분석 (핫스팟·자기상관)

| 플러그인 | 용도 | GitHub |
|---|---|---|
| **Hotspot Analysis** | Getis-Ord Gi*, Anselin Local Moran's I 로 핫스팟/콜드스팟·군집 탐지 | [danioxoli/HotSpotAnalysis_Plugin](https://github.com/danioxoli/HotSpotAnalysis_Plugin) |
| **Spatial Analysis Toolbox** | Moran's I, GWR(지리가중회귀), 각종 공간지수 처리 알고리즘 | [parmendel/spatialanalysistoolbox](https://github.com/parmendel/spatialanalysistoolbox) |

## 3) 네트워크 · 접근성 분석

| 플러그인 | 용도 | GitHub |
|---|---|---|
| **QNEAT3** | 최단경로, 등시선(서비스권역), OD 매트릭스 — Processing 툴박스에 통합 | [root676/QNEAT3](https://github.com/root676/QNEAT3) |

## 4) 원격탐사 · 래스터 분석

| 플러그인 | 용도 | GitHub |
|---|---|---|
| **Semi-Automatic Classification Plugin (SCP)** | 위성영상 토지피복 분류·밴드연산·식생지수 | `semiautomaticgit/SemiAutomaticClassificationPlugin` |

## 5) 웹 · 3D 내보내기

| 플러그인 | 용도 | GitHub |
|---|---|---|
| **qgis2web** | 지도를 Leaflet/OpenLayers 웹지도로 내보내기 | `tomchadwin/qgis2web` |
| **Qgis2threejs** | 지형·건물 3D 시각화(웹) | `minorua/Qgis2threejs` |

---

## Processing 백엔드(provider) — 플러그인은 아니지만 강력함

QGIS Processing 툴박스는 외부 GIS 엔진을 알고리즘 공급자로 연결한다.
설치 후 `설정 → 옵션 → 처리(Processing)`에서 활성화한다.

| 엔진 | 강점 | 비고 |
|---|---|---|
| **GDAL** | 래스터/벡터 변환·기본 분석 | QGIS에 기본 내장 |
| **GRASS GIS** | 수문·지형·래스터 고급 분석 | 보통 QGIS 설치 시 동봉 |
| **SAGA GIS** | 지형분석(TWI·경사·곡률)·토양 | 별도 설치 후 경로 지정 |
| **Orfeo Toolbox (OTB)** | 대용량 위성영상 분할·분류 | 별도 다운로드 |
| **WhiteboxTools** | LiDAR·DEM·수문 600+ 도구 | `Whitebox for Processing` 플러그인으로 연결 |

---

## 권장 시작 세트 (목적별)

- **도시·생활권 분석** → QuickOSM + QNEAT3 + Hotspot Analysis + DataPlotly
- **환경·지형 분석** → SAGA/GRASS provider + WhiteboxTools + QuickMapServices
- **위성영상·토지피복** → SCP + OTB provider
- **결과 공유** → qgis2web (웹) / Qgis2threejs (3D)

## 출처

- [QGIS 공식 플러그인 저장소](https://plugins.qgis.org/) · [최다 다운로드](https://plugins.qgis.org/plugins/most_downloaded/) · [spatial-analysis 태그](https://plugins.qgis.org/plugins/tags/spatial-analysis/)
- [DataPlotly](https://github.com/ghtmtt/DataPlotly) · [QNEAT3](https://github.com/root676/QNEAT3) · [HotSpotAnalysis_Plugin](https://github.com/danioxoli/HotSpotAnalysis_Plugin) · [Spatial Analysis Toolbox](https://github.com/parmendel/spatialanalysistoolbox)
