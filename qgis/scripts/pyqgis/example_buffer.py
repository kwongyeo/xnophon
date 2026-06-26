"""
PyQGIS 시작 예시 — 포인트 레이어에 버퍼를 생성한다.

폴더 구조 활용 예시:
  입력:  qgis/data/processed/  의 벡터 레이어
  출력:  qgis/outputs/tables/  에 결과 저장

실행 (QGIS 파이썬 콘솔):
  exec(open('qgis/scripts/pyqgis/example_buffer.py', encoding='utf-8').read())
"""
from pathlib import Path

from qgis.core import QgsVectorLayer, QgsProject
import processing  # QGIS Processing 프레임워크

# qgis/ 작업공간 루트를 기준으로 경로 구성
QGIS_ROOT = Path(__file__).resolve().parents[2]
INPUT = QGIS_ROOT / "data" / "processed" / "points.gpkg"
OUTPUT = QGIS_ROOT / "outputs" / "tables" / "points_buffer.gpkg"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)


def run(distance_m: float = 500.0):
    layer = QgsVectorLayer(str(INPUT), "points", "ogr")
    if not layer.isValid():
        raise SystemExit(f"레이어를 불러올 수 없습니다: {INPUT}")

    print(f"CRS: {layer.crs().authid()}  |  피처 수: {layer.featureCount()}")

    result = processing.run(
        "native:buffer",
        {
            "INPUT": str(INPUT),
            "DISTANCE": distance_m,   # 레이어 CRS 단위(m) 기준
            "SEGMENTS": 8,
            "DISSOLVE": False,
            "OUTPUT": str(OUTPUT),
        },
    )

    out = QgsVectorLayer(result["OUTPUT"], "points_buffer", "ogr")
    QgsProject.instance().addMapLayer(out)
    print(f"버퍼 저장 완료 → {OUTPUT}")
    return result


if __name__ == "__main__":
    run()
