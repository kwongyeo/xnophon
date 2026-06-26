# qgis — 공간분석(QGIS) 작업공간

QGIS를 이용한 공간분석을 위한 표준 폴더 구조. GIS 분석의 일반적 워크플로
**원본 데이터 → 중간 처리 → 분석 산출물**을 그대로 디렉터리로 옮겨,
데이터 출처와 가공 단계를 항상 추적할 수 있게 한다.

## 디렉터리 구조

```
qgis/
├── README.md
├── .gitignore                  대용량 GIS 데이터·산출물 추적 제외 규칙
│
├── data/                       모든 데이터의 단일 루트
│   ├── raw/                    원본 데이터 (다운로드 그대로, 수정 금지)
│   ├── interim/                중간 처리 데이터 (정제·변환 진행 중)
│   ├── processed/              분석 완료 데이터 (최종 분석 입력)
│   ├── vector/                 벡터 레이어 (.shp .geojson .gpkg)
│   ├── raster/                 래스터 레이어 (.tif DEM 위성영상)
│   └── external/               외부 참조 데이터 (행정경계·기준 레이어)
│
├── projects/                   QGIS 프로젝트 파일 (.qgz / .qgs)
├── styles/                     레이어 스타일 (.qml / .sld)
├── layouts/                    인쇄 레이아웃 템플릿 (.qpt)
│
├── scripts/
│   ├── pyqgis/                 PyQGIS 자동화 스크립트 (.py)
│   └── models/                 그래픽 모델러 모델 (.model3)
│
├── outputs/                    분석 산출물 (재생성 가능 → gitignore)
│   ├── maps/                   내보낸 지도 이미지·PDF (.png .pdf)
│   ├── tables/                 분석 결과 표 (.csv .xlsx)
│   └── reports/                보고서 (.md .pdf)
│
└── docs/                       메타데이터·방법론·데이터 출처 기록
```

## 작업 원칙

1. **`data/raw/`는 읽기 전용으로 취급한다.** 원본은 절대 덮어쓰지 않고,
   모든 가공 결과는 `interim/` → `processed/`로 단계별로 저장한다.
2. **재현 가능성.** 분석은 가급적 `scripts/`(PyQGIS) 또는 `models/`(모델러)로
   기록해, 원본 데이터에서 산출물까지 자동 재생성이 가능하도록 한다.
3. **좌표계(CRS) 명시.** 데이터마다 좌표계가 다르면 분석이 어긋난다.
   한국 데이터는 보통 `EPSG:5179`(UTM-K) 또는 `EPSG:5186`을 쓰며,
   레이어별 CRS는 `docs/`의 메타데이터에 기록한다.
4. **대용량 데이터는 git에 올리지 않는다.** `.gitignore`가 일반적인 GIS
   확장자와 `outputs/`를 제외한다. 폴더 구조 자체는 `.gitkeep`으로 유지된다.

## 권장 데이터 형식

| 용도 | 권장 형식 | 비고 |
|---|---|---|
| 벡터 | **GeoPackage (.gpkg)** | shapefile보다 권장 (단일 파일·다중 레이어·필드명 제한 없음) |
| 래스터 | **GeoTIFF (.tif)** | 압축(`COMPRESS=DEFLATE`) 권장 |
| 프로젝트 | **.qgz** | 압축 프로젝트 (스타일·관계 포함) |
| 좌표계 | EPSG 코드로 명시 | 한국: 5179(UTM-K), 5186, 4326(WGS84) |

## 시작하기

1. 분석할 원본 데이터를 `data/raw/`에 넣는다.
2. `projects/`에 QGIS 프로젝트(.qgz)를 만들고 작업을 시작한다.
3. 정제·가공 결과를 `data/processed/`에 저장한다.
4. 완성된 지도·표·보고서를 `outputs/`로 내보낸다.
5. 데이터 출처와 처리 단계를 `docs/`에 기록한다.
