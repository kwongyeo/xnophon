# PyQGIS 스크립트

QGIS 파이썬 콘솔(`Plugins → Python Console`) 또는 `qgis_process` CLI에서
실행하는 자동화 스크립트를 둔다.

## 실행 방법

**1) QGIS 파이썬 콘솔에서**
```python
exec(open('/경로/qgis/scripts/pyqgis/example_buffer.py').encode('utf-8'))
```

**2) 헤드리스(CLI)에서** — QGIS가 설치된 환경
```bash
qgis_process run native:buffer \
  --INPUT=data/processed/points.gpkg \
  --DISTANCE=500 \
  --OUTPUT=outputs/tables/buffer.gpkg
```

`example_buffer.py`는 폴더 구조를 활용하는 최소 예시다.
