#!/usr/bin/env python3.12
"""
17개 시도 2020→2025 인구 변화 분석지도 (헤드리스 PyQGIS).

입력:
  data/external/skorea-provinces-2018-geo.json   시도 경계 (EPSG:4326, code 2자리)
  data/processed/population_sido.csv              인구 (code, pop_2020, pop_2025)
출력:
  data/processed/sido_population.gpkg             병합·계산 결과 레이어
  outputs/maps/population_change_2020_2025.png     단계구분 분석지도(증감률)
  outputs/maps/population_2025.png                 분석지도(2025 인구 규모)

실행:
  source qgis/scripts/qgis-env.sh
  python3.12 qgis/scripts/pyqgis/make_population_map.py

주의: 반드시 python3.12 로 실행. 2025 인구는 잠정 추정치(헤더 참조).
"""
import csv
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("XDG_RUNTIME_DIR", "/tmp/runtime-root")
Path(os.environ["XDG_RUNTIME_DIR"]).mkdir(parents=True, exist_ok=True)

from qgis.core import (
    QgsApplication, QgsVectorLayer, QgsField, QgsProject, QgsFeature,
    QgsCoordinateReferenceSystem, QgsVectorFileWriter, QgsCoordinateTransformContext,
    QgsGraduatedSymbolRenderer, QgsRendererRange, QgsSymbol, QgsFillSymbol,
    QgsClassificationCustom, QgsRendererRangeLabelFormat,
    QgsPrintLayout, QgsLayoutItemMap, QgsLayoutItemLegend, QgsLayoutItemLabel,
    QgsLayoutPoint, QgsLayoutSize, QgsUnitTypes, QgsLayoutExporter,
    QgsRectangle, QgsTextFormat, QgsPalLayerSettings, QgsVectorLayerSimpleLabeling,
    QgsLayoutItemScaleBar, Qgis, QgsLegendStyle,
)
from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtCore import QVariant, QSizeF

ROOT = Path(__file__).resolve().parents[2]
GEO = ROOT / "data" / "external" / "skorea-provinces-2018-geo.json"
CSV = ROOT / "data" / "processed" / "population_sido.csv"
GPKG = ROOT / "data" / "processed" / "sido_population.gpkg"
MAP_CHANGE = ROOT / "outputs" / "maps" / "population_change_2020_2025.png"
MAP_2025 = ROOT / "outputs" / "maps" / "population_2025.png"
KOREA_CRS = "EPSG:5179"   # UTM-K, 면적/형상 왜곡 최소


BOUNDARY_URL = ("https://raw.githubusercontent.com/southkorea/southkorea-maps/"
                "master/kostat/2018/json/skorea-provinces-2018-geo.json")


def ensure_boundary():
    """시도 경계 GeoJSON이 없으면 GitHub에서 내려받는다(프록시 경유)."""
    if GEO.exists():
        return
    import subprocess
    GEO.parent.mkdir(parents=True, exist_ok=True)
    print(f"▶ 경계 데이터 다운로드: {BOUNDARY_URL}")
    subprocess.run(["curl", "-sSf", "--max-time", "60", "-o", str(GEO), BOUNDARY_URL],
                   check=True)


def build_layer():
    """경계 + 인구 CSV 병합 → 증감 계산 → EPSG:5179 GeoPackage 저장."""
    ensure_boundary()
    pop = {}
    with open(CSV, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            pop[r["code"]] = r
    src = QgsVectorLayer(str(GEO), "src", "ogr")
    if not src.isValid():
        raise SystemExit(f"경계 레이어 로드 실패: {GEO}")

    # 결과를 담을 메모리 레이어 (EPSG:5179)
    mem = QgsVectorLayer(f"MultiPolygon?crs={KOREA_CRS}", "sido", "memory")
    dp = mem.dataProvider()
    dp.addAttributes([
        QgsField("code", QVariant.String),
        QgsField("sido", QVariant.String),
        QgsField("sido_eng", QVariant.String),
        QgsField("pop_2020", QVariant.LongLong),
        QgsField("pop_2025", QVariant.LongLong),
        QgsField("change", QVariant.LongLong),
        QgsField("pct", QVariant.Double),
    ])
    mem.updateFields()

    from qgis.core import QgsCoordinateTransform
    xform = QgsCoordinateTransform(src.crs(),
                                   QgsCoordinateReferenceSystem(KOREA_CRS),
                                   QgsProject.instance())
    for f in src.getFeatures():
        code = str(f["code"])
        if code not in pop:
            continue
        p = pop[code]
        p20, p25 = int(p["pop_2020"]), int(p["pop_2025"])
        chg = p25 - p20
        pct = round(chg / p20 * 100, 2)
        g = f.geometry()
        g.transform(xform)
        nf = QgsFeature(mem.fields())
        nf.setGeometry(g)
        nf.setAttributes([code, p["sido"], p["sido_eng"], p20, p25, chg, pct])
        dp.addFeature(nf)
    mem.updateExtents()

    # GeoPackage 로 저장
    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "GPKG"
    opts.layerName = "sido_population"
    GPKG.parent.mkdir(parents=True, exist_ok=True)
    if GPKG.exists():
        GPKG.unlink()
    QgsVectorFileWriter.writeAsVectorFormatV3(
        mem, str(GPKG), QgsCoordinateTransformContext(), opts)
    print(f"✔ 병합 레이어 저장: {GPKG} (피처 {mem.featureCount()})")
    return str(GPKG)


def graduated_renderer(field, ranges):
    """ranges: [(low, high, color_hex, label)] → QgsGraduatedSymbolRenderer."""
    rr = []
    for lo, hi, hexc, label in ranges:
        sym = QgsFillSymbol.createSimple({
            "color": hexc, "outline_color": "70,70,70,255", "outline_width": "0.25"})
        rr.append(QgsRendererRange(lo, hi, sym, label))
    r = QgsGraduatedSymbolRenderer(field, rr)
    r.setClassificationMethod(QgsClassificationCustom())
    return r


def add_labels(layer, expr, size=9, bold=True):
    s = QgsPalLayerSettings()
    s.fieldName = expr
    s.isExpression = True
    s.placement = Qgis.LabelPlacement.OverPoint if hasattr(Qgis, "LabelPlacement") else 0
    tf = QgsTextFormat()
    f = QFont("Sans"); f.setBold(bold); tf.setFont(f); tf.setSize(size)
    from qgis.core import QgsTextBufferSettings
    buf = QgsTextBufferSettings(); buf.setEnabled(True); buf.setSize(1.0)
    buf.setColor(QColor("white")); tf.setBuffer(buf)
    s.setFormat(tf)
    layer.setLabeling(QgsVectorLayerSimpleLabeling(s))
    layer.setLabelsEnabled(True)


def _label(layout, text, x, y, w, pt, bold=False, color=None):
    it = QgsLayoutItemLabel(layout); it.setText(text)
    f = QFont("Sans"); f.setBold(bold); f.setPointSize(pt); it.setFont(f)
    if color:
        it.setFontColor(color)
    it.attemptResize(QgsLayoutSize(w, pt * 0.6 + 4, QgsUnitTypes.LayoutMillimeters))
    it.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(it)
    return it


def render_layout(layer, title, subtitle, source, out_png, legend_title):
    project = QgsProject.instance()
    # 범례는 프로젝트 레이어 트리에서 채워지므로, 이 지도 레이어만 트리에 둔다
    root = project.layerTreeRoot(); root.removeAllChildren()
    root.addLayer(layer)

    layout = QgsPrintLayout(project); layout.initializeDefaults()
    layout.setUnits(QgsUnitTypes.LayoutMillimeters)

    # 지도 프레임 (A4 가로 기준 여백)
    m = QgsLayoutItemMap(layout)
    m.attemptMove(QgsLayoutPoint(8, 24, QgsUnitTypes.LayoutMillimeters))
    m.attemptResize(QgsLayoutSize(198, 165, QgsUnitTypes.LayoutMillimeters))
    m.setCrs(QgsCoordinateReferenceSystem(KOREA_CRS))   # 축척/거리 단위 정확화
    ext = layer.extent(); ext.scale(1.08)
    m.setExtent(ext); m.setLayers([layer]); m.setBackgroundColor(QColor("white"))
    layout.addLayoutItem(m)

    # 제목 / 부제 (넓은 프레임으로 줄바꿈 방지)
    _label(layout, title, 8, 6, 280, 17, bold=True)
    _label(layout, subtitle, 8, 16, 280, 10)

    # 범례
    lg = QgsLayoutItemLegend(layout); lg.setTitle(legend_title)
    lg.setLinkedMap(m); lg.setLegendFilterByMapEnabled(False)
    lg.setAutoUpdateModel(True)
    lg.setStyleFont(QgsLegendStyle.Title, QFont("Sans", 11, QFont.Bold))
    lg.setStyleFont(QgsLegendStyle.SymbolLabel, QFont("Sans", 9))
    lg.attemptMove(QgsLayoutPoint(210, 28, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(lg)

    # 축척 막대
    sb = QgsLayoutItemScaleBar(layout); sb.setStyle("Single Box")
    sb.setLinkedMap(m)
    sb.setUnits(QgsUnitTypes.DistanceKilometers)
    sb.applyDefaultSize(QgsUnitTypes.DistanceKilometers)   # km 기준 세그먼트 자동 산정
    sb.setNumberOfSegmentsLeft(0)
    sb.attemptMove(QgsLayoutPoint(8, 190, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(sb)

    # 출처
    _label(layout, source, 110, 196, 180, 7, color=QColor(90, 90, 90))

    out_png.parent.mkdir(parents=True, exist_ok=True)
    exporter = QgsLayoutExporter(layout)
    settings = QgsLayoutExporter.ImageExportSettings(); settings.dpi = 200
    res = exporter.exportToImage(str(out_png), settings)
    ok = res == QgsLayoutExporter.Success
    print(f"{'✔' if ok else '✖'} 지도 저장: {out_png}")
    return ok


def main():
    QgsApplication.setPrefixPath("/usr", True)
    qgs = QgsApplication([], False); qgs.initQgis()
    try:
        gpkg = build_layer()

        # --- 지도 1: 증감률(%) 단계구분 (발산형: 적색=감소, 청색=증가) ---
        lyr = QgsVectorLayer(f"{gpkg}|layername=sido_population", "증감률", "ogr")
        QgsProject.instance().addMapLayer(lyr, False)
        ranges_pct = [
            (-10.0, -4.0, "#b2182b", "≤ -4% (큰 감소)"),
            (-4.0, -2.0, "#ef8a62", "-4 ~ -2%"),
            (-2.0, 0.0, "#fddbc7", "-2 ~ 0%"),
            (0.0, 2.0, "#d1e5f0", "0 ~ +2%"),
            (2.0, 12.0, "#2166ac", "≥ +2% (증가)"),
        ]
        lyr.setRenderer(graduated_renderer("pct", ranges_pct))
        add_labels(lyr, "\"sido_eng\" || '\\n' || format_number(\"pct\",1) || '%'", 8)
        render_layout(
            lyr,
            "17개 시도 인구 증감 분석 (2020 → 2025)",
            "주민등록인구 증감률(%) · 청색=증가, 적색=감소",
            "자료: 2020 행정안전부 주민등록인구(확정) / 2025 잠정 추정치(KOSIS DT_1B040A3 대조 필요)\n경계: southkorea-maps(2018) · 좌표계 EPSG:5179",
            MAP_CHANGE, "증감률 (%)")

        # --- 지도 2: 2025 인구 규모 단계구분 ---
        lyr2 = QgsVectorLayer(f"{gpkg}|layername=sido_population", "인구2025", "ogr")
        QgsProject.instance().addMapLayer(lyr2, False)
        ranges_pop = [
            (0, 700000, "#edf8e9", "< 70만"),
            (700000, 1500000, "#bae4b3", "70만 ~ 150만"),
            (1500000, 2500000, "#74c476", "150만 ~ 250만"),
            (2500000, 3500000, "#31a354", "250만 ~ 350만"),
            (3500000, 14000000, "#006d2c", "≥ 350만"),
        ]
        lyr2.setRenderer(graduated_renderer("pop_2025", ranges_pop))
        add_labels(lyr2, "\"sido_eng\" || '\\n' || format_number(\"pop_2025\",0)", 8)
        render_layout(
            lyr2,
            "17개 시도 인구 규모 (2025)",
            "주민등록인구(명) · 잠정 추정치",
            "자료: 2025 잠정 추정치(KOSIS DT_1B040A3 대조 필요)\n경계: southkorea-maps(2018) · 좌표계 EPSG:5179",
            MAP_2025, "2025 인구(명)")
    finally:
        qgs.exitQgis()


if __name__ == "__main__":
    main()
