#!/usr/bin/env python3.12
"""
헤드리스 PyQGIS 예시 — 포인트 레이어에 버퍼를 생성한다.

이 환경(컨테이너)에서 실행:
  source qgis/scripts/qgis-env.sh        # QT_QPA_PLATFORM=offscreen 등 적용
  python3.12 qgis/scripts/pyqgis/example_buffer.py

주의: 기본 python3(3.11)이 아니라 python3.12 로 실행해야 한다(바인딩이 3.12용).

폴더 구조 활용:
  입력  qgis/data/processed/points.geojson
  출력  qgis/outputs/tables/points_buffer.gpkg
"""
import os
import sys
from pathlib import Path

# 화면이 없으면 offscreen 으로 강제 (qgis-env.sh 를 안 거쳐도 동작하도록)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import QgsApplication, QgsVectorLayer

QGIS_ROOT = Path(__file__).resolve().parents[2]
INPUT = QGIS_ROOT / "data" / "processed" / "points.geojson"
OUTPUT = QGIS_ROOT / "outputs" / "tables" / "points_buffer.gpkg"


def main(distance_m: float = 500.0):
    # 1) QGIS 애플리케이션 초기화 (GUI 없음)
    QgsApplication.setPrefixPath("/usr", True)
    qgs = QgsApplication([], False)
    qgs.initQgis()

    try:
        # 2) Processing 프레임워크 + 네이티브 알고리즘 등록
        sys.path.append("/usr/share/qgis/python/plugins")
        import processing
        from processing.core.Processing import Processing
        Processing.initialize()

        # 3) 입력 확인
        if not INPUT.exists():
            raise SystemExit(f"입력 파일이 없습니다: {INPUT}")
        layer = QgsVectorLayer(str(INPUT), "points", "ogr")
        if not layer.isValid():
            raise SystemExit(f"레이어를 불러올 수 없습니다: {INPUT}")
        print(f"입력 CRS={layer.crs().authid()}  피처수={layer.featureCount()}")

        # 4) 버퍼 실행
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        result = processing.run("native:buffer", {
            "INPUT": str(INPUT),
            "DISTANCE": distance_m,    # 레이어 CRS 단위(m)
            "SEGMENTS": 8,
            "DISSOLVE": False,
            "OUTPUT": str(OUTPUT),
        })

        out = QgsVectorLayer(result["OUTPUT"], "buffer", "ogr")
        print(f"✔ 버퍼 저장: {OUTPUT}  (피처수={out.featureCount()}, CRS={out.crs().authid()})")
    finally:
        qgs.exitQgis()


if __name__ == "__main__":
    main()
