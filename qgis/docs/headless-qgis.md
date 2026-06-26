# 헤드리스 QGIS 분석 환경

GUI 없이 서버/컨테이너에서 `qgis_process`(CLI)와 PyQGIS(파이썬)로 공간분석을
실행하기 위한 구성. 이 저장소의 클라우드 컨테이너(Ubuntu 24.04)에 실제로
설치·검증되었다.

## 설치 (Ubuntu 24.04)

```bash
sudo bash qgis/scripts/setup_qgis_headless.sh
```

apt universe의 **QGIS 3.34 LTR** + `python3-qgis` + `qgis-providers`와
**GRASS 8.3**(+SAGA 바이너리)을 설치하고, **GRASS Processing 공급자를 활성화**한다.
멱등이라 이미 설치돼 있으면 건너뛴다.

> ⚠️ **이 컨테이너는 임시(ephemeral)다.** 세션이 끝나면 설치가 사라진다.
> 새 세션마다 자동 재설치되도록 **SessionStart 훅이 이미 구성**되어 있다
> (`.claude/settings.json` → `sudo bash qgis/scripts/setup_qgis_headless.sh`).
> 설치에 수 분이 걸리는 점은 감안한다.

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

# native 버퍼 분석 (파라미터명 대문자)
qgis_process run native:buffer \
  --INPUT=qgis/data/processed/points.geojson \
  --DISTANCE=500 \
  --OUTPUT=qgis/outputs/tables/points_buffer.gpkg

# GRASS 알고리즘 (접두사 grass7:, 파라미터명 소문자)
qgis_process run grass7:v.buffer \
  --input=qgis/data/processed/points.geojson \
  --distance=300 \
  --output=qgis/outputs/tables/grass_buffer.gpkg
```

> GRASS 알고리즘 ID는 `grass7:` 접두사를 쓰고 파라미터명은 **소문자**(`input`,
> `output`)다. native/gdal/qgis 는 대문자(`INPUT`, `OUTPUT`)를 쓴다.

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
| 사용 가능한 알고리즘 | **644개** (native 242 · grass7 306 · gdal 56 · qgis 39 · 3d 1) |
| `qgis_process` CLI | ✔ 정상 |
| PyQGIS (python3.12) | ✔ 정상 (`QgsApplication` 초기화 후 처리 실행) |
| 엔드투엔드 버퍼 분석 (native) | ✔ EPSG:5179 유지, GeoPackage 출력 |
| 엔드투엔드 GRASS 분석 (grass7:v.buffer) | ✔ EPSG:5179 유지, 폴리곤 출력 |

### Processing 공급자 현황

| 공급자 | 상태 | 비고 |
|---|---|---|
| native (QGIS) | ✔ 244 | 기본 내장 |
| gdal | ✔ 56 | 기본 내장 |
| qgis / 3d | ✔ 40 | 기본 내장 |
| **GRASS** (`grass7:`) | ✔ **306** | `grass`+`grass-core` 설치 후 `grassprovider` 활성화 |
| SAGA | ✖ 미노출 | QGIS 3.34 코어에서 분리. `saga_cmd` 바이너리는 설치되어 독립 실행은 가능하나, QGIS 공급자로 쓰려면 'SAGA NextGen' 플러그인 필요 → `plugins.qgis.org` 프록시 차단(403)으로 설치 불가 |
| OTB (Orfeo) | ✖ 미설치 | apt 패키지 없음 + `orfeo-toolbox.org` 프록시 차단(403)으로 설치 불가 |

## 새 세션마다 자동 설치 — SessionStart 훅 (구성됨)

컨테이너가 임시라, 매 세션 시작 시 QGIS+GRASS가 자동 재설치되도록
`.claude/settings.json`에 SessionStart 훅을 **이미 구성**했다. 설치에 수 분이
걸리므로 `timeout`을 600초로 둔다.

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [
          { "type": "command",
            "command": "sudo bash qgis/scripts/setup_qgis_headless.sh",
            "timeout": 600 }
      ] }
    ]
  }
}
```

## 한계

- **GUI 플러그인은 헤드리스에서 의미가 없다.** `recommended-plugins.md`의
  플러그인 대부분은 데스크톱 GUI용이다. 헤드리스에서는 `qgis_process`의
  내장 알고리즘(native/gdal/qgis)과 **GRASS** 공급자를 사용한다.
- **SAGA / OTB는 이 환경에서 QGIS 공급자로 쓸 수 없다.** SAGA는 QGIS 3.34
  코어에서 분리되어 별도 플러그인이 필요하고, OTB는 apt 패키지가 없는데,
  둘 다 배포처(`plugins.qgis.org`, `orfeo-toolbox.org`)가 조직 egress 정책상
  차단(403)되어 있다. 네트워크 정책이 열린 환경이면 설치 가능하다.
- 그래도 **native+gdal+qgis(337) + GRASS(306) = 644개** 알고리즘으로
  벡터·래스터·지형·수문 등 대부분의 공간분석이 가능하다.
