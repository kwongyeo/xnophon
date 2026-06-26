# 헤드리스 QGIS 분석 환경

GUI 없이 서버/컨테이너에서 `qgis_process`(CLI)와 PyQGIS(파이썬)로 공간분석을
실행하기 위한 구성. 이 저장소의 클라우드 컨테이너(Ubuntu 24.04)에 실제로
설치·검증되었다.

## 설치 (Ubuntu 24.04)

```bash
sudo bash qgis/scripts/setup_qgis_headless.sh
```

apt universe의 **QGIS 3.34 LTR**과 `python3-qgis`, `qgis-providers`를 설치한다.
멱등이라 이미 설치돼 있으면 건너뛴다.

> ⚠️ **이 컨테이너는 임시(ephemeral)다.** 세션이 끝나면 설치가 사라진다.
> 새 세션마다 위 스크립트를 다시 실행하거나, 아래 SessionStart 훅으로 자동화한다.

## 환경 적용

```bash
source qgis/scripts/qgis-env.sh
```

설정 내용:
- `QT_QPA_PLATFORM=offscreen` — 화면 없이 Qt 구동
- `XDG_RUNTIME_DIR` 지정 — 런타임 경고 제거
- `qpy` 별칭 = `python3.12`

> ⚠️ **파이썬 버전 주의.** 이 컨테이너의 기본 `python3`은 **3.11**이지만,
> apt QGIS 바인딩은 **3.12**용으로 빌드돼 있다. PyQGIS 스크립트는 반드시
> **`python3.12`**(별칭 `qpy`)로 실행해야 한다. `python3`로 실행하면
> `No module named 'PyQt5.sip'` 오류가 난다.

## 사용법

### 1) CLI — `qgis_process`

```bash
# 사용 가능한 알고리즘 목록 / 공급자
qgis_process list
qgis_process plugins

# 특정 알고리즘 도움말
qgis_process help native:buffer

# 버퍼 분석 실행
qgis_process run native:buffer \
  --INPUT=qgis/data/processed/points.geojson \
  --DISTANCE=500 \
  --OUTPUT=qgis/outputs/tables/points_buffer.gpkg
```

### 2) PyQGIS — 파이썬 스크립트 (반드시 python3.12)

```bash
python3.12 qgis/scripts/pyqgis/example_buffer.py
```

`example_buffer.py`는 `QgsApplication` 초기화 → Processing 등록 → 알고리즘
실행까지 헤드리스로 수행하는 표준 템플릿이다.

## 검증 결과 (이 컨테이너 기준)

| 항목 | 결과 |
|---|---|
| QGIS 버전 | 3.34.4-Prizren (LTR) |
| 사용 가능한 알고리즘 | **338개** (native 242 · gdal 56 · qgis 39 + GRASS/OTB 공급자) |
| `qgis_process` CLI | ✔ 정상 |
| PyQGIS (python3.12) | ✔ 정상 (`QgsApplication` 초기화 후 처리 실행) |
| 엔드투엔드 버퍼 분석 | ✔ EPSG:5179 유지, GeoPackage 출력 |

## (선택) 새 세션마다 자동 설치 — SessionStart 훅

컨테이너가 임시이므로, 매 세션 시작 시 자동으로 QGIS를 재설치하려면
`.claude/settings.json`에 SessionStart 훅을 둔다. 설치에 수 분이 걸리는 점은
감안한다.

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [
          { "type": "command",
            "command": "sudo bash qgis/scripts/setup_qgis_headless.sh" }
      ] }
    ]
  }
}
```

## 한계

- **GUI 플러그인은 헤드리스에서 의미가 없다.** `recommended-plugins.md`의
  플러그인 대부분은 데스크톱 GUI용이다. 헤드리스에서는 `qgis_process`의
  내장 알고리즘(native/gdal/qgis)과 GRASS·OTB·SAGA 공급자를 사용한다.
- GRASS/OTB 공급자를 실제로 쓰려면 해당 엔진 패키지(`grass`, OTB)를 추가
  설치해야 한다. 기본 native+gdal+qgis 337개로도 대부분의 분석이 가능하다.
